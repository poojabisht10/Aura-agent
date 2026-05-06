"""Figma REST API interaction utilities."""

import httpx
import aiofiles
from pathlib import Path

from backend.utils.figma_rate_limiter import get_rate_limiter


async def fetch_figma_data(file_key: str, figma_token: str) -> dict:
    """Fetch design data from Figma API with extended timeout for large files."""
    if not figma_token:
        return {"error": "No Figma token provided"}

    headers = {"X-Figma-Token": figma_token}
    rate_limiter = get_rate_limiter()

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            # Get file data with geometry to get accurate bounds
            response = await rate_limiter.request_with_retry(
                client=client,
                method="GET",
                url=f"https://api.figma.com/v1/files/{file_key}",
                headers=headers,
                params={"geometry": "paths"},
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return {"error": "Figma file not found. Check the URL and your access permissions."}
            elif response.status_code == 403:
                return {"error": "Access denied. Make sure your Figma token has access to this file."}
            else:
                return {"error": f"Figma API error: {response.status_code} - {response.text}"}
        except httpx.TimeoutException:
            return {"error": "Request timed out. The Figma file may be too large."}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return {"error": "Figma API rate limit hit (10 req/min). Consider using the Figma Plugin instead, which bypasses API rate limits entirely."}
            return {"error": f"Figma API error: {e.response.status_code} - {str(e)}"}
        except Exception as e:
            return {"error": f"Failed to fetch Figma data: {str(e)}"}


async def fetch_figma_image_fills(file_key: str, figma_token: str) -> dict:
    """Fetch image fill metadata from Figma API.

    This endpoint returns metadata about image fills in the file,
    including their image references (content hashes).
    """
    if not figma_token:
        return {"error": "No Figma token provided"}

    headers = {"X-Figma-Token": figma_token}
    rate_limiter = get_rate_limiter()

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # The correct endpoint to get image fill metadata
            response = await rate_limiter.request_with_retry(
                client=client,
                method="GET",
                url=f"https://api.figma.com/v1/files/{file_key}/images",
                headers=headers,
            )

            if response.status_code == 200:
                data = response.json()
                # Figma returns {"err": null, "images": {...}} or {"error": true, "status": 404}
                if data.get("err") or data.get("error"):
                    return {"error": data.get("err") or "Unknown error from Figma"}
                return data
            else:
                return {"error": f"Figma API error: {response.status_code}"}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return {"error": "Figma API rate limit hit (10 req/min). Consider using the Figma Plugin instead, which bypasses API rate limits entirely."}
            return {"error": f"Figma API error: {e.response.status_code} - {str(e)}"}
        except Exception as e:
            return {"error": f"Failed to fetch images metadata: {str(e)}"}


async def download_figma_images(
    file_key: str,
    image_refs_dict: dict,
    figma_token: str,
    output_dir: Path,
) -> dict:
    """Download images from Figma and save to project's public folder.

    Args:
        file_key: Figma file key
        image_refs_dict: Dict mapping image reference hashes to node IDs
        figma_token: Figma API token
        output_dir: Project's public/images directory

    Returns:
        dict mapping image_ref to local file path
    """
    if not image_refs_dict:
        return {}

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    headers = {"X-Figma-Token": figma_token}
    downloaded = {}

    # Get node IDs from the dict
    node_ids = list(image_refs_dict.values())

    if not node_ids:
        return {}

    # Batch export images (Figma API limit is ~50 nodes per request)
    batch_size = 50
    rate_limiter = get_rate_limiter()

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(0, len(node_ids), batch_size):
            batch = node_ids[i:i + batch_size]
            ids_param = ",".join(batch)

            try:
                # Use the Figma images export API with rate limiting
                response = await rate_limiter.request_with_retry(
                    client=client,
                    method="GET",
                    url=f"https://api.figma.com/v1/images/{file_key}",
                    headers=headers,
                    params={
                        "ids": ids_param,
                        "format": "png",
                        "scale": 2,
                    },
                )

                if response.status_code == 200:
                    data = response.json()

                    # Check for API errors
                    if data.get("err"):
                        print(f"[Warning] Figma API error: {data.get('err')}")
                        continue

                    images = data.get("images", {})

                    # Download each image URL
                    for node_id, url in images.items():
                        if url:
                            try:
                                img_response = await client.get(url)
                                if img_response.status_code == 200:
                                    # Find the imageRef for this node_id
                                    image_ref = None
                                    for ref, nid in image_refs_dict.items():
                                        if nid == node_id:
                                            image_ref = ref
                                            break

                                    if not image_ref:
                                        # Use node_id if we can't find the ref
                                        image_ref = node_id.replace(":", "-")

                                    # Determine extension from content type
                                    content_type = img_response.headers.get("content-type", "image/png")
                                    ext = ".png" if "png" in content_type else ".jpg"

                                    filename = f"{image_ref}{ext}"
                                    filepath = output_dir / filename

                                    async with aiofiles.open(filepath, "wb") as f:
                                        await f.write(img_response.content)

                                    downloaded[image_ref] = f"images/{filename}"
                                    print(f"[Image] Downloaded {filename}")
                            except Exception as e:
                                print(f"[Warning] Failed to download image {node_id}: {e}")
                else:
                    print(f"[Warning] Figma images API returned {response.status_code}: {response.text[:200]}")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    print(f"[Warning] Figma API rate limit hit (10 req/min). Consider using the Figma Plugin instead, which bypasses API rate limits entirely. Skipping batch.")
                else:
                    print(f"[Warning] Failed to export batch: {e}")
            except Exception as e:
                print(f"[Warning] Failed to export batch: {e}")

    return downloaded


async def export_figma_node_images(
    file_key: str,
    node_ids: list,
    figma_token: str,
    output_dir: Path,
    format: str = "png",
    scale: float = 2.0,
) -> dict:
    """Export specific Figma nodes as images (for icons, vectors, etc).

    Args:
        file_key: Figma file key
        node_ids: List of node IDs to export
        figma_token: Figma API token
        output_dir: Output directory for images
        format: Image format (png, jpg, svg, pdf)
        scale: Export scale (1-4)

    Returns:
        dict mapping node_id to local file path
    """
    if not node_ids:
        return {}

    output_dir.mkdir(parents=True, exist_ok=True)
    headers = {"X-Figma-Token": figma_token}
    exported = {}

    # Batch node IDs (Figma API limit)
    batch_size = 50
    rate_limiter = get_rate_limiter()

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(0, len(node_ids), batch_size):
            batch = node_ids[i:i + batch_size]
            ids_param = ",".join(batch)

            try:
                # Get image URLs for these nodes with rate limiting
                response = await rate_limiter.request_with_retry(
                    client=client,
                    method="GET",
                    url=f"https://api.figma.com/v1/images/{file_key}",
                    headers=headers,
                    params={
                        "ids": ids_param,
                        "format": format,
                        "scale": scale,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    images = data.get("images", {})

                    # Download each image
                    for node_id, url in images.items():
                        if url:
                            try:
                                img_response = await client.get(url)
                                if img_response.status_code == 200:
                                    safe_name = node_id.replace(":", "-")
                                    filename = f"{safe_name}.{format}"
                                    filepath = output_dir / filename

                                    async with aiofiles.open(filepath, "wb") as f:
                                        await f.write(img_response.content)

                                    exported[node_id] = f"images/{filename}"
                            except Exception as e:
                                print(f"[Warning] Failed to download node {node_id}: {e}")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    print(f"[Warning] Figma API rate limit hit (10 req/min). Consider using the Figma Plugin instead, which bypasses API rate limits entirely. Skipping batch.")
                else:
                    print(f"[Warning] Failed to export batch: {e}")
            except Exception as e:
                print(f"[Warning] Failed to export batch: {e}")

    return exported
