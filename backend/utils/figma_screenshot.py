"""Figma design screenshot export using Figma REST API."""

import asyncio
import base64
from pathlib import Path
from typing import Dict, List, Optional
import httpx
from backend.config import settings


async def export_figma_design_image(
    file_key: str,
    node_ids: List[str],
    figma_token: str,
    output_dir: Path,
    scale: int = 2,
    format: str = "png",
) -> Dict[str, Path]:
    """
    Export Figma designs as PNG images using Figma REST API.

    Uses: GET https://api.figma.com/v1/images/:file_key

    Args:
        file_key: Figma file key from URL
        node_ids: List of node IDs to export
        figma_token: Figma personal access token
        output_dir: Directory to save exported images
        scale: Image scale (1-4, default 2 for retina)
        format: Image format (png, jpg, svg, pdf)

    Returns:
        Dict mapping node_id to local PNG path
    """
    print(f"[Figma Export] Exporting {len(node_ids)} nodes from file {file_key}...", flush=True)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Build API request
    base_url = "https://api.figma.com/v1/images"
    url = f"{base_url}/{file_key}"

    params = {
        "ids": ",".join(node_ids),
        "scale": str(scale),
        "format": format,
    }

    headers = {
        "X-Figma-Token": figma_token,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Request image export
            print(f"[Figma Export] Requesting image URLs from Figma API...", flush=True)
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()

            data = response.json()

            if data.get("err"):
                print(f"[Figma Export] Figma API error: {data['err']}", flush=True)
                return {}

            image_urls = data.get("images", {})

            if not image_urls:
                print("[Figma Export] No images returned from Figma API", flush=True)
                return {}

            print(f"[Figma Export] Received {len(image_urls)} image URLs", flush=True)

            # Download images
            result = {}
            for node_id, image_url in image_urls.items():
                if not image_url:
                    print(f"[Figma Export] No URL for node {node_id}", flush=True)
                    continue

                # Download image
                print(f"[Figma Export] Downloading image for node {node_id}...", flush=True)
                image_response = await client.get(image_url)
                image_response.raise_for_status()

                # Save to file
                output_path = output_dir / f"figma_design_{node_id}.{format}"
                output_path.write_bytes(image_response.content)

                print(f"[Figma Export] Saved to {output_path}", flush=True)
                result[node_id] = output_path

            return result

    except httpx.HTTPStatusError as e:
        print(f"[Figma Export] HTTP error: {e.response.status_code} - {e.response.text}", flush=True)
        return {}
    except Exception as e:
        print(f"[Figma Export] Error exporting Figma images: {e}", flush=True)
        return {}


async def get_figma_file_nodes(file_key: str, figma_token: str) -> List[Dict]:
    """
    Get all frame nodes from a Figma file.

    Uses: GET https://api.figma.com/v1/files/:file_key

    Args:
        file_key: Figma file key
        figma_token: Figma personal access token

    Returns:
        List of frame nodes with their IDs and names
    """
    url = f"https://api.figma.com/v1/files/{file_key}"
    headers = {"X-Figma-Token": figma_token}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            document = data.get("document", {})

            # Extract frame nodes
            frames = []
            _extract_frames(document, frames)

            print(f"[Figma Export] Found {len(frames)} frames in file", flush=True)
            return frames

    except Exception as e:
        print(f"[Figma Export] Error getting Figma file nodes: {e}", flush=True)
        return []


def _extract_frames(node: dict, frames: List[Dict], depth: int = 0):
    """Recursively extract FRAME and COMPONENT nodes from Figma tree."""
    if depth > 10:  # Prevent infinite recursion
        return

    node_type = node.get("type")
    node_id = node.get("id")
    node_name = node.get("name")

    # Collect frames and components
    if node_type in ["FRAME", "COMPONENT", "COMPONENT_SET"]:
        frames.append({
            "id": node_id,
            "name": node_name,
            "type": node_type,
        })

    # Recurse into children
    children = node.get("children", [])
    for child in children:
        _extract_frames(child, frames, depth + 1)


def save_plugin_screenshot(plugin_data: dict, output_dir: Path) -> Optional[Path]:
    """
    Extract and save screenshot from Figma plugin data if available.

    Args:
        plugin_data: Plugin data that may contain design screenshot
        output_dir: Directory to save screenshot

    Returns:
        Path to saved screenshot or None
    """
    # Check if plugin data includes a screenshot
    screenshot_b64 = plugin_data.get("designScreenshot")

    if not screenshot_b64:
        print("[Figma Export] No screenshot in plugin data", flush=True)
        return None

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "figma_design_plugin.png"

        # Decode base64 and save
        screenshot_bytes = base64.b64decode(screenshot_b64)
        output_path.write_bytes(screenshot_bytes)

        print(f"[Figma Export] Saved plugin screenshot to {output_path}", flush=True)
        return output_path

    except Exception as e:
        print(f"[Figma Export] Error saving plugin screenshot: {e}", flush=True)
        return None


async def export_design_screenshot(
    figma_url: Optional[str],
    plugin_data: Optional[dict],
    figma_token: str,
    output_dir: Path,
) -> Optional[Path]:
    """
    Export Figma design screenshot from either URL or plugin data.

    Args:
        figma_url: Figma file URL (if using REST API)
        plugin_data: Plugin data (if using plugin upload)
        figma_token: Figma personal access token
        output_dir: Directory to save screenshot

    Returns:
        Path to design screenshot or None
    """
    # Try plugin screenshot first (faster, no API limit)
    if plugin_data:
        screenshot_path = save_plugin_screenshot(plugin_data, output_dir)
        if screenshot_path:
            return screenshot_path

    # Fall back to Figma REST API
    if not figma_url or not figma_token:
        print("[Figma Export] No Figma URL or token available", flush=True)
        return None

    # Extract file key from URL
    from backend.agents._figma_to_react.figma_extraction import extract_figma_file_key

    file_key = extract_figma_file_key(figma_url)
    if not file_key:
        print("[Figma Export] Could not extract file key from URL", flush=True)
        return None

    # Get all frames in the file
    frames = await get_figma_file_nodes(file_key, figma_token)

    if not frames:
        print("[Figma Export] No frames found in Figma file", flush=True)
        return None

    # Export the first frame (main design)
    # In a multi-page project, this could be smarter
    first_frame = frames[0]
    node_ids = [first_frame["id"]]

    print(f"[Figma Export] Exporting frame: {first_frame['name']}", flush=True)

    result = await export_figma_design_image(
        file_key=file_key,
        node_ids=node_ids,
        figma_token=figma_token,
        output_dir=output_dir,
        scale=1,
        format="png",
    )

    if result:
        # Return path to first exported image
        return list(result.values())[0]

    return None
