"""Figma design data extraction utilities."""

from .design_styles import (
    extract_text_style,
    extract_layout_info,
    extract_effects,
    extract_fills,
    extract_strokes,
    extract_corner_radius,
    extract_design_tokens,
    rgba_to_hex,
)

from typing import Dict, Optional


def extract_figma_file_key(figma_url: str) -> str:
    """Extract file key from Figma URL."""
    # Handle various Figma URL formats
    # https://www.figma.com/file/ABC123/Name
    # https://www.figma.com/design/ABC123/Name
    parts = figma_url.split("/")
    for i, part in enumerate(parts):
        if part in ("file", "design") and i + 1 < len(parts):
            return parts[i + 1].split("?")[0]
    return ""


def extract_node_data(
    node: dict,
    depth: int = 0,
    file_styles: Optional[Dict[str, dict]] = None,
) -> dict:
    """Extract complete data from a single Figma node."""
    node_type = node.get("type", "")

    data = {
        "id": node.get("id"),
        "name": node.get("name", ""),
        "type": node_type,
        "visible": node.get("visible", True),
    }

    # Add opacity if not default
    if node.get("opacity") is not None and node.get("opacity") != 1:
        data["opacity"] = node["opacity"]

    # Design token references (Figma Variables + named Styles)
    tokens = extract_design_tokens(node, file_styles)
    if tokens:
        data["designTokens"] = tokens

    # Extract type-specific data
    if node_type == "TEXT":
        data["text"] = node.get("characters", "")
        data["style"] = extract_text_style(node)
        data["fills"] = extract_fills(node)

    elif node_type in ("FRAME", "GROUP", "COMPONENT", "INSTANCE", "SECTION"):
        data["layout"] = extract_layout_info(node)
        data["fills"] = extract_fills(node)
        data["strokes"] = extract_strokes(node)
        data["effects"] = extract_effects(node)
        data["cornerRadius"] = extract_corner_radius(node)
        data["clipsContent"] = node.get("clipsContent", False)

        # Recursively process children
        if node.get("children"):
            data["children"] = [
                extract_node_data(child, depth + 1, file_styles=file_styles)
                for child in node["children"]
                if child.get("visible", True)
            ]

    elif node_type == "RECTANGLE":
        data["layout"] = extract_layout_info(node)
        data["fills"] = extract_fills(node)
        data["strokes"] = extract_strokes(node)
        data["effects"] = extract_effects(node)
        data["cornerRadius"] = extract_corner_radius(node)

    elif node_type == "VECTOR":
        data["fills"] = extract_fills(node)
        data["strokes"] = extract_strokes(node)
        data["layout"] = extract_layout_info(node)

    elif node_type == "ELLIPSE":
        data["fills"] = extract_fills(node)
        data["strokes"] = extract_strokes(node)
        data["layout"] = extract_layout_info(node)

    elif node_type == "LINE":
        data["strokes"] = extract_strokes(node)
        data["layout"] = extract_layout_info(node)

    return data


def collect_image_refs(node: dict, refs: dict) -> None:
    """Recursively collect all image references with node IDs from a node tree.

    Args:
        node: Figma node dictionary
        refs: Dict mapping imageRef (hash) to node ID
    """
    # Check fills for images
    for fill in node.get("fills", []):
        if fill.get("type") == "IMAGE" and fill.get("imageRef"):
            image_ref = fill["imageRef"]
            node_id = node.get("id")
            if node_id and image_ref not in refs:
                # Store the first node ID for each image ref
                refs[image_ref] = node_id

    # Recurse into children
    for child in node.get("children", []):
        collect_image_refs(child, refs)


def collect_colors_and_fonts(node: dict, colors: dict, fonts: dict) -> None:
    """Recursively collect all colors and fonts from a node tree."""
    # Collect colors from fills
    for fill in node.get("fills", []):
        if fill.get("type") == "SOLID" and fill.get("color"):
            hex_color = rgba_to_hex(fill["color"], fill.get("opacity", 1))
            context = f"{node.get('type', 'unknown')}:{node.get('name', 'unnamed')}"
            if hex_color not in colors:
                colors[hex_color] = {"count": 0, "contexts": []}
            colors[hex_color]["count"] += 1
            if len(colors[hex_color]["contexts"]) < 3:
                colors[hex_color]["contexts"].append(context)

    # Collect colors from strokes
    for stroke in node.get("strokes", []):
        if stroke.get("type") == "SOLID" and stroke.get("color"):
            hex_color = rgba_to_hex(stroke["color"], stroke.get("opacity", 1))
            context = f"stroke:{node.get('name', 'unnamed')}"
            if hex_color not in colors:
                colors[hex_color] = {"count": 0, "contexts": []}
            colors[hex_color]["count"] += 1
            if len(colors[hex_color]["contexts"]) < 3:
                colors[hex_color]["contexts"].append(context)

    # Collect fonts from text nodes
    if node.get("type") == "TEXT":
        style = node.get("style", {})
        font_family = style.get("fontFamily", "Inter")
        font_weight = style.get("fontWeight", 400)

        if font_family not in fonts:
            fonts[font_family] = {"weights": set(), "usages": 0}
        fonts[font_family]["weights"].add(font_weight)
        fonts[font_family]["usages"] += 1

    # Recurse into children
    for child in node.get("children", []):
        collect_colors_and_fonts(child, colors, fonts)


def extract_complete_design_data(figma_data: dict) -> dict:
    """Extract complete design data for pixel-perfect recreation.

    This extracts ALL data needed to recreate the Figma design:
    - Complete node hierarchy with exact properties
    - All text content verbatim
    - All fonts with exact weights
    - All colors with usage context
    - Layout info (auto-layout → flex mappings)
    - Image references for download

    Args:
        figma_data: Raw Figma API response

    Returns:
        Structured design data dict or error dict
    """
    if "error" in figma_data:
        return {"error": figma_data["error"]}

    try:
        document = figma_data.get("document", {})
        name = figma_data.get("name", "Unknown")
        version = figma_data.get("version", "")

        # File-level named styles (resolve style IDs → names in nodes)
        file_styles: Dict[str, dict] = figma_data.get("styles", {})

        # Extract pages with their frames
        pages = []
        all_colors = {}
        all_fonts = {}
        all_image_refs = {}  # Dict mapping imageRef to node ID

        for page in document.get("children", []):
            if page.get("type") != "CANVAS":
                continue

            page_data = {
                "id": page.get("id"),
                "name": page.get("name", "Page"),
                "frames": [],
            }

            # Extract top-level frames from this page
            for frame in page.get("children", []):
                if not frame.get("visible", True):
                    continue

                # Extract complete frame data (pass file_styles for token resolution)
                frame_data = extract_node_data(frame, file_styles=file_styles)
                page_data["frames"].append(frame_data)

                # Collect colors and fonts from this frame
                collect_colors_and_fonts(frame, all_colors, all_fonts)

                # Collect image references
                collect_image_refs(frame, all_image_refs)

            pages.append(page_data)

        # Process fonts to make them JSON serializable
        fonts_list = []
        for family, data in all_fonts.items():
            fonts_list.append({
                "family": family,
                "weights": sorted(list(data["weights"])),
                "usages": data["usages"],
            })

        # Sort colors by usage count
        colors_list = sorted(
            [{"color": c, **data} for c, data in all_colors.items()],
            key=lambda x: x["count"],
            reverse=True
        )

        return {
            "name": name,
            "version": version,
            "pages": pages,
            "colors": colors_list,
            "fonts": fonts_list,
            "imageRefs": all_image_refs,  # Dict mapping imageRef to node ID
            "stats": {
                "pageCount": len(pages),
                "frameCount": sum(len(p["frames"]) for p in pages),
                "colorCount": len(colors_list),
                "fontCount": len(fonts_list),
                "imageCount": len(all_image_refs),
            }
        }

    except Exception as e:
        return {"error": f"Error parsing Figma data: {str(e)}"}
