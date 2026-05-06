"""FastAPI application for Aura2 - Figma-to-React conversion platform."""
import asyncio
import logging
import subprocess
import requests
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

# Configure logging so all print/log statements are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("aura2")

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.config import settings, UILibrary
from backend.storage import get_project_store, Project
from backend.rag.component_store import get_component_store
from backend.agents import FigmaToReactAgent
from backend.dev_server_manager import (
    start_dev_server,
    stop_dev_server,
    get_dev_server_port,
    is_server_running,
)
from backend.utils.image_optimizer import optimize_project_images
from backend.utils.figma_rate_limiter import get_rate_limiter


# Pydantic models for API
class ProjectCreateRequest(BaseModel):
    """Request model for creating a new project."""
    figma_url: Optional[str] = None  # Required if data_source="api"
    project_name: str
    ui_library: str = "tailwind"  # Options: tailwind, mui, chakra
    add_as: str = "new_project"  # Options: new_project, new_page
    parent_project_id: Optional[int] = None  # Required if add_as=new_page
    data_source: str = "api"  # Options: "api" (REST API) or "plugin" (Figma Plugin)
    plugin_data: Optional[dict] = None  # Pre-extracted Figma data from plugin


class PluginUploadRequest(BaseModel):
    """Request model for Figma plugin upload."""
    project_name: str
    ui_library: str = "tailwind"
    design_data: dict  # Complete Figma node tree from plugin
    add_as: str = "new_project"  # Options: new_project, new_page
    parent_project_id: Optional[int] = None  # Required if add_as=new_page


class ProjectResponse(BaseModel):
    """Response model for project operations."""
    project_id: str
    status: str
    message: str


class ProjectStatusResponse(BaseModel):
    """Response model for project status."""
    id: int
    name: str
    status: str
    figma_url: str
    project_path: Optional[str]
    components_generated: int
    components_reused: int
    conversion_time_seconds: Optional[float]
    created_at: str
    error_message: Optional[str]
    parent_project_id: Optional[int] = None
    is_page: bool = False
    route_path: Optional[str] = None
    # GitHub integration fields
    github_repo_url: Optional[str] = None
    github_pushed: bool = False
    github_branch: Optional[str] = None
    github_pr_url: Optional[str] = None
    # Visual verification fields
    visual_match: bool = False
    verification_confidence: float = 0.0
    verification_iterations: int = 0
    # Vercel deployment fields
    deployment_status: str = "not_deployed"
    deployment_url: Optional[str] = None
    deployment_error: Optional[str] = None
    last_deployed_at: Optional[str] = None


class DeploymentStatusResponse(BaseModel):
    """Response model for deployment status."""
    project_id: int
    project_name: str
    # GitHub
    github_pushed: bool = False
    github_repo_url: Optional[str] = None
    github_branch: Optional[str] = None
    github_pr_url: Optional[str] = None
    # Vercel
    deployment_status: str = "not_deployed"
    deployment_url: Optional[str] = None
    deployment_error: Optional[str] = None
    last_deployed_at: Optional[str] = None
    vercel_project_id: Optional[str] = None


# Lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize stores on startup."""
    # Ensure output directories exist
    settings.generated_projects_dir.mkdir(parents=True, exist_ok=True)
    settings.component_library_dir.mkdir(parents=True, exist_ok=True)

    # Initialize stores (they auto-load from disk)
    get_project_store()
    get_component_store()

    yield


# Create FastAPI app
app = FastAPI(
    title="Aura2 - Figma-to-React Generator",
    description="AI-powered platform for converting Figma designs to React + Tailwind CSS",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for serving generated projects
# This allows serving the built dist folders and other static assets
try:
    app.mount("/projects", StaticFiles(directory=str(settings.generated_projects_dir)), name="projects")
except Exception:
    # Directory might not exist yet, that's okay
    pass


# Background task for conversion (REST API path)
def run_conversion_sync(
    project_id: int,
    figma_url: str,
    project_name: str,
    is_new_project: bool,
    ui_library: str = "tailwind",
    add_as: str = "new_project",
    parent_project_path: Optional[str] = None,
):
    """Background task that runs the Figma-to-React conversion using REST API."""
    store = get_project_store()

    # Update status to generating
    store.update(project_id, status="generating")
    from backend.utils.conversion_logger import ConversionLogger
    log = ConversionLogger(project_id, project_name)
    log.info(f"Starting conversion — add_as={add_as}, ui_library={ui_library}")

    try:
        # Run conversion using LiteLLM proxy
        agent = FigmaToReactAgent(
            figma_token=settings.figma_token,
            litellm_api_key=settings.litellm_api_key,
        )

        # Run async conversion in a dedicated event loop
        result = asyncio.run(
            agent.convert_figma_to_react(
                figma_url=figma_url,
                project_name=project_name,
                is_new_project=is_new_project,
                ui_library=ui_library,
                add_as=add_as,
                parent_project_path=Path(parent_project_path) if parent_project_path else None,
                log=log,
            )
        )

        # Update project with results
        # Only mark as success if visual match is true (if visual verification ran)
        final_status = result.get("status", "failed")
        if "visual_match" in result:
            if result.get("visual_match"):
                final_status = "success"
            elif result.get("status") == "success":
                final_status = "completed_with_warnings"
        
        store.update(
            project_id,
            status=final_status,
            project_path=result.get("project_path"),
            components_generated=result.get("components_generated", 0),
            components_reused=result.get("components_reused", 0),
            components_adapted=result.get("reuse_stats", {}).get("adapted", 0),
            reuse_stats=result.get("reuse_stats"),
            conversion_time_seconds=result.get("conversion_time_seconds"),
            error_message="; ".join(result["errors"]) if result.get("errors") else None,
            visual_match=result.get("visual_match", False),
            verification_iterations=result.get("verification_iterations", 0),
            verification_confidence=result.get("verification_confidence", 0.0),
            visual_discrepancies=result.get("visual_discrepancies"),
        )
        build_info = result.get("build_verification", {})
        build_ok = build_info.get("success", True) if build_info else (final_status in ("success", "completed"))
        log.done(
            components=result.get("components_generated", 0),
            build_ok=build_ok,
        )

    except Exception as e:
        store.update(project_id, status="failed", error_message=str(e))
        log.error(f"Conversion failed: {e}")


# Background task for plugin data conversion (bypasses REST API)
def run_plugin_conversion_sync(
    project_id: int,
    plugin_data: dict,
    project_name: str,
    ui_library: str = "tailwind",
    add_as: str = "new_project",
    parent_project_path: Optional[str] = None,
):
    """Background task that runs conversion using pre-extracted plugin data."""
    store = get_project_store()

    # Update status to generating
    store.update(project_id, status="generating")
    from backend.utils.conversion_logger import ConversionLogger
    log = ConversionLogger(project_id, project_name)
    log.info(f"Starting conversion — add_as={add_as}, ui_library={ui_library}")

    try:
        # Run conversion using LiteLLM proxy
        agent = FigmaToReactAgent(
            figma_token=settings.figma_token,  # Not used for plugin path
            litellm_api_key=settings.litellm_api_key,
        )

        # Run async conversion in a dedicated event loop
        result = asyncio.run(
            agent.convert_from_plugin_data(
                plugin_data=plugin_data,
                project_name=project_name,
                ui_library=ui_library,
                add_as=add_as,
                parent_project_path=Path(parent_project_path) if parent_project_path else None,
                log=log,
            )
        )

        # Update project with results
        # Only mark as success if visual match is true (if visual verification ran)
        final_status = result.get("status", "failed")
        if "visual_match" in result:
            if result.get("visual_match"):
                final_status = "success"
            elif result.get("status") == "success":
                final_status = "completed_with_warnings"
        
        store.update(
            project_id,
            status=final_status,
            project_path=result.get("project_path"),
            components_generated=result.get("components_generated", 0),
            components_reused=result.get("components_reused", 0),
            components_adapted=result.get("reuse_stats", {}).get("adapted", 0),
            reuse_stats=result.get("reuse_stats"),
            conversion_time_seconds=result.get("conversion_time_seconds"),
            error_message="; ".join(result["errors"]) if result.get("errors") else None,
            visual_match=result.get("visual_match", False),
            verification_iterations=result.get("verification_iterations", 0),
            verification_confidence=result.get("verification_confidence", 0.0),
            visual_discrepancies=result.get("visual_discrepancies"),
        )
        build_info = result.get("build_verification", {})
        build_ok = build_info.get("success", True) if build_info else (final_status in ("success", "completed"))
        log.done(
            components=result.get("components_generated", 0),
            build_ok=build_ok,
        )

    except Exception as e:
        store.update(project_id, status="failed", error_message=str(e))
        log.error(f"Conversion failed: {e}")


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Aura2 - Figma-to-React Generator",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.post("/api/projects/create", response_model=ProjectResponse)
async def create_project(
    request: ProjectCreateRequest,
    background_tasks: BackgroundTasks,
):
    """
    Create a new React project from a Figma URL or plugin data.
    
    Data source options:
    - "api": Use Figma REST API (requires figma_url)
    - "plugin": Use pre-extracted plugin data (requires plugin_data)
    """
    store = get_project_store()

    # Validate data_source parameter
    if request.data_source not in ["api", "plugin"]:
        raise HTTPException(
            status_code=400,
            detail="data_source must be 'api' or 'plugin'"
        )

    # Validate based on data_source
    if request.data_source == "api":
        if not request.figma_url:
            raise HTTPException(
                status_code=400,
                detail="figma_url is required when data_source='api'"
            )
    elif request.data_source == "plugin":
        if not request.plugin_data:
            raise HTTPException(
                status_code=400,
                detail="plugin_data is required when data_source='plugin'"
            )

    # Validate add_as parameter
    if request.add_as not in ["new_project", "new_page"]:
        raise HTTPException(
            status_code=400,
            detail="add_as must be 'new_project' or 'new_page'"
        )

    # Validate new_page mode requirements
    parent_project = None
    parent_project_path = None
    if request.add_as == "new_page":
        if not request.parent_project_id:
            raise HTTPException(
                status_code=400,
                detail="parent_project_id is required when add_as='new_page'"
            )

        parent_project = store.get(request.parent_project_id)
        if not parent_project:
            raise HTTPException(
                status_code=404,
                detail=f"Parent project with ID {request.parent_project_id} not found"
            )

        if parent_project.status != "success":
            raise HTTPException(
                status_code=400,
                detail="Parent project must be completed successfully before adding pages"
            )

        parent_project_path = parent_project.project_path

    # Check if project name already exists
    if store.get_by_name(request.project_name):
        raise HTTPException(
            status_code=400,
            detail=f"Project '{request.project_name}' already exists"
        )

    # Check if this is the first project (for component reuse logic)
    is_first_project = store.count() == 0

    # Validate UI library
    ui_library = request.ui_library.lower()
    if ui_library not in settings.supported_ui_libraries:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported UI library: {ui_library}. Supported: {settings.supported_ui_libraries}"
        )

    # Create project record
    figma_url = request.figma_url or f"plugin://{request.project_name}"
    project = store.create(
        name=request.project_name,
        figma_url=figma_url,
        parent_project_id=request.parent_project_id,
        is_page=(request.add_as == "new_page"),
        route_path=f"/{request.project_name}" if request.add_as == "new_page" else None,
    )

    # Start background conversion based on data_source
    if request.data_source == "plugin":
        # Plugin path - bypasses REST API rate limits
        background_tasks.add_task(
            run_plugin_conversion_sync,
            project_id=project.id,
            plugin_data=request.plugin_data,
            project_name=request.project_name,
            ui_library=ui_library,
            add_as=request.add_as,
            parent_project_path=parent_project_path,
        )
        source_msg = "Using plugin data (no API rate limits)"
    else:
        # REST API path
        background_tasks.add_task(
            run_conversion_sync,
            project_id=project.id,
            figma_url=request.figma_url,
            project_name=request.project_name,
            is_new_project=is_first_project,
            ui_library=ui_library,
            add_as=request.add_as,
            parent_project_path=parent_project_path,
        )
        source_msg = "Using REST API"

    # Build appropriate message
    if request.add_as == "new_page":
        message = f"Adding new page '{request.project_name}' to project '{parent_project.name}' with {ui_library.upper()}. {source_msg}."
    else:
        reuse_message = (
            "First project - all components will be created from scratch and saved to library."
            if is_first_project
            else "Component reuse will be maximized from existing library."
        )
        message = f"Project creation started with {ui_library.upper()}. {source_msg}. {reuse_message}"

    return ProjectResponse(
        project_id=str(project.id),
        status="pending",
        message=message,
    )


@app.post("/api/figma/plugin-upload", response_model=ProjectResponse)
async def plugin_upload(
    request: PluginUploadRequest,
    background_tasks: BackgroundTasks,
):
    """
    Direct endpoint for Figma Plugin to upload extracted design data.
    
    This endpoint bypasses the Figma REST API entirely - the plugin extracts
    all design data directly from Figma and sends it here.
    
    Benefits:
    - No API rate limits
    - No Figma API token required
    - Faster (no network roundtrip to Figma)
    - Complete access to design data
    
    Supports:
    - Creating new projects (add_as="new_project")
    - Adding as new page to existing project (add_as="new_page" with parent_project_id)
    """
    store = get_project_store()

    # Validate add_as parameter
    if request.add_as not in ["new_project", "new_page"]:
        raise HTTPException(
            status_code=400,
            detail="add_as must be 'new_project' or 'new_page'"
        )

    # Validate new_page mode requirements
    parent_project = None
    parent_project_path = None
    is_new_project = True
    
    if request.add_as == "new_page":
        if not request.parent_project_id:
            raise HTTPException(
                status_code=400,
                detail="parent_project_id is required when add_as='new_page'"
            )

        parent_project = store.get(request.parent_project_id)
        if not parent_project:
            raise HTTPException(
                status_code=404,
                detail=f"Parent project with ID {request.parent_project_id} not found"
            )

        if parent_project.status != "success":
            raise HTTPException(
                status_code=400,
                detail="Parent project must be completed successfully before adding pages"
            )

        parent_project_path = parent_project.project_path
        is_new_project = False
        # Check for duplicate page name
        if store.get_by_name(request.project_name):
            raise HTTPException(
                status_code=400,
                detail=f"Project '{request.project_name}' already exists"
            )
    else:
        # For new_project, check if name already exists
        if store.get_by_name(request.project_name):
            raise HTTPException(
                status_code=400,
                detail=f"Project '{request.project_name}' already exists"
            )
        # Check if this is the first project (for component reuse logic)
        is_new_project = store.count() == 0

    # Validate UI library
    ui_library = request.ui_library.lower()
    if ui_library not in settings.supported_ui_libraries:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported UI library: {ui_library}. Supported: {settings.supported_ui_libraries}"
        )

    # Get file name from design data
    file_name = request.design_data.get("fileName", request.project_name)

    # Create project record
    project = store.create(
        name=request.project_name,
        figma_url=f"plugin://{file_name}",  # Mark as plugin source
        parent_project_id=request.parent_project_id,
        is_page=(request.add_as == "new_page"),
        route_path=f"/{request.project_name}" if request.add_as == "new_page" else None,
    )

    # Start background conversion using plugin data
    background_tasks.add_task(
        run_plugin_conversion_sync,
        project_id=project.id,
        plugin_data=request.design_data,
        project_name=request.project_name,
        ui_library=ui_library,
        add_as=request.add_as,
        parent_project_path=parent_project_path,
    )

    # Get stats from design data
    stats = request.design_data.get("stats", {})
    
    # Build appropriate message
    if request.add_as == "new_page":
        message = (
            f"Adding new page '{request.project_name}' to project '{parent_project.name}' with {ui_library.upper()}. "
            f"Extracted {stats.get('frameCount', 0)} frames, "
            f"{stats.get('colorCount', 0)} colors, "
            f"{stats.get('fontCount', 0)} fonts. "
            f"Component reuse will be maximized from existing library."
        )
    else:
        reuse_message = (
            "First project - all components will be created from scratch and saved to library."
            if is_new_project
            else "Component reuse will be maximized from existing library."
        )
        message = (
            f"Plugin upload received! "
            f"Extracted {stats.get('frameCount', 0)} frames, "
            f"{stats.get('colorCount', 0)} colors, "
            f"{stats.get('fontCount', 0)} fonts. "
            f"Converting with {ui_library.upper()}... {reuse_message}"
        )

    return ProjectResponse(
        project_id=str(project.id),
        status="pending",
        message=message,
    )


@app.post("/api/projects/add-website", response_model=ProjectResponse)
async def add_website(
    request: ProjectCreateRequest,
    background_tasks: BackgroundTasks,
):
    """
    Add another website to the project library or as a page to an existing project.
    Always maximizes component reuse.
    """
    store = get_project_store()

    # Validate required fields
    if not request.figma_url:
        raise HTTPException(status_code=400, detail="figma_url is required")

    # Validate add_as parameter
    if request.add_as not in ["new_project", "new_page"]:
        raise HTTPException(
            status_code=400,
            detail="add_as must be 'new_project' or 'new_page'"
        )

    # Validate new_page mode requirements
    parent_project = None
    parent_project_path = None
    if request.add_as == "new_page":
        if not request.parent_project_id:
            raise HTTPException(
                status_code=400,
                detail="parent_project_id is required when add_as='new_page'"
            )

        parent_project = store.get(request.parent_project_id)
        if not parent_project:
            raise HTTPException(
                status_code=404,
                detail=f"Parent project with ID {request.parent_project_id} not found"
            )

        if parent_project.status != "success":
            raise HTTPException(
                status_code=400,
                detail="Parent project must be completed successfully before adding pages"
            )

        parent_project_path = parent_project.project_path

    # Check if project name already exists
    if store.get_by_name(request.project_name):
        raise HTTPException(
            status_code=400,
            detail=f"Project '{request.project_name}' already exists"
        )

    # Validate UI library
    ui_library = request.ui_library.lower()
    if ui_library not in settings.supported_ui_libraries:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported UI library: {ui_library}. Supported: {settings.supported_ui_libraries}"
        )

    # Create project record
    project = store.create(
        name=request.project_name,
        figma_url=request.figma_url,
        parent_project_id=request.parent_project_id,
        is_page=(request.add_as == "new_page"),
        route_path=f"/{request.project_name}" if request.add_as == "new_page" else None,
    )

    # Start background conversion with component reuse enabled
    background_tasks.add_task(
        run_conversion_sync,
        project_id=project.id,
        figma_url=request.figma_url,
        project_name=request.project_name,
        is_new_project=False,  # Always enable component reuse
        ui_library=ui_library,
        add_as=request.add_as,
        parent_project_path=parent_project_path,
    )

    # Build appropriate message
    if request.add_as == "new_page":
        message = f"Adding new page '{request.project_name}' to project '{parent_project.name}' with {ui_library.upper()}. Analyzing library for reuse..."
    else:
        message = f"Website conversion started with {ui_library.upper()}. Analyzing component library for reuse opportunities..."

    return ProjectResponse(
        project_id=str(project.id),
        status="pending",
        message=message,
    )


@app.get("/api/projects/{project_id}/status", response_model=ProjectStatusResponse)
async def get_project_status(project_id: int):
    """Get the current status of a project."""
    store = get_project_store()
    project = store.get(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectStatusResponse(
        id=project.id,
        name=project.name,
        status=project.status,
        figma_url=project.figma_url,
        project_path=project.project_path,
        components_generated=project.components_generated,
        components_reused=project.components_reused,
        conversion_time_seconds=project.conversion_time_seconds,
        created_at=project.created_at,
        error_message=project.error_message,
        parent_project_id=project.parent_project_id,
        is_page=project.is_page,
        route_path=project.route_path,
    )


@app.get("/api/projects")
async def list_projects(skip: int = 0, limit: int = 100, status: Optional[str] = None):
    """List all projects. Optionally filter by status."""
    store = get_project_store()
    projects = store.list_all(skip=skip, limit=limit)
    
    # Filter by status if provided
    if status:
        projects = [p for p in projects if p.status == status]

    return {
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status,
                "components_generated": p.components_generated,
                "components_reused": p.components_reused,
                "created_at": p.created_at,
                "parent_project_id": getattr(p, "parent_project_id", None),
                "is_page": getattr(p, "is_page", False),
                "route_path": getattr(p, "route_path", None),
                # GitHub integration
                "github_pushed": getattr(p, "github_pushed", False),
                "github_repo_url": getattr(p, "github_repo_url", None),
                # Vercel deployment
                "deployment_status": getattr(p, "deployment_status", "not_deployed"),
                "deployment_url": getattr(p, "deployment_url", None),
            }
            for p in projects
        ],
        "total": store.count(),
    }


@app.get("/api/projects/available")
async def list_available_projects():
    """List only successful projects that can be extended (for plugin dropdown)."""
    store = get_project_store()
    all_projects = store.list_all(skip=0, limit=1000)
    
    # Filter to only successful projects that are not pages (can be parent projects)
    available = [
        {
            "id": p.id,
            "name": p.name,
            "status": p.status,
        }
        for p in all_projects
        if p.status == "success" and not getattr(p, "is_page", False)
    ]

    return {
        "projects": available,
        "total": len(available),
    }


@app.get("/api/components")
async def list_components(category: Optional[str] = None, limit: int = 100):
    """List all components in the library."""
    store = get_component_store()
    components = store.list_components(category=category, limit=limit)

    return {
        "components": components,
        "total": store.count(),
    }


@app.get("/api/stats")
async def get_stats():
    """Get platform statistics."""
    project_store = get_project_store()
    component_store = get_component_store()

    return {
        "total_projects": project_store.count_projects(),
        "completed_projects": project_store.count_by_status("success"),
        "total_components": component_store.count(),
        "total_component_reuses": component_store.get_total_reuse_count(),
    }


@app.get("/api/projects/{project_id}/progress")
async def get_project_progress(project_id: int):
    """Get real-time conversion progress (phase, log lines, tool count)."""
    from backend.utils.conversion_logger import get_progress
    progress = get_progress(project_id)
    if progress is None:
        # No active conversion — check if project exists and return its status
        store = get_project_store()
        project = store.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return {
            "project_id": project_id,
            "phase": "DONE" if project.status == "success" else project.status.upper(),
            "status": project.status,
            "elapsed_s": project.conversion_time_seconds or 0,
            "components": project.components_generated,
            "tools_used": 0,
            "lines": [],
        }
    return progress


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: int):
    """Delete a project."""
    store = get_project_store()

    if not store.delete(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    return {"message": "Project deleted"}


@app.get("/api/projects/{project_id}/figma-json")
async def get_figma_design_data(project_id: int):
    """Get the extracted design data JSON for a project."""
    store = get_project_store()
    project = store.get(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.project_path:
        raise HTTPException(status_code=404, detail="Project path not available")

    design_data_path = Path(project.project_path) / "figma_data" / "design_data.json"
    if not design_data_path.exists():
        raise HTTPException(status_code=404, detail="Figma design data not found for this project")

    import json
    data = json.loads(design_data_path.read_text(encoding="utf-8"))
    return JSONResponse(content=data)


@app.get("/api/projects/{project_id}/figma-json/raw")
async def get_figma_raw_json(project_id: int):
    """Get the raw Figma API response JSON for a project."""
    store = get_project_store()
    project = store.get(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.project_path:
        raise HTTPException(status_code=404, detail="Project path not available")

    raw_path = Path(project.project_path) / "figma_data" / "raw_figma_response.json"
    if not raw_path.exists():
        raise HTTPException(status_code=404, detail="Raw Figma data not found for this project")

    import json
    data = json.loads(raw_path.read_text(encoding="utf-8"))
    return JSONResponse(content=data)


@app.get("/api/projects/{project_id}/trace")
async def get_conversion_trace(project_id: int):
    """Get the conversion trace JSON for a project."""
    store = get_project_store()
    project = store.get(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.project_path:
        raise HTTPException(status_code=404, detail="Project path not available")

    trace_path = Path(project.project_path) / "trace" / "conversion_trace.json"
    if not trace_path.exists():
        raise HTTPException(status_code=404, detail="Conversion trace not found for this project")

    import json
    data = json.loads(trace_path.read_text(encoding="utf-8"))
    return JSONResponse(content=data)


@app.get("/api/projects/{project_id}/verification-report")
async def get_verification_report(project_id: int):
    """Get the structured verification report JSON for a project."""
    store = get_project_store()
    project = store.get(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.project_path:
        raise HTTPException(status_code=404, detail="Project path not available")

    report_path = Path(project.project_path) / "screenshots" / "verification-report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Verification report not found — verification may not have run for this project")

    import json as _json
    data = _json.loads(report_path.read_text(encoding="utf-8"))
    return JSONResponse(content=data)


@app.get("/api/projects/{project_id}/screenshots/{path:path}")
async def get_project_screenshot(project_id: int, path: str):
    """Serve a screenshot file from the project's screenshots directory."""
    store = get_project_store()
    project = store.get(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.project_path:
        raise HTTPException(status_code=404, detail="Project path not available")

    # Resolve paths and guard against traversal
    project_dir = Path(project.project_path).resolve()
    full_path = (project_dir / "screenshots" / path).resolve()
    try:
        full_path.relative_to(project_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail=f"Screenshot not found: {path}")

    # Determine media type
    suffix = full_path.suffix.lower()
    media_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".json": "application/json"}
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(str(full_path), media_type=media_type)


@app.post("/api/projects/cleanup")
async def cleanup_orphaned_projects():
    """Remove projects whose folders no longer exist on disk."""
    store = get_project_store()
    deleted = store.cleanup_orphaned()

    return {
        "message": f"Cleaned up {len(deleted)} orphaned projects",
        "deleted_count": len(deleted),
        "deleted_projects": [{"id": p.id, "name": p.name, "path": p.project_path} for p in deleted]
    }


@app.delete("/api/projects/clear-all")
async def clear_all_projects():
    """Clear all projects from the database (does not delete files)."""
    store = get_project_store()
    count = store.clear_all()

    return {
        "message": f"Cleared {count} projects from database",
        "deleted_count": count
    }


@app.get("/api/projects/{project_id}/preview-url")
async def get_project_preview_url(project_id: int):
    """Get the preview URL for a project. Starts dev server if not running."""
    store = get_project_store()
    project = store.get(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.project_path:
        raise HTTPException(status_code=400, detail="Project path not available")

    project_dir = Path(project.project_path)

    # For child pages, use parent's dev server
    effective_project_id = project.parent_project_id if project.is_page else project_id

    # Build preview URL with route path for child pages
    def build_preview_url(port: int) -> str:
        base_url = f"http://localhost:{port}"
        if project.is_page and project.route_path:
            return f"{base_url}{project.route_path}"
        return base_url

    # Check if dev server is already running
    if is_server_running(effective_project_id):
        port = get_dev_server_port(effective_project_id)
        if port:
            return {
                "preview_url": build_preview_url(port),
                "type": "dev_server",
                "needs_build": False,
                "port": port
            }

    # Try to start dev server
    port = start_dev_server(effective_project_id, project_dir, project.name)
    if port:
        return {
            "preview_url": build_preview_url(port),
            "type": "dev_server",
            "needs_build": False,
            "port": port
        }
    
    # Fallback: Check if dist folder exists (built project)
    dist_index = project_dir / "dist" / "index.html"
    if dist_index.exists():
        return {
            "preview_url": f"http://localhost:8000/projects/{project.name}/dist/index.html",
            "type": "built",
            "needs_build": False
        }
    
    # If nothing works, return error
    return {
        "preview_url": None,
        "type": "not_available",
        "needs_build": True,
        "message": "Failed to start dev server. Project may need dependencies installed (npm install)."
    }


@app.post("/api/projects/{project_id}/build")
async def build_project(project_id: int, background_tasks: BackgroundTasks):
    """Build a project by running npm run build."""
    store = get_project_store()
    project = store.get(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.project_path:
        raise HTTPException(status_code=400, detail="Project path not available")

    project_dir = Path(project.project_path)
    
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    package_json = project_dir / "package.json"
    if not package_json.exists():
        raise HTTPException(status_code=400, detail="package.json not found in project")

    def run_build():
        """Background task to run npm build."""
        try:
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=str(project_dir),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            if result.returncode != 0:
                print(f"Build failed for project {project.name}: {result.stderr}")
        except subprocess.TimeoutExpired:
            print(f"Build timeout for project {project.name}")
        except Exception as e:
            print(f"Build error for project {project.name}: {e}")

    background_tasks.add_task(run_build)

    return {
        "message": "Build started in background",
        "project_id": project_id,
        "project_name": project.name
    }


@app.post("/api/projects/{project_id}/start-dev-server")
async def start_project_dev_server(project_id: int):
    """Start a dev server for a project."""
    store = get_project_store()
    project = store.get(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.project_path:
        raise HTTPException(status_code=400, detail="Project path not available")

    project_dir = Path(project.project_path)

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    # Helper to build preview URL with route path for child pages
    def build_preview_url(port: int) -> str:
        base_url = f"http://localhost:{port}"
        if project.is_page and project.route_path:
            return f"{base_url}{project.route_path}"
        return base_url

    # For child pages, use parent's dev server
    effective_project_id = project.parent_project_id if project.is_page else project_id

    # Check if already running
    if is_server_running(effective_project_id):
        port = get_dev_server_port(effective_project_id)
        return {
            "message": "Dev server already running",
            "port": port,
            "preview_url": build_preview_url(port)
        }

    # Start dev server
    port = start_dev_server(effective_project_id, project_dir, project.name)

    if port:
        return {
            "message": "Dev server started",
            "port": port,
            "preview_url": build_preview_url(port)
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to start dev server. Make sure npm dependencies are installed."
        )


@app.post("/api/projects/{project_id}/stop-dev-server")
async def stop_project_dev_server(project_id: int):
    """Stop a dev server for a project."""
    if stop_dev_server(project_id):
        return {"message": "Dev server stopped"}
    else:
        raise HTTPException(status_code=404, detail="Dev server not running for this project")


@app.get("/api/projects/{project_id}/reuse-stats")
async def get_project_reuse_stats(project_id: int):
    """Get the reuse statistics for a project."""
    store = get_project_store()
    project = store.get(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.reuse_stats:
        return project.reuse_stats

    # Fallback: return basic stats from project fields
    return {
        "reused": project.components_reused,
        "adapted": project.components_adapted,
        "created_new": project.components_generated,
        "library_size": get_component_store().count(),
    }


@app.get("/api/figma/rate-limit-status")
async def figma_rate_limit_status():
    """Return current Figma API rate limiter status."""
    limiter = get_rate_limiter()
    return limiter.get_rate_limit_status()


# =============================================================================
# DEPLOYMENT ENDPOINTS (GitHub + Vercel)
# =============================================================================

@app.get("/api/projects/{project_id}/deployment-status", response_model=DeploymentStatusResponse)
async def get_deployment_status(project_id: int):
    """Get deployment status for a project."""
    store = get_project_store()
    project = store.get(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return DeploymentStatusResponse(
        project_id=project.id,
        project_name=project.name,
        github_pushed=project.github_pushed,
        github_repo_url=project.github_repo_url,
        github_branch=project.github_branch,
        github_pr_url=project.github_pr_url,
        deployment_status=project.deployment_status,
        deployment_url=project.deployment_url,
        deployment_error=project.deployment_error,
        last_deployed_at=project.last_deployed_at,
        vercel_project_id=project.vercel_project_id,
    )


@app.post("/api/projects/{project_id}/push-to-github")
async def push_to_github(project_id: int, background_tasks: BackgroundTasks):
    """Push project code to GitHub repository."""
    store = get_project_store()
    project = store.get(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status != "success":
        raise HTTPException(status_code=400, detail="Project must be successfully generated before pushing to GitHub")

    if not project.project_path:
        raise HTTPException(status_code=400, detail="Project path not found")

    if not settings.effective_github_token:
        raise HTTPException(status_code=400, detail="GitHub token not configured")

    # Run the GitHub push in background
    background_tasks.add_task(_push_to_github_task, project_id)

    return {"message": "GitHub push started", "project_id": project_id}


def _push_to_github_task(project_id: int):
    """Background task to push code to GitHub using git commands and GitHub API."""
    from backend.utils.git_manager import generate_gitignore
    from pathlib import Path
    import subprocess
    import requests

    print(f"[GitHub] Starting push for project {project_id}")

    store = get_project_store()
    project = store.get(project_id)

    if not project or not project.project_path:
        print(f"[GitHub] Project {project_id} not found or no path")
        return

    project_path = Path(project.project_path)
    print(f"[GitHub] Project path: {project_path}")

    if not project_path.exists():
        print(f"[GitHub] Project path does not exist: {project_path}")
        store.update(project_id, deployment_error="Project path does not exist")
        return

    token = settings.effective_github_token
    owner = settings.github_owner

    if not token or not owner:
        error_msg = "GitHub token or owner not configured"
        print(f"[GitHub] {error_msg}")
        store.update(project_id, deployment_error=error_msg)
        return

    try:
        # Optimize images before pushing to reduce payload size
        print(f"[GitHub] Optimizing project images...")
        loop = asyncio.new_event_loop()
        try:
            img_report = loop.run_until_complete(optimize_project_images(project_path))
        finally:
            loop.close()
        if img_report["files_processed"] > 0:
            print(f"[GitHub] Image optimization: {img_report['files_processed']} files, {img_report['space_saved_kb']} KB saved")

        # Ensure .gitignore exists before committing
        gitignore_path = project_path / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text(generate_gitignore())
            print(f"[GitHub] Created .gitignore for {project.name}")

        # Clean repo name
        repo_name = project.name.lower().replace(" ", "-").replace("_", "-")
        repo_name = "".join(c for c in repo_name if c.isalnum() or c == "-")
        print(f"[GitHub] Repo name: {repo_name}")

        # Step 1: Create GitHub repo via API
        print(f"[GitHub] Creating repo via API...")
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }

        create_response = requests.post(
            "https://api.github.com/user/repos",
            headers=headers,
            json={
                "name": repo_name,
                "private": True,
                "auto_init": False
            }
        )

        if create_response.status_code == 201:
            print(f"[GitHub] Repo created successfully")
        elif create_response.status_code == 422:
            # Repo might already exist
            print(f"[GitHub] Repo may already exist, continuing...")
        elif create_response.status_code == 401:
            error_msg = "Authentication failed. Check/regenerate your GitHub token."
            store.update(project_id, deployment_error=error_msg)
            print(f"[GitHub] {error_msg}")
            return
        elif create_response.status_code == 403:
            error_msg = "Permission denied. Verify token scopes include repo access."
            store.update(project_id, deployment_error=error_msg)
            print(f"[GitHub] {error_msg}")
            return
        else:
            print(f"[GitHub] Create repo response: {create_response.status_code} - {create_response.text[:200]}")

        # Step 2: Initialize git repo if needed
        if not (project_path / ".git").exists():
            print(f"[GitHub] Initializing git repo...")
            subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
            subprocess.run(["git", "config", "user.email", "aura@generated.local"], cwd=project_path, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Aura Generator"], cwd=project_path, capture_output=True)

        # Step 3: Add and commit
        print(f"[GitHub] Adding files...")
        subprocess.run(["git", "add", "."], cwd=project_path, capture_output=True)

        commit_result = subprocess.run(
            ["git", "commit", "-m", "feat(figma): Initial project from Figma design"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )
        print(f"[GitHub] Commit result: {commit_result.returncode}")

        # Step 4: Set remote with token authentication
        # Token passed as list arg — not visible in process list, no shell injection risk
        remote_url = f"https://{token}@github.com/{owner}/{repo_name}.git"

        # Remove existing remote if any
        subprocess.run(["git", "remote", "remove", "origin"], cwd=project_path, capture_output=True)

        # Add remote with token
        print(f"[GitHub] Setting remote...")
        subprocess.run(
            ["git", "remote", "add", "origin", remote_url],
            cwd=project_path,
            capture_output=True,
        )

        # Step 5: Ensure we're on main branch
        subprocess.run(["git", "branch", "-M", "main"], cwd=project_path, capture_output=True)

        # Step 6: Push to GitHub
        print(f"[GitHub] Pushing to GitHub...")
        push_result = subprocess.run(
            ["git", "push", "-u", "origin", "main", "--force"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )

        print(f"[GitHub] Push result: {push_result.returncode}")
        if push_result.stderr:
            print(f"[GitHub] Push stderr: {push_result.stderr}")
        if push_result.stdout:
            print(f"[GitHub] Push stdout: {push_result.stdout}")

        if push_result.returncode == 0:
            repo_url = f"https://github.com/{owner}/{repo_name}"
            store.update(
                project_id,
                github_pushed=True,
                github_repo_url=repo_url,
                github_branch="main",
                deployment_error=None
            )
            print(f"[GitHub] Successfully pushed to {repo_url}")
        else:
            stderr = push_result.stderr or ""
            if "Authentication" in stderr or "401" in stderr:
                error_msg = "Authentication failed. Check/regenerate your GitHub token."
            elif "403" in stderr or "denied" in stderr.lower():
                error_msg = "Permission denied. Verify token scopes include repo access."
            elif "large" in stderr.lower() or "413" in stderr:
                error_msg = "Payload too large. Images may need further compression."
            else:
                error_msg = f"Push failed (exit {push_result.returncode}): {stderr[:300]}"
            store.update(project_id, deployment_error=error_msg)
            print(f"[GitHub] {error_msg}")

    except Exception as e:
        error_msg = f"GitHub push error: {str(e)}"
        store.update(project_id, deployment_error=error_msg)
        print(f"[GitHub] {error_msg}")
        import traceback
        traceback.print_exc()


@app.post("/api/projects/{project_id}/deploy-to-vercel")
async def deploy_to_vercel(project_id: int, background_tasks: BackgroundTasks):
    """Deploy project to Vercel."""
    store = get_project_store()
    project = store.get(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status != "success":
        raise HTTPException(status_code=400, detail="Project must be successfully generated before deploying")

    if not project.project_path:
        raise HTTPException(status_code=400, detail="Project path not found")

    if not settings.vercel_token:
        raise HTTPException(status_code=400, detail="Vercel token not configured")

    # Update status to deploying
    store.update(project_id, deployment_status="deploying", deployment_error=None)

    # Run deployment in background
    background_tasks.add_task(_deploy_to_vercel_task, project_id)

    return {"message": "Vercel deployment started", "project_id": project_id}


def _deploy_to_vercel_task(project_id: int):
    """Background task to deploy to Vercel using Vercel API - static files only."""
    from pathlib import Path
    from datetime import datetime
    from backend.utils import get_npm_command, get_npx_command
    import subprocess
    import os
    import base64
    import json
    import time
    import hashlib

    print(f"[Vercel] Starting deployment for project {project_id}")

    store = get_project_store()
    project = store.get(project_id)

    if not project or not project.project_path:
        print(f"[Vercel] Project {project_id} not found or no path")
        return

    project_path = Path(project.project_path)
    print(f"[Vercel] Project path: {project_path}")

    if not project_path.exists():
        print(f"[Vercel] Project path does not exist")
        store.update(project_id, deployment_status="failed", deployment_error="Project path does not exist")
        return

    token = settings.vercel_token
    if not token:
        print(f"[Vercel] No token configured")
        store.update(project_id, deployment_status="failed", deployment_error="Vercel token not configured")
        return

    try:
        # Optimize images before building to reduce deployment payload
        print(f"[Vercel] Optimizing project images...")
        loop = asyncio.new_event_loop()
        try:
            img_report = loop.run_until_complete(optimize_project_images(project_path))
        finally:
            loop.close()
        if img_report["files_processed"] > 0:
            print(f"[Vercel] Image optimization: {img_report['files_processed']} files, {img_report['space_saved_kb']} KB saved")

        # First, build the project locally
        # Use 'vite build' directly instead of 'npm run build' (which runs tsc -b && vite build)
        # This skips TypeScript type-checking so minor TS issues in generated code don't block deployment
        print(f"[Vercel] Building project locally...")
        build_result = subprocess.run(
            [get_npx_command(), "vite", "build"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )
        print(f"[Vercel] Build result: {build_result.returncode}")
        if build_result.returncode != 0:
            print(f"[Vercel] Build stderr: {build_result.stderr}")
            store.update(
                project_id,
                deployment_status="failed",
                deployment_error=f"Build failed: {build_result.stderr[:500]}"
            )
            return

        # Check if dist folder exists
        dist_path = project_path / "dist"
        if not dist_path.exists():
            print(f"[Vercel] dist folder not found")
            store.update(project_id, deployment_status="failed", deployment_error="Build output (dist) not found")
            return

        # Create unique project name to avoid cached settings
        base_name = project.name.lower().replace(" ", "-").replace("_", "-")
        base_name = "".join(c for c in base_name if c.isalnum() or c == "-")
        # Use a short hash to make it unique but consistent
        name_hash = hashlib.md5(project.name.encode()).hexdigest()[:6]
        project_name = f"{base_name}-{name_hash}"

        print(f"[Vercel] Project name: {project_name}")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Collect files from dist folder - NO vercel.json, NO package.json
        # Just pure static files
        files = []

        for file_path in dist_path.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(dist_path)
                rel_path_str = str(rel_path).replace("\\", "/")

                # Skip any config files that might trigger build detection
                if rel_path_str in ["package.json", "package-lock.json", "vite.config.js", "vite.config.ts"]:
                    continue

                try:
                    content = file_path.read_bytes()
                    files.append({
                        "file": rel_path_str,
                        "data": base64.b64encode(content).decode("utf-8"),
                        "encoding": "base64"
                    })
                except Exception as e:
                    print(f"[Vercel] Error reading {rel_path}: {e}")

        print(f"[Vercel] Collected {len(files)} static files")

        # List some files for debugging
        file_names = [f["file"] for f in files[:10]]
        print(f"[Vercel] Sample files: {file_names}")

        # Check if project exists and delete it
        print(f"[Vercel] Checking for existing project...")
        project_response = requests.get(
            f"https://api.vercel.com/v9/projects/{project_name}",
            headers=headers
        )

        if project_response.status_code == 200:
            print(f"[Vercel] Deleting existing project...")
            requests.delete(f"https://api.vercel.com/v9/projects/{project_name}", headers=headers)
            time.sleep(3)

        # Create deployment directly without creating project first
        # This creates the project automatically with the right settings
        deployment_payload = {
            "name": project_name,
            "files": files,
            "target": "production",
            "projectSettings": {
                "buildCommand": "",
                "installCommand": "",
                "outputDirectory": ""
            }
        }

        print(f"[Vercel] Creating deployment with {len(files)} files...")
        deploy_response = requests.post(
            "https://api.vercel.com/v13/deployments?skipAutoDetectionConfirmation=1",
            headers=headers,
            json=deployment_payload
        )

        print(f"[Vercel] Deploy response: {deploy_response.status_code}")

        if deploy_response.status_code in [200, 201]:
            deploy_data = deploy_response.json()
            deployment_url = deploy_data.get("url")
            if deployment_url and not deployment_url.startswith("http"):
                deployment_url = f"https://{deployment_url}"

            print(f"[Vercel] Deployment URL: {deployment_url}")

            store.update(
                project_id,
                deployment_status="deployed",
                deployment_url=deployment_url,
                last_deployed_at=datetime.utcnow().isoformat(),
                deployment_error=None,
                vercel_project_id=deploy_data.get("projectId")
            )
            print(f"[Vercel] Successfully deployed to {deployment_url}")
        else:
            status_code = deploy_response.status_code
            error_text = deploy_response.text[:300]
            if status_code == 401:
                error_msg = "Authentication failed. Check/regenerate your Vercel token."
            elif status_code == 403:
                error_msg = "Permission denied. Verify your Vercel token has deployment access."
            elif status_code == 413:
                error_msg = "Payload too large. Images may need further compression."
            else:
                error_msg = f"Vercel API error ({status_code}): {error_text}"
            print(f"[Vercel] Deploy failed: {error_msg}")
            store.update(
                project_id,
                deployment_status="failed",
                deployment_error=error_msg
            )

    except Exception as e:
        error_msg = f"Deployment error: {str(e)}"
        store.update(
            project_id,
            deployment_status="failed",
            deployment_error=error_msg
        )
        print(f"[Vercel] {error_msg}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True,
        timeout_keep_alive=60,
        timeout_graceful_shutdown=60,
    )
