"""Project initialization and configuration utilities."""

import os
import shutil
from pathlib import Path

from backend.config import settings


def configure_litellm():
    """Configure environment variables to use LiteLLM proxy."""
    os.environ["ANTHROPIC_BASE_URL"] = settings.litellm_base_url
    os.environ["ANTHROPIC_API_KEY"] = settings.litellm_api_key
    os.environ["OPENAI_API_BASE"] = settings.litellm_base_url
    os.environ["OPENAI_API_KEY"] = settings.litellm_api_key


def setup_project_from_template(project_name: str, output_dir: Path, ui_library: str = "tailwind") -> Path:
    """Copy template and set up project directory based on UI library."""
    # Map UI library to template directory
    template_map = {
        "tailwind": "react-tailwind",
        "mui": "react-mui",
        "chakra": "react-chakra",
        "css-modules": "react-css-modules",
    }
    template_name = template_map.get(ui_library, "react-tailwind")
    template_dir = Path(__file__).parent.parent.parent.parent / "templates" / template_name

    # Fallback to tailwind template if specific template doesn't exist
    if not template_dir.exists():
        template_dir = Path(__file__).parent.parent.parent.parent / "templates" / "react-tailwind"

    project_path = output_dir / project_name

    # Remove existing project if exists
    if project_path.exists():
        shutil.rmtree(project_path)

    # Copy template
    shutil.copytree(template_dir, project_path, ignore=shutil.ignore_patterns('.gitkeep'))

    # Replace placeholders in package.json and index.html
    for file_name in ["package.json", "index.html"]:
        file_path = project_path / file_name
        if file_path.exists():
            content = file_path.read_text()
            content = content.replace("{{PROJECT_NAME}}", project_name)
            file_path.write_text(content)

    return project_path
