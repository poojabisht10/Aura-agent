"""Main Figma-to-React conversion agent using Claude Agent SDK."""
import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Optional

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ResultMessage,
)

from backend.config import settings
from backend.utils.conversion_logger import ConversionLogger
from backend.utils.trace_logger import ConversionTrace

_logger = logging.getLogger("aura2")
from backend.mcp_tools.component_library import create_component_library_server
from backend.utils.code_quality import run_all_quality_checks
from backend.utils.build_verifier import verify_build
from backend.utils.git_manager import is_github_enabled
from backend.utils import get_npx_command

# Import from refactored modules
from backend.agents._figma_to_react.project_setup import (
    configure_litellm,
    setup_project_from_template,
)
from backend.agents._figma_to_react.figma_extraction import (
    extract_figma_file_key,
    extract_complete_design_data,
)
from backend.agents._figma_to_react.figma_api import (
    fetch_figma_data,
    download_figma_images,
)
from backend.agents._figma_to_react.plugin_conversion import (
    convert_plugin_data_to_design_data,
    save_plugin_images,
)
from backend.agents._figma_to_react.figma_json_persistence import save_figma_json
from backend.agents._figma_to_react.prompt_generation import (
    get_system_prompt,
    build_conversion_prompt,
)
from backend.agents._figma_to_react.verification import (
    visual_verification_loop,
    apply_fixes,
)

# Re-export commonly used functions for backward compatibility
from backend.agents._figma_to_react.design_styles import (
    rgba_to_hex,
    extract_text_style,
    extract_layout_info,
    extract_effects,
    extract_fills,
    extract_strokes,
    extract_corner_radius,
)
from backend.agents._figma_to_react.figma_extraction import (
    extract_node_data,
    collect_image_refs,
    collect_colors_and_fonts,
)
from backend.agents._figma_to_react.prompt_generation import (
    design_data_to_prompt_text,
    format_frame_for_prompt,
)
from backend.agents._figma_to_react.semantic_analysis import (
    infer_semantic_type,
    get_aria_role,
)


class FigmaToReactAgent:
    """Agent that converts Figma designs to React + Tailwind CSS projects."""

    def __init__(self, figma_token: str, litellm_api_key: Optional[str] = None):
        self.figma_token = figma_token
        self.litellm_api_key = litellm_api_key or settings.litellm_api_key
        configure_litellm()

    async def convert_figma_to_react(
        self,
        figma_url: str,
        project_name: str,
        is_new_project: bool = True,
        output_dir: Optional[Path] = None,
        ui_library: str = "tailwind",
        add_as: str = "new_project",
        parent_project_path: Optional[Path] = None,
        log: Optional[ConversionLogger] = None,
    ) -> dict:
        """Main conversion pipeline with comprehensive Figma data extraction.

        Args:
            figma_url: Figma file URL
            project_name: Name for the generated project
            is_new_project: Whether this is a new project or extending existing
            output_dir: Optional output directory override
            ui_library: UI library to use (tailwind, mui, chakra)
            add_as: Either "new_project" (create new directory) or "new_page" (add to existing project)
            parent_project_path: Required when add_as="new_page" - path to parent project

        Returns:
            Conversion result dict with status, path, etc.
        """
        output_dir = output_dir or settings.generated_projects_dir
        start_time = time.time()

        # Extract Figma file key
        file_key = extract_figma_file_key(figma_url)
        if not file_key:
            return {
                "status": "failed",
                "project_path": None,
                "errors": ["Could not extract Figma file key from URL"],
            }

        print(f"[Figma] Fetching design data for file: {file_key}")

        # Fetch complete Figma data
        figma_data = await fetch_figma_data(file_key, self.figma_token)

        if "error" in figma_data:
            return {
                "status": "failed",
                "project_path": None,
                "errors": [figma_data["error"]],
            }

        # Extract complete design data
        print("[Figma] Extracting complete design data...")
        design_data = extract_complete_design_data(figma_data)

        if "error" in design_data:
            return {
                "status": "failed",
                "project_path": None,
                "errors": [design_data["error"]],
            }

        # Log extraction stats
        stats = design_data.get("stats", {})
        print(f"[Figma] Extracted: {stats.get('pageCount', 0)} pages, "
              f"{stats.get('frameCount', 0)} frames, "
              f"{stats.get('colorCount', 0)} colors, "
              f"{stats.get('fontCount', 0)} fonts, "
              f"{stats.get('imageCount', 0)} images")

        # Set up project - either new project or use existing parent
        if add_as == "new_page":
            if not parent_project_path:
                return {
                    "status": "failed",
                    "project_path": None,
                    "errors": ["parent_project_path required when add_as='new_page'"],
                }

            project_path = Path(parent_project_path)
            print(f"[Project] Adding page to existing project at: {project_path}")

            # Ensure pages directory exists
            pages_dir = project_path / "src" / "pages"
            pages_dir.mkdir(parents=True, exist_ok=True)
        else:
            # New project mode - set up from template
            project_path = setup_project_from_template(project_name, output_dir, ui_library)
            print(f"[Project] Created at: {project_path}")

        # Persist raw Figma JSON and extracted design data
        figma_data_dir = save_figma_json(
            project_path=project_path,
            raw_data=figma_data,
            design_data=design_data,
            source="api",
            file_key=file_key,
        )
        print(f"[Figma] Saved design data to: {figma_data_dir}")

        # Download all images from Figma BEFORE starting the agent
        image_refs_dict = design_data.get("imageRefs", {})
        images_dir = project_path / "public" / "images"
        downloaded_images = {}

        if image_refs_dict:
            print(f"[Images] Downloading {len(image_refs_dict)} images from Figma...")
            downloaded_images = await download_figma_images(
                file_key=file_key,
                image_refs_dict=image_refs_dict,
                figma_token=self.figma_token,
                output_dir=images_dir,
            )
            print(f"[Images] Downloaded {len(downloaded_images)} images")
            if len(downloaded_images) < len(image_refs_dict):
                missing = len(image_refs_dict) - len(downloaded_images)
                print(f"[Images] WARNING: {missing} image(s) failed to download — agent will run with incomplete image set")

        # Run conversion with agent
        return await self._run_agent_conversion(
            figma_url=figma_url,
            project_name=project_name,
            project_path=project_path,
            design_data=design_data,
            downloaded_images=downloaded_images,
            is_new_project=is_new_project,
            ui_library=ui_library,
            add_as=add_as,
            start_time=start_time,
            log=log,
        )

    async def convert_from_plugin_data(
        self,
        plugin_data: dict,
        project_name: str,
        ui_library: str = "tailwind",
        output_dir: Optional[Path] = None,
        add_as: str = "new_project",
        parent_project_path: Optional[Path] = None,
        log: Optional[ConversionLogger] = None,
    ) -> dict:
        """
        Convert Figma design using pre-extracted plugin data.

        This method bypasses the Figma REST API entirely - the data is already
        extracted by the Figma Plugin and sent directly to the backend.

        Args:
            plugin_data: Pre-extracted design data from Figma Plugin
            project_name: Name for the generated project
            ui_library: UI library to use (tailwind, mui, chakra)
            output_dir: Optional output directory override
            add_as: Either "new_project" or "new_page"
            parent_project_path: Required when add_as="new_page"

        Returns:
            Conversion result dict with status, path, etc.
        """
        output_dir = output_dir or settings.generated_projects_dir
        start_time = time.time()

        # Convert plugin data format to design data format
        design_data = convert_plugin_data_to_design_data(plugin_data)

        if "error" in design_data:
            return {
                "status": "failed",
                "project_path": None,
                "errors": [design_data["error"]],
            }

        # Log stats
        stats = design_data.get("stats", {})
        if log:
            log.info(f"Design: {stats.get('pageCount', 0)} pages, "
                     f"{stats.get('frameCount', 0)} frames, "
                     f"{stats.get('colorCount', 0)} colors, "
                     f"{stats.get('fontCount', 0)} fonts, "
                     f"{stats.get('imageCount', 0)} images")
            log.info(f"Screenshot in plugin data: {'YES' if design_data.get('designScreenshot') else 'NO'}")
        else:
            _logger.info(f"[Plugin] Design: {stats.get('pageCount', 0)} pages, {stats.get('frameCount', 0)} frames")

        # Set up project - either new project or use existing parent
        if add_as == "new_page":
            if not parent_project_path:
                return {
                    "status": "failed",
                    "project_path": None,
                    "errors": ["parent_project_path required when add_as='new_page'"],
                }

            project_path = Path(parent_project_path)
            pages_dir = project_path / "src" / "pages"
            pages_dir.mkdir(parents=True, exist_ok=True)
            if log:
                log.info(f"Adding page to existing project at {project_path}")
        else:
            project_path = setup_project_from_template(project_name, output_dir, ui_library)
            if log:
                log.info(f"Created project at {project_path}")

        # Persist raw plugin data and extracted design data
        figma_data_dir = save_figma_json(
            project_path=project_path,
            raw_data=plugin_data,
            design_data=design_data,
            source="plugin",
        )
        print(f"[Figma] Saved design data to: {figma_data_dir}")

        # Process images from plugin data (base64 encoded)
        if log:
            log.phase("IMAGES")
        images_dir = project_path / "public" / "images"
        downloaded_images = {}

        plugin_images = plugin_data.get("images", {})
        if plugin_images:
            if log:
                log.info(f"Processing {len(plugin_images)} images from plugin…")
            downloaded_images = await save_plugin_images(plugin_images, images_dir)
            if log:
                log.info(f"Saved {len(downloaded_images)}/{len(plugin_images)} images")
                for ref, path in list(downloaded_images.items())[:5]:
                    log.info(f"  {ref[:20]} → {path}")
        else:
            if log:
                log.info("No images in plugin data")

        # FIXED: Don't override is_new_project based on library state
        is_new_project = (add_as == "new_project")

        # Save design screenshot for visual reference (if plugin captured one)
        design_screenshot_path = None
        screenshot_b64 = design_data.get("designScreenshot")
        if screenshot_b64:
            from backend.utils.figma_screenshot import save_plugin_screenshot
            screenshots_dir = project_path / "screenshots"
            design_screenshot_path = save_plugin_screenshot(
                {"designScreenshot": screenshot_b64}, screenshots_dir
            )
            if design_screenshot_path and log:
                size_kb = design_screenshot_path.stat().st_size // 1024
                log.info(f"Design screenshot saved: {design_screenshot_path} ({size_kb}KB)")
        elif log:
            log.warn("No designScreenshot in plugin data — agent won't have visual reference")

        # Run conversion with agent
        return await self._run_agent_conversion(
            figma_url=f"plugin://{plugin_data.get('fileName', project_name)}",
            project_name=project_name,
            project_path=project_path,
            design_data=design_data,
            downloaded_images=downloaded_images,
            is_new_project=is_new_project,
            ui_library=ui_library,
            add_as=add_as,
            start_time=start_time,
            log=log,
            design_screenshot_path=design_screenshot_path,
        )

    async def _run_agent_conversion(
        self,
        figma_url: str,
        project_name: str,
        project_path: Path,
        design_data: dict,
        downloaded_images: dict,
        is_new_project: bool,
        ui_library: str,
        add_as: str,
        start_time: float,
        log: Optional[ConversionLogger] = None,
        design_screenshot_path: Optional[Path] = None,
    ) -> dict:
        """Run the Claude agent to perform the conversion.

        This is the core conversion logic shared between convert_figma_to_react
        and convert_from_plugin_data.
        """
        if log is None:
            log = ConversionLogger(0, project_name)

        # Initialise conversion trace (observability)
        trace: ConversionTrace | None = None
        if settings.enable_trace_logging:
            trace = ConversionTrace(
                project_id=getattr(log, "project_id", 0),
                project_name=project_name,
            )
            trace.model = settings.default_model
            trace.ui_library = ui_library
            # Update Langfuse trace tags now that ui_library is known
            if trace._lf_trace:
                try:
                    trace._lf_trace.update(
                        tags=["aura2", "figma-to-react", ui_library],
                        metadata={"model": settings.default_model, "ui_library": ui_library},
                    )
                except Exception:
                    pass

        log.phase("SETUP")
        log.info(f"Project: {project_name} at {project_path}")
        log.info(f"Design: {design_data.get('stats', {}).get('pageCount', 0)} pages, "
                 f"{design_data.get('stats', {}).get('frameCount', 0)} frames, "
                 f"{design_data.get('stats', {}).get('colorCount', 0)} colors, "
                 f"{design_data.get('stats', {}).get('fontCount', 0)} fonts")
        log.info(f"Images downloaded: {len(downloaded_images)}")
        if design_screenshot_path:
            log.info(f"Design screenshot: {design_screenshot_path} ({design_screenshot_path.stat().st_size // 1024}KB)")
        else:
            log.warn("No design screenshot available — agent will work from data only")
        # Create component library MCP server
        component_library_server = create_component_library_server()

        # Configure MCP servers
        mcp_servers = {
            "playwright": {
                "type": "stdio",
                "command": get_npx_command(),
                "args": ["@playwright/mcp@latest"],
            },
            "component_library": component_library_server,
        }

        # Add GitHub MCP Server for git integration
        if settings.effective_github_token and settings.auto_create_repo:
            mcp_servers["github"] = {
                "type": "stdio",
                "command": get_npx_command(),
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {
                    "GITHUB_PERSONAL_ACCESS_TOKEN": settings.effective_github_token,
                },
            }
            log.info("GitHub MCP Server enabled")

        # Add Vercel MCP Server for deployment
        if settings.is_vercel_enabled:
            mcp_servers["vercel"] = {
                "type": "stdio",
                "command": get_npx_command(),
                "args": ["-y", "@vercel/mcp"],
                "env": {
                    "VERCEL_TOKEN": settings.vercel_token,
                    **({"VERCEL_ORG_ID": settings.vercel_org_id} if settings.vercel_org_id else {}),
                },
            }
            log.info("Vercel MCP Server enabled")

        log.info(f"MCP servers: {list(mcp_servers.keys())}")

        system_prompt = get_system_prompt(
            is_new_project,
            ui_library,
            add_as,
            project_name,
            has_github=bool(settings.effective_github_token and settings.auto_create_repo),
            has_vercel=settings.is_vercel_enabled,
        )
        log.info(f"System prompt: {len(system_prompt)} chars")
        if trace:
            trace.log_system_prompt(system_prompt)

        options = ClaudeAgentOptions(
            model=settings.default_model,
            system_prompt=system_prompt,
            max_turns=settings.max_agent_turns,
            cwd=str(project_path),
            max_buffer_size=20 * 1024 * 1024,  # 20MB - handles large base64 screenshots
            allowed_tools=[
                "Read", "Write", "Edit", "Bash", "Glob", "Grep",
                "TodoWrite", "KillShell", "BashOutput", "TaskOutput",
                "mcp__component_library__search_components",
                "mcp__component_library__save_component",
                "mcp__component_library__get_component",
                "mcp__component_library__get_reuse_report",
                # Playwright tools for thorough visual testing
                "mcp__playwright__browser_navigate",
                "mcp__playwright__browser_take_screenshot",
                "mcp__playwright__browser_snapshot",
                "mcp__playwright__browser_click",
                "mcp__playwright__browser_hover",
                "mcp__playwright__browser_scroll",
                "mcp__playwright__browser_resize",
                "mcp__playwright__browser_evaluate",
                "mcp__playwright__browser_wait_for",
                "mcp__playwright__browser_console_messages",
                "mcp__playwright__browser_network_requests",
            ] + (
                # GitHub MCP Server tools (if enabled)
                [
                    "mcp__github__create_repository",
                    "mcp__github__create_branch",
                    "mcp__github__push_files",
                    "mcp__github__create_pull_request",
                    "mcp__github__create_or_update_file",
                    "mcp__github__get_file_contents",
                    "mcp__github__list_branches",
                ] if settings.effective_github_token and settings.auto_create_repo else []
            ) + (
                # Vercel MCP Server tools (if enabled)
                [
                    "mcp__vercel__deploy",
                    "mcp__vercel__list_projects",
                    "mcp__vercel__get_project",
                    "mcp__vercel__create_project",
                    "mcp__vercel__list_deployments",
                    "mcp__vercel__get_deployment",
                ] if settings.is_vercel_enabled else []
            ),
            mcp_servers=mcp_servers,
            permission_mode="acceptEdits",
        )
        # Build the conversion prompt
        conversion_prompt = build_conversion_prompt(
            figma_url=figma_url,
            project_name=project_name,
            project_path=str(project_path),
            design_data=design_data,
            downloaded_images=downloaded_images,
            is_new_project=is_new_project,
            ui_library=ui_library,
            design_screenshot_path=str(design_screenshot_path) if design_screenshot_path else "",
        )

        if trace:
            trace.log_conversion_prompt(conversion_prompt)

        # Track results
        components_generated = 0
        components_reused = 0
        component_files_seen = set()  # Track unique component files to avoid double-counting
        files_written = []
        screenshots_taken = 0
        turn_count = 0
        errors = []
        stats = design_data.get("stats", {})
        build_result = None  # Will be set by build-fix loop

        # For pages, snapshot existing components to detect reuse later
        existing_components = set()
        if add_as == "new_page":
            comp_dir = project_path / "src" / "components"
            if comp_dir.exists():
                existing_components = {
                    f.stem for f in comp_dir.iterdir()
                    if f.suffix in (".tsx", ".ts") and f.is_file()
                }

        log.phase("CONVERSION")
        log.info(f"Prompt: {len(conversion_prompt)} chars, model={settings.default_model}, max_turns={settings.max_agent_turns}")

        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(conversion_prompt)

                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        turn_count += 1
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                text_preview = block.text[:200].replace('\n', ' ')
                                log.info(text_preview)
                                if trace:
                                    trace.log_agent_message("assistant", block.text)
                            elif isinstance(block, ToolUseBlock):
                                tool_name = block.name
                                tool_input = block.input if isinstance(block.input, dict) else {}

                                # Rich tool logging with details
                                if tool_name == "Write":
                                    fp = str(tool_input.get("file_path", "") or tool_input.get("path", ""))
                                    short = fp.split("src/")[-1] if "src/" in fp else fp.split("/")[-1]
                                    log.tool(tool_name, short)
                                    files_written.append(short)
                                    # Count unique component files only once
                                    if "/src/components/" in fp and fp.endswith(".tsx"):
                                        comp_name = fp.split("/src/components/")[-1].replace(".tsx", "")
                                        if comp_name not in component_files_seen:
                                            component_files_seen.add(comp_name)
                                            components_generated += 1
                                elif tool_name == "Edit":
                                    fp = str(tool_input.get("file_path", ""))
                                    short = fp.split("src/")[-1] if "src/" in fp else fp.split("/")[-1]
                                    log.tool(tool_name, short)
                                elif tool_name == "Bash":
                                    cmd = str(tool_input.get("command", ""))
                                    log.tool(tool_name, cmd[:80])
                                    # Count component files created via Bash, but only if not already seen
                                    if "/src/components/" in cmd and (".tsx" in cmd or ".ts" in cmd):
                                        # Extract component name from bash command
                                        bash_comp_match = re.search(r'/src/components/(\w+)\.tsx', cmd)
                                        if bash_comp_match:
                                            comp_name = bash_comp_match.group(1)
                                            if comp_name not in component_files_seen:
                                                component_files_seen.add(comp_name)
                                                components_generated += 1
                                elif "screenshot" in tool_name.lower():
                                    screenshots_taken += 1
                                    log.tool(tool_name, f"(screenshot #{screenshots_taken})")
                                elif "navigate" in tool_name.lower():
                                    url = str(tool_input.get("url", ""))
                                    log.tool(tool_name, url)
                                elif "save_component" in tool_name:
                                    comp_name = str(tool_input.get("name", "?"))
                                    comp_cat = str(tool_input.get("category", ""))
                                    log.component_saved(comp_name, comp_cat)
                                    # Don't increment components_generated here - already counted on file Write
                                elif "get_component" in tool_name:
                                    # Actual reuse: agent retrieved a library component to use
                                    comp_id = str(tool_input.get("component_id", ""))
                                    log.tool(tool_name, comp_id)
                                    components_reused += 1
                                elif "search_component" in tool_name:
                                    # Just a search, not actual reuse - only log it
                                    query = str(tool_input.get("query", ""))
                                    log.tool(tool_name, query)
                                elif "resize" in tool_name.lower():
                                    w = tool_input.get("width", "?")
                                    h = tool_input.get("height", "?")
                                    log.tool(tool_name, f"{w}x{h}")
                                else:
                                    log.tool(tool_name)

                                # Trace: log every tool call
                                if trace:
                                    trace.log_tool_call(tool_name, tool_input)

                    elif isinstance(message, ResultMessage):
                        # Capture token usage and cost from the SDK result
                        if trace:
                            usage = getattr(message, "usage", None) or {}
                            if isinstance(usage, dict):
                                trace.log_tokens(
                                    usage.get("input_tokens", 0),
                                    usage.get("output_tokens", 0),
                                )
                            cost = getattr(message, "total_cost_usd", None)
                            if cost is not None:
                                trace.log_event("cost", {"total_cost_usd": cost})
                            trace.log_event("result", {
                                "num_turns": getattr(message, "num_turns", 0),
                                "duration_ms": getattr(message, "duration_ms", 0),
                                "duration_api_ms": getattr(message, "duration_api_ms", 0),
                            })

                        if message.subtype == "error":
                            error_text = getattr(message, "content", None) or getattr(message, "text", None) or str(message)
                            log.error(f"Agent error: {error_text}")
                            errors.append(str(error_text))

                log.info(f"Agent finished: {turn_count} turns, {len(files_written)} files written, {screenshots_taken} screenshots")

                # ── BUILD-FIX LOOP: verify build, feed errors back to agent ──
                if settings.verify_build:
                    max_fix_attempts = 2
                    for fix_attempt in range(max_fix_attempts + 1):
                        log.phase("BUILD")
                        try:
                            build_result = await verify_build(project_path)
                            build_ok = build_result.get("success", False)
                            build_errors = build_result.get("errors", [])

                            if build_ok:
                                log.info("Build succeeded" + (f" (after {fix_attempt} fix{'es' if fix_attempt > 1 else ''})" if fix_attempt > 0 else ""))
                                break

                            # Format error messages for the agent
                            error_lines = []
                            for err in build_errors[:10]:
                                msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                                f_path = err.get("file", "") if isinstance(err, dict) else ""
                                if f_path:
                                    error_lines.append(f"  - {f_path}: {msg}")
                                else:
                                    error_lines.append(f"  - {msg}")
                            error_text = "\n".join(error_lines)

                            if fix_attempt < max_fix_attempts:
                                log.info(f"Build FAILED — sending {len(build_errors)} error(s) to agent (fix {fix_attempt + 1}/{max_fix_attempts})")
                                fix_prompt = (
                                    f"BUILD FAILED with {len(build_errors)} error(s). Fix them NOW:\n\n"
                                    f"{error_text}\n\n"
                                    "Common fixes:\n"
                                    "- \"Cannot find module '../components/X'\" → Create the missing component OR remove the import and use an existing component.\n"
                                    "- \"'React' is declared but its value is never read\" → Remove `import React from 'react'`.\n"
                                    "- Type errors → Fix the TypeScript issue in the indicated file.\n\n"
                                    "Fix ALL errors now."
                                )
                                await client.query(fix_prompt)
                                async for msg in client.receive_response():
                                    if isinstance(msg, AssistantMessage):
                                        turn_count += 1
                                        for block in msg.content:
                                            if isinstance(block, TextBlock):
                                                log.info(block.text[:200].replace('\n', ' '))
                                            elif isinstance(block, ToolUseBlock):
                                                tn = block.name
                                                ti = block.input if isinstance(block.input, dict) else {}
                                                if tn == "Write":
                                                    fp = str(ti.get("file_path", "") or ti.get("path", ""))
                                                    short = fp.split("src/")[-1] if "src/" in fp else fp.split("/")[-1]
                                                    log.tool(tn, short)
                                                    files_written.append(short)
                                                    if "/src/components/" in fp and fp.endswith(".tsx"):
                                                        cn = fp.split("/src/components/")[-1].replace(".tsx", "")
                                                        if cn not in component_files_seen:
                                                            component_files_seen.add(cn)
                                                            components_generated += 1
                                                elif tn == "Edit":
                                                    fp = str(ti.get("file_path", ""))
                                                    short = fp.split("src/")[-1] if "src/" in fp else fp.split("/")[-1]
                                                    log.tool(tn, short)
                                                elif tn == "Bash":
                                                    log.tool(tn, str(ti.get("command", ""))[:80])
                                                else:
                                                    log.tool(tn)
                                    elif isinstance(msg, ResultMessage):
                                        if msg.subtype == "error":
                                            log.error(f"Fix error: {getattr(msg, 'content', None) or str(msg)}")
                            else:
                                log.info(f"Build FAILED after {max_fix_attempts} fix attempts")
                        except Exception as be:
                            log.error(f"Build verification error: {be}")
                            build_result = {"success": False, "error": str(be)}
                            break

            # For pages: detect reuse of parent components by scanning page imports
            if add_as == "new_page" and existing_components:
                pages_dir = project_path / "src" / "pages"
                if pages_dir.exists():
                    for page_file in pages_dir.iterdir():
                        if page_file.suffix == ".tsx" and page_file.is_file():
                            try:
                                content = page_file.read_text(encoding="utf-8")
                                # Find all component imports from ../components/
                                imports = re.findall(
                                    r"import\s+\w+\s+from\s+['\"]\.\.\/components\/(\w+)['\"]",
                                    content
                                )
                                for imp in imports:
                                    if imp in existing_components and imp not in component_files_seen:
                                        components_reused += 1
                            except Exception:
                                pass

            # Fallback: if agent wrote components but counts are 0, scan filesystem
            if components_generated == 0:
                comp_dir = project_path / "src" / "components"
                if comp_dir.exists():
                    all_comps = {
                        f.stem for f in comp_dir.iterdir()
                        if f.suffix in (".tsx", ".ts") and f.is_file()
                    }
                    new_comps = all_comps - existing_components
                    reused_from_parent = all_comps & existing_components if existing_components else set()
                    components_generated = len(new_comps) if add_as == "new_page" else len(all_comps)
                    if add_as == "new_page" and components_reused == 0:
                        components_reused = len(reused_from_parent)

            # For standalone projects: detect library reuse by checking component names
            # against existing library entries (if get_component wasn't called explicitly)
            if components_reused == 0 and not is_new_project:
                try:
                    from backend.rag.component_store import ComponentStore
                    from backend.config import settings as app_settings
                    persist_dir = app_settings.component_library_dir / "chroma"
                    if persist_dir.exists():
                        lib_store = ComponentStore(persist_directory=str(persist_dir))
                        lib_names = set()
                        try:
                            all_items = lib_store.collection.get()
                            for meta in (all_items.get("metadatas") or []):
                                if meta and "name" in meta:
                                    lib_names.add(meta["name"])
                        except Exception:
                            pass
                        if lib_names:
                            comp_dir = project_path / "src" / "components"
                            if comp_dir.exists():
                                project_comps = {
                                    f.stem for f in comp_dir.iterdir()
                                    if f.suffix in (".tsx", ".ts") and f.is_file()
                                }
                                matched = project_comps & lib_names
                                components_reused = len(matched)
                except Exception:
                    pass  # Don't fail conversion if library check fails

            elapsed_time = time.time() - start_time

            # Collect reuse stats from the component library
            reuse_stats = {
                "reused": components_reused,
                "adapted": 0,
                "created_new": components_generated,
                "library_size": 0,
            }
            try:
                from backend.rag.component_store import get_component_store
                lib_store = get_component_store()
                lib_stats = lib_store.get_reuse_stats()
                reuse_stats["library_size"] = lib_stats.get("total_components", 0)
            except Exception:
                pass

            # Finalise and save trace
            if trace:
                trace.finish(
                    status="success" if not errors else "completed_with_errors",
                    error=errors[0] if errors else None,
                )
                try:
                    trace.save(project_path)
                except Exception as te:
                    _logger.warning(f"Failed to save conversion trace: {te}")

            result = {
                "status": "success" if not errors else "completed_with_errors",
                "project_path": str(project_path),
                "components_generated": components_generated,
                "components_reused": components_reused,
                "conversion_time_seconds": elapsed_time,
                "design_stats": stats,
                "images_downloaded": len(downloaded_images),
                "errors": errors if errors else None,
                "reuse_stats": reuse_stats,
            }

            # Attach trace summary to result
            if trace:
                result["trace_summary"] = trace.summary()

            # Run code quality checks if enabled
            if settings.auto_run_lint or settings.auto_run_format:
                log.phase("QUALITY")
                try:
                    quality_results = await run_all_quality_checks(
                        project_path,
                        auto_fix=settings.auto_fix_lint
                    )
                    result["code_quality"] = {
                        "eslint": quality_results.get("eslint"),
                        "prettier": quality_results.get("prettier"),
                        "overall_success": quality_results.get("overall_success"),
                    }
                    log.info(f"Quality checks complete — success={quality_results.get('overall_success')}")
                except Exception as qe:
                    log.error(f"Quality checks failed: {qe}")
                    result["code_quality"] = {"error": str(qe)}

            # Add build verification result from the build-fix loop (ran inside agent session)
            if settings.verify_build and build_result is not None:
                result["build_verification"] = {
                    "success": build_result.get("success") if isinstance(build_result, dict) else False,
                    "errors": build_result.get("errors", []) if isinstance(build_result, dict) else [],
                    "bundle_size": build_result.get("bundle_size") if isinstance(build_result, dict) else None,
                    "duration": build_result.get("duration") if isinstance(build_result, dict) else None,
                }

            # Visual verification loop (runs after build is confirmed)
            if settings.enable_vision_comparison or settings.enable_structural_comparison:
                log.phase("VERIFICATION")
                try:
                    # Derive file key from URL for element-level Figma export
                    _fk = ""
                    if figma_url and not figma_url.startswith("plugin://"):
                        from backend.agents._figma_to_react.figma_extraction import extract_figma_file_key
                        _fk = extract_figma_file_key(figma_url) or ""

                    verification_result = await visual_verification_loop(
                        project_path=project_path,
                        design_data=design_data,
                        figma_url=figma_url if (figma_url and not figma_url.startswith("plugin://")) else None,
                        figma_screenshot_path=design_screenshot_path,
                        figma_token=self.figma_token,
                        file_key=_fk,
                    )

                    v_confidence = verification_result.get("confidence", 0.0)
                    v_iterations = verification_result.get("iterations", 0)
                    v_status = verification_result.get("status", "failed")

                    result["visual_match"] = v_confidence >= settings.verification_confidence_threshold
                    result["verification_confidence"] = round(v_confidence, 4)
                    result["verification_iterations"] = v_iterations

                    # Collect discrepancies from the final iteration
                    history = verification_result.get("history", [])
                    result["visual_discrepancies"] = (
                        history[-1].get("discrepancies", []) if history else []
                    )

                    # Full verification report (element summaries, score breakdown)
                    result["visual_verification"] = {
                        "status": v_status,
                        "confidence": v_confidence,
                        "iterations": v_iterations,
                        "final_scores": verification_result.get("final_scores", {}),
                        "element_comparison": verification_result.get("element_comparison", {}),
                    }

                    log.info(
                        f"Verification: {v_status} "
                        f"(confidence={v_confidence:.2%}, iterations={v_iterations})"
                    )
                except Exception as ve:
                    log.error(f"Verification loop failed: {ve}")
                    result.setdefault("visual_match", False)
                    result.setdefault("verification_confidence", 0.0)
                    result.setdefault("verification_iterations", 0)
                    result.setdefault("visual_discrepancies", [])
            else:
                result.setdefault("visual_match", False)
                result.setdefault("verification_confidence", 0.0)
                result.setdefault("verification_iterations", 0)
                result.setdefault("visual_discrepancies", [])

            # Git integration is handled by GitHub MCP Server
            if is_github_enabled():
                result["git"] = {
                    "enabled": True,
                    "note": "GitHub MCP tools available for repo creation and push",
                }
                log.info("GitHub MCP integration enabled")

            return result

        except Exception as e:
            elapsed_time = time.time() - start_time
            if trace:
                trace.finish(status="failed", error=str(e))
                try:
                    trace.save(project_path)
                except Exception:
                    pass
            return {
                "status": "failed",
                "project_path": str(project_path),
                "components_generated": components_generated,
                "components_reused": components_reused,
                "conversion_time_seconds": elapsed_time,
                "errors": [str(e)],
                **({"trace_summary": trace.summary()} if trace else {}),
            }
