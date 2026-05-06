"""Persist raw Figma JSON and extracted design data to disk for debugging and API exposure."""

import json
from datetime import datetime, timezone
from pathlib import Path


def save_figma_json(
    project_path: Path,
    raw_data: dict,
    design_data: dict,
    source: str,
    file_key: str = "",
) -> Path:
    """Save Figma JSON data to the project's figma_data directory.

    Args:
        project_path: Root path of the generated project.
        raw_data: The raw Figma REST API response or plugin payload.
        design_data: The extracted/normalised design data dict.
        source: Either "api" or "plugin".
        file_key: Figma file key (only meaningful for the API path).

    Returns:
        The figma_data directory path.
    """
    figma_data_dir = project_path / "figma_data"
    figma_data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Raw Figma response
    _write_json(figma_data_dir / "raw_figma_response.json", raw_data)

    # 2. Extracted design data
    _write_json(figma_data_dir / "design_data.json", design_data)

    # 3. Metadata
    stats = design_data.get("stats", {})
    metadata = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "file_key": file_key,
        "stats": stats,
    }
    _write_json(figma_data_dir / "design_metadata.json", metadata)

    return figma_data_dir


def _write_json(path: Path, data: dict) -> None:
    """Write a dict to a JSON file, handling large payloads gracefully."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
