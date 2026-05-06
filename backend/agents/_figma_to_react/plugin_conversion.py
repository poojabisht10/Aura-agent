"""Figma plugin data transformation utilities."""

import base64
from pathlib import Path

from .semantic_analysis import infer_semantic_type, get_aria_role


def convert_plugin_data_to_design_data(plugin_data: dict) -> dict:
    """
    Convert plugin data format to the design data format expected by the agent.

    The plugin extracts data in a different format, so we need to transform:
    - layoutMode -> layout.mode
    - paddingLeft/Right/Top/Bottom -> layout.padding
    - absoluteBoundingBox -> layout.bounds
    - fills[].color (RGBA) -> fills[].color (hex string)
    """
    try:
        # Unwrap if nested
        if "pages" not in plugin_data and "design_data" in plugin_data:
            plugin_data = plugin_data["design_data"]

        # Convert colors from dict to list format expected by prompt builder
        colors_dict = plugin_data.get("colors", {})
        colors_list = []
        for hex_color, color_info in colors_dict.items():
            colors_list.append({
                "color": hex_color,
                "count": len(color_info.get("usage", [])),
                "contexts": color_info.get("usage", []),
            })

        # Transform pages and frames to match expected format
        transformed_pages = []
        for page in plugin_data.get("pages", []):
            transformed_frames = []
            for frame in page.get("frames", []):
                transformed_frames.append(transform_plugin_node(frame))
            transformed_pages.append({
                "id": page.get("id", ""),
                "name": page.get("name", ""),
                "frames": transformed_frames,
            })

        result = {
            "name": plugin_data.get("fileName", "Unknown"),
            "pages": transformed_pages,
            "colors": colors_list,
            "fonts": plugin_data.get("fonts", []),
            "imageRefs": {},
            "stats": plugin_data.get("stats", {
                "pageCount": len(plugin_data.get("pages", [])),
                "frameCount": sum(len(p.get("frames", [])) for p in plugin_data.get("pages", [])),
                "colorCount": len(colors_dict),
                "fontCount": len(plugin_data.get("fonts", [])),
                "imageCount": len(plugin_data.get("images", {})),
            }),
        }

        # Preserve design screenshot(s) for visual verification
        if plugin_data.get("designScreenshot"):
            result["designScreenshot"] = plugin_data["designScreenshot"]
        if plugin_data.get("designScreenshots"):
            result["designScreenshots"] = plugin_data["designScreenshots"]

        return result
    except Exception as e:
        return {"error": f"Failed to parse plugin data: {str(e)}"}


def transform_plugin_node(node: dict) -> dict:
    """
    Transform a single plugin node to match the format expected by format_frame_for_prompt.
    Recursively transforms children.
    """
    transformed = {
        "id": node.get("id", ""),
        "name": node.get("name", ""),
        "type": node.get("type", ""),
        "visible": node.get("visible", True),
    }

    # Transform layout info
    plugin_layout = node.get("layout", {})
    bbox = node.get("absoluteBoundingBox", {})

    if plugin_layout or bbox:
        layout = {}

        # Map layoutMode to mode
        if plugin_layout.get("layoutMode"):
            layout["mode"] = plugin_layout["layoutMode"]

        # Map item spacing
        if plugin_layout.get("itemSpacing") is not None:
            layout["itemSpacing"] = plugin_layout["itemSpacing"]

        # Map padding
        padding = {}
        if plugin_layout.get("paddingTop") is not None:
            padding["top"] = plugin_layout["paddingTop"]
        if plugin_layout.get("paddingRight") is not None:
            padding["right"] = plugin_layout["paddingRight"]
        if plugin_layout.get("paddingBottom") is not None:
            padding["bottom"] = plugin_layout["paddingBottom"]
        if plugin_layout.get("paddingLeft") is not None:
            padding["left"] = plugin_layout["paddingLeft"]
        if padding:
            layout["padding"] = padding

        # Map bounds from absoluteBoundingBox or layout width/height
        bounds = {}
        if bbox:
            bounds["width"] = bbox.get("width", 0)
            bounds["height"] = bbox.get("height", 0)
            bounds["x"] = bbox.get("x", 0)
            bounds["y"] = bbox.get("y", 0)
        elif plugin_layout.get("width") is not None or plugin_layout.get("height") is not None:
            bounds["width"] = plugin_layout.get("width", 0)
            bounds["height"] = plugin_layout.get("height", 0)
        if bounds:
            layout["bounds"] = bounds

        if layout:
            transformed["layout"] = layout

    # Transform fills - convert RGBA color objects to hex strings
    if node.get("fills"):
        transformed["fills"] = []
        for fill in node["fills"]:
            transformed_fill = {"type": fill.get("type", "")}
            if fill.get("color"):
                # Convert RGBA {r, g, b, a} to hex string
                c = fill["color"]
                r = int(c.get("r", 0) * 255)
                g = int(c.get("g", 0) * 255)
                b = int(c.get("b", 0) * 255)
                transformed_fill["color"] = f"#{r:02x}{g:02x}{b:02x}"
            if fill.get("imageRef"):
                transformed_fill["imageRef"] = fill["imageRef"]
            if fill.get("gradientStops"):
                transformed_fill["gradientStops"] = fill["gradientStops"]
            transformed["fills"].append(transformed_fill)

    # Transform strokes
    if node.get("strokes"):
        transformed["strokes"] = []
        for stroke in node["strokes"]:
            transformed_stroke = {"type": stroke.get("type", "")}
            if stroke.get("color"):
                c = stroke["color"]
                r = int(c.get("r", 0) * 255)
                g = int(c.get("g", 0) * 255)
                b = int(c.get("b", 0) * 255)
                transformed_stroke["color"] = f"#{r:02x}{g:02x}{b:02x}"
            transformed["strokes"].append(transformed_stroke)

    # Transform effects
    if node.get("effects"):
        transformed["effects"] = []
        for effect in node["effects"]:
            transformed_effect = {
                "type": effect.get("type", ""),
                "visible": effect.get("visible", True),
            }
            if effect.get("radius") is not None:
                transformed_effect["radius"] = effect["radius"]
            if effect.get("offset"):
                transformed_effect["offset"] = effect["offset"]
            if effect.get("color"):
                c = effect["color"]
                r = int(c.get("r", 0) * 255)
                g = int(c.get("g", 0) * 255)
                b = int(c.get("b", 0) * 255)
                a = c.get("a", 1)
                transformed_effect["color"] = f"rgba({r},{g},{b},{a:.2f})"
            transformed["effects"].append(transformed_effect)

    # Pass through corner radius
    if node.get("cornerRadius"):
        transformed["cornerRadius"] = node["cornerRadius"]

    # Pass through text content and style
    if node.get("text"):
        transformed["text"] = node["text"]
    if node.get("style"):
        transformed["style"] = node["style"]

    # Transform children recursively
    if node.get("children"):
        transformed["children"] = [
            transform_plugin_node(child)
            for child in node["children"]
        ]

    # Infer semantic type based on node properties
    semantic_type, suggested_element = infer_semantic_type(transformed)
    transformed["semanticType"] = semantic_type
    transformed["suggestedElement"] = suggested_element

    # Add ARIA role
    aria_role = get_aria_role(semantic_type, transformed)
    if aria_role:
        transformed["ariaRole"] = aria_role

    return transformed


async def save_plugin_images(
    images: dict,
    output_dir: Path,
) -> dict:
    """
    Save base64 encoded images from plugin to disk.

    Args:
        images: Dict mapping imageRef to base64 data URL
        output_dir: Directory to save images

    Returns:
        Dict mapping imageRef to local file path
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_images = {}

    for image_ref, data_url in images.items():
        try:
            # Parse data URL: data:image/png;base64,<data>
            if data_url.startswith("data:"):
                # Extract format and data
                header, encoded = data_url.split(",", 1)
                # Get format from header (e.g., "data:image/png;base64")
                format_str = header.split(";")[0].split("/")[-1]
                if format_str not in ["png", "jpg", "jpeg", "gif", "webp", "svg+xml"]:
                    format_str = "png"
                if format_str == "svg+xml":
                    format_str = "svg"
            else:
                # Assume base64 PNG if no header
                encoded = data_url
                format_str = "png"

            # Decode and save
            image_data = base64.b64decode(encoded)
            filename = f"{image_ref[:20]}.{format_str}"
            filepath = output_dir / filename

            with open(filepath, "wb") as f:
                f.write(image_data)

            saved_images[image_ref] = f"/images/{filename}"

        except Exception as e:
            print(f"[Warning] Failed to save image {image_ref}: {e}")

    return saved_images
