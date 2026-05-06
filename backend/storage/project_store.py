"""JSON-based Project Store - Simple, efficient, no SQL needed."""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
import threading


@dataclass
class Project:
    """Project data model."""
    id: int
    name: str
    figma_url: str
    status: str = "pending"  # pending, generating, success, failed, completed_with_warnings, completed_with_errors
    project_path: Optional[str] = None
    components_generated: int = 0
    components_reused: int = 0
    conversion_time_seconds: Optional[float] = None
    error_message: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Component reuse tracking
    components_adapted: int = 0
    reuse_stats: Optional[Dict[str, Any]] = None

    # Multi-page support
    parent_project_id: Optional[int] = None
    is_page: bool = False
    route_path: Optional[str] = None

    # Visual verification fields
    visual_match: bool = False
    verification_iterations: int = 0
    verification_confidence: float = 0.0
    visual_discrepancies: Optional[List[Dict[str, Any]]] = None

    # GitHub integration fields
    github_repo_url: Optional[str] = None
    github_pushed: bool = False
    github_branch: Optional[str] = None
    github_pr_url: Optional[str] = None

    # Vercel deployment fields
    deployment_status: str = "not_deployed"  # not_deployed, deploying, deployed, failed
    deployment_url: Optional[str] = None
    deployment_error: Optional[str] = None
    last_deployed_at: Optional[str] = None
    vercel_project_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        return cls(**data)


class ProjectStore:
    """
    Simple JSON file-based storage for projects.
    Thread-safe and persistent.
    """

    def __init__(self, storage_path: str = "./data/projects.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._projects: Dict[int, Project] = {}
        self._next_id = 1
        self._load()

    def _load(self):
        """Load projects from JSON file."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._projects = {
                        int(k): Project.from_dict(v)
                        for k, v in data.get("projects", {}).items()
                    }
                    self._next_id = data.get("next_id", 1)
            except (json.JSONDecodeError, KeyError):
                self._projects = {}
                self._next_id = 1

    def _save(self):
        """Save projects to JSON file."""
        data = {
            "projects": {str(k): v.to_dict() for k, v in self._projects.items()},
            "next_id": self._next_id,
        }
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def create(
        self,
        name: str,
        figma_url: str,
        parent_project_id: Optional[int] = None,
        is_page: bool = False,
        route_path: Optional[str] = None,
    ) -> Project:
        """Create a new project or page."""
        with self._lock:
            # Check for duplicate name
            for p in self._projects.values():
                if p.name == name:
                    raise ValueError(f"Project '{name}' already exists")

            project = Project(
                id=self._next_id,
                name=name,
                figma_url=figma_url,
                parent_project_id=parent_project_id,
                is_page=is_page,
                route_path=route_path,
            )
            self._projects[self._next_id] = project
            self._next_id += 1
            self._save()
            return project

    def get(self, project_id: int) -> Optional[Project]:
        """Get a project by ID."""
        return self._projects.get(project_id)

    def get_by_name(self, name: str) -> Optional[Project]:
        """Get a project by name."""
        for p in self._projects.values():
            if p.name == name:
                return p
        return None

    def update(self, project_id: int, **kwargs) -> Optional[Project]:
        """Update a project."""
        with self._lock:
            project = self._projects.get(project_id)
            if not project:
                return None

            for key, value in kwargs.items():
                if hasattr(project, key):
                    setattr(project, key, value)

            project.updated_at = datetime.now().isoformat()
            self._save()
            return project

    def list_all(self, skip: int = 0, limit: int = 100) -> List[Project]:
        """List all projects with pagination."""
        projects = sorted(
            self._projects.values(),
            key=lambda p: p.created_at,
            reverse=True
        )
        return projects[skip:skip + limit]

    def count(self) -> int:
        """Get total number of projects."""
        return len(self._projects)

    def count_projects(self) -> int:
        """Get total number of standalone projects (excludes page records)."""
        return sum(1 for p in self._projects.values() if not p.is_page)

    def count_by_status(self, status: str) -> int:
        """Count standalone projects (not pages) by status."""
        return sum(1 for p in self._projects.values() if p.status == status and not p.is_page)

    def delete(self, project_id: int) -> bool:
        """Delete a project and any child pages that belong to it."""
        with self._lock:
            if project_id not in self._projects:
                return False
            # Cascade: remove all child pages that reference this project
            child_ids = [
                pid for pid, p in self._projects.items()
                if p.parent_project_id == project_id
            ]
            for cid in child_ids:
                del self._projects[cid]
            del self._projects[project_id]
            self._save()
            return True

    def cleanup_orphaned(self) -> List[Project]:
        """
        Remove projects whose project_path doesn't exist on disk.
        Returns list of deleted projects.
        """
        deleted = []
        with self._lock:
            to_delete = []
            for project_id, project in self._projects.items():
                if project.project_path:
                    path = Path(project.project_path)
                    if not path.exists():
                        to_delete.append(project_id)
                        deleted.append(project)

            for project_id in to_delete:
                del self._projects[project_id]

            if to_delete:
                self._save()

        return deleted

    def clear_all(self) -> int:
        """Clear all projects from the store. Returns count of deleted projects."""
        with self._lock:
            count = len(self._projects)
            self._projects = {}
            self._next_id = 1
            self._save()
            return count


# Singleton instance
_store_instance: Optional[ProjectStore] = None


def get_project_store(storage_path: str = "./data/projects.json") -> ProjectStore:
    """Get or create the singleton ProjectStore instance."""
    global _store_instance
    if _store_instance is None:
        _store_instance = ProjectStore(storage_path)
    return _store_instance
