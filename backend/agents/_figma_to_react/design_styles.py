"""Color and style extraction utilities for Figma designs."""

from typing import Dict, Optional


def rgba_to_hex(color: dict, opacity: float = 1.0) -> str:
    """Convert Figma RGBA color to hex string."""
    r = int(color.get("r", 0) * 255)
    g = int(color.get("g", 0) * 255)
    b = int(color.get("b", 0) * 255)
    a = color.get("a", 1.0) * opacity
    if a < 1.0:
        return f"rgba({r}, {g}, {b}, {a:.2f})"
    return f"#{r:02x}{g:02x}{b:02x}"


def extract_text_style(node: dict) -> dict:
    """Extract text styling from a TEXT node."""
    style = node.get("style", {})
    return {
        "fontFamily": style.get("fontFamily", "Inter"),
        "fontSize": style.get("fontSize", 16),
        "fontWeight": style.get("fontWeight", 400),
        "lineHeight": style.get("lineHeightPx"),
        "letterSpacing": style.get("letterSpacing", 0),
        "textAlignHorizontal": style.get("textAlignHorizontal", "LEFT"),
        "textAlignVertical": style.get("textAlignVertical", "TOP"),
        "textCase": style.get("textCase", "ORIGINAL"),
        "textDecoration": style.get("textDecoration", "NONE"),
    }


def extract_layout_info(node: dict) -> dict:
    """Extract comprehensive auto-layout and positioning information."""
    layout = {}

    # Auto-layout (maps to flexbox)
    if node.get("layoutMode"):
        layout["mode"] = node["layoutMode"]  # HORIZONTAL or VERTICAL
        layout["primaryAxisSizingMode"] = node.get("primaryAxisSizingMode", "AUTO")
        layout["counterAxisSizingMode"] = node.get("counterAxisSizingMode", "AUTO")
        layout["primaryAxisAlignItems"] = node.get("primaryAxisAlignItems", "MIN")
        layout["counterAxisAlignItems"] = node.get("counterAxisAlignItems", "MIN")
        layout["itemSpacing"] = node.get("itemSpacing", 0)
        layout["counterAxisSpacing"] = node.get("counterAxisSpacing")

        # Flex properties
        layout["layoutGrow"] = node.get("layoutGrow", 0)  # flex-grow
        layout["layoutAlign"] = node.get("layoutAlign", "INHERIT")  # flex item alignment

        # Padding
        layout["padding"] = {
            "top": node.get("paddingTop", 0),
            "right": node.get("paddingRight", 0),
            "bottom": node.get("paddingBottom", 0),
            "left": node.get("paddingLeft", 0),
        }

    # Sizing constraints
    sizing = {}
    if node.get("absoluteBoundingBox"):
        bbox = node["absoluteBoundingBox"]
        sizing["width"] = bbox.get("width", 0)
        sizing["height"] = bbox.get("height", 0)

    # Min/Max constraints
    if node.get("minWidth"):
        sizing["minWidth"] = node["minWidth"]
    if node.get("maxWidth"):
        sizing["maxWidth"] = node["maxWidth"]
    if node.get("minHeight"):
        sizing["minHeight"] = node["minHeight"]
    if node.get("maxHeight"):
        sizing["maxHeight"] = node["maxHeight"]

    if sizing:
        layout["sizing"] = sizing

    # Constraints (for absolute positioning and responsive behavior)
    constraints = node.get("constraints", {})
    if constraints:
        layout["constraints"] = {
            "horizontal": constraints.get("horizontal", "LEFT"),  # LEFT, RIGHT, CENTER, SCALE, STRETCH
            "vertical": constraints.get("vertical", "TOP"),  # TOP, BOTTOM, CENTER, SCALE, STRETCH
        }

    # Position (absolute coordinates)
    if node.get("absoluteBoundingBox"):
        bbox = node["absoluteBoundingBox"]
        layout["position"] = {
            "x": bbox.get("x", 0),
            "y": bbox.get("y", 0),
        }

        # Relative position (if parent exists)
        if node.get("relativeTransform"):
            transform = node["relativeTransform"]
            if len(transform) >= 2:
                layout["relativePosition"] = {
                    "x": transform[0][2] if len(transform[0]) > 2 else 0,
                    "y": transform[1][2] if len(transform[1]) > 2 else 0,
                }

    # Absolute bounds (full bounding box)
    if node.get("absoluteBoundingBox"):
        bbox = node["absoluteBoundingBox"]
        layout["bounds"] = {
            "x": bbox.get("x", 0),
            "y": bbox.get("y", 0),
            "width": bbox.get("width", 0),
            "height": bbox.get("height", 0),
        }

    # Layer ordering (for z-index)
    layout["zIndex"] = node.get("zIndex", 0)

    # Clipping and overflow
    layout["clipsContent"] = node.get("clipsContent", False)
    layout["overflow"] = "hidden" if node.get("clipsContent") else "visible"

    return layout


def extract_effects(node: dict) -> list:
    """Extract effects (shadows, blur, etc.) with CSS mapping."""
    effects = []
    for effect in node.get("effects", []):
        if not effect.get("visible", True):
            continue

        effect_type = effect.get("type")
        effect_data = {"type": effect_type}

        if effect_type in ("DROP_SHADOW", "INNER_SHADOW"):
            color = effect.get("color", {})
            offset_x = effect.get("offset", {}).get("x", 0)
            offset_y = effect.get("offset", {}).get("y", 0)
            radius = effect.get("radius", 0)
            spread = effect.get("spread", 0)
            color_str = rgba_to_hex(color, color.get("a", 1))

            effect_data.update({
                "color": color_str,
                "offset": {
                    "x": offset_x,
                    "y": offset_y,
                },
                "radius": radius,
                "spread": spread,
            })

            # CSS box-shadow format
            shadow_type = "inset " if effect_type == "INNER_SHADOW" else ""
            effect_data["css"] = f"{shadow_type}{offset_x}px {offset_y}px {radius}px {spread}px {color_str}"

            # Tailwind shadow class (approximation)
            if abs(offset_y) <= 2 and radius <= 4:
                effect_data["tailwind"] = "shadow-sm"
            elif abs(offset_y) <= 6 and radius <= 10:
                effect_data["tailwind"] = "shadow"
            elif abs(offset_y) <= 15 and radius <= 20:
                effect_data["tailwind"] = "shadow-lg"
            else:
                effect_data["tailwind"] = f"shadow-[{offset_x}px_{offset_y}px_{radius}px_{spread}px_{color_str}]"

        elif effect_type == "LAYER_BLUR":
            radius = effect.get("radius", 0)
            effect_data["radius"] = radius
            effect_data["css"] = f"filter: blur({radius}px)"

        elif effect_type == "BACKGROUND_BLUR":
            radius = effect.get("radius", 0)
            effect_data["radius"] = radius
            effect_data["css"] = f"backdrop-filter: blur({radius}px)"

        effects.append(effect_data)

    return effects


def extract_fills(node: dict) -> list:
    """Extract fill colors and gradients."""
    fills = []
    for fill in node.get("fills", []):
        if not fill.get("visible", True):
            continue

        fill_data = {"type": fill.get("type")}

        if fill["type"] == "SOLID":
            fill_data["color"] = rgba_to_hex(
                fill.get("color", {}),
                fill.get("opacity", 1)
            )
        elif fill["type"] in ("GRADIENT_LINEAR", "GRADIENT_RADIAL", "GRADIENT_ANGULAR"):
            stops = []
            for stop in fill.get("gradientStops", []):
                stops.append({
                    "color": rgba_to_hex(stop.get("color", {})),
                    "position": stop.get("position", 0),
                })
            fill_data["gradientStops"] = stops
            fill_data["gradientHandlePositions"] = fill.get("gradientHandlePositions", [])

            # Calculate gradient angle for linear gradients
            if fill["type"] == "GRADIENT_LINEAR" and len(fill_data["gradientHandlePositions"]) >= 2:
                handle_positions = fill_data["gradientHandlePositions"]
                start = handle_positions[0]
                end = handle_positions[1]

                # Calculate angle from handle positions
                import math
                dx = end.get("x", 1) - start.get("x", 0)
                dy = end.get("y", 1) - start.get("y", 0)
                angle_rad = math.atan2(dy, dx)
                angle_deg = (angle_rad * 180 / math.pi) + 90  # Adjust for CSS convention
                fill_data["angle"] = angle_deg

                # CSS linear-gradient
                stop_strings = [f"{stop['color']} {int(stop['position'] * 100)}%" for stop in stops]
                fill_data["css"] = f"linear-gradient({angle_deg:.0f}deg, {', '.join(stop_strings)})"
            elif fill["type"] == "GRADIENT_RADIAL":
                stop_strings = [f"{stop['color']} {int(stop['position'] * 100)}%" for stop in stops]
                fill_data["css"] = f"radial-gradient(circle, {', '.join(stop_strings)})"
        elif fill["type"] == "IMAGE":
            fill_data["imageRef"] = fill.get("imageRef")
            fill_data["scaleMode"] = fill.get("scaleMode", "FILL")

        fills.append(fill_data)

    return fills


def extract_strokes(node: dict) -> list:
    """Extract stroke/border information as a list of stroke objects."""
    strokes = []
    for stroke in node.get("strokes", []):
        if not stroke.get("visible", True):
            continue

        if stroke.get("type") == "SOLID":
            strokes.append({
                "color": rgba_to_hex(stroke.get("color", {}), stroke.get("opacity", 1)),
                "weight": node.get("strokeWeight", 0),
                "align": node.get("strokeAlign", "INSIDE"),
            })

    return strokes


def extract_corner_radius(node: dict) -> dict:
    """Extract corner radius values."""
    if node.get("cornerRadius"):
        return {"all": node["cornerRadius"]}

    if any(node.get(f"rectangle{corner}Radius") for corner in ["TopLeft", "TopRight", "BottomLeft", "BottomRight"]):
        return {
            "topLeft": node.get("rectangleTopLeftRadius", 0),
            "topRight": node.get("rectangleTopRightRadius", 0),
            "bottomLeft": node.get("rectangleBottomLeftRadius", 0),
            "bottomRight": node.get("rectangleBottomRightRadius", 0),
        }

    return {}


# ---------------------------------------------------------------------------
# Figma Variables / Design Token extraction
# ---------------------------------------------------------------------------

def extract_design_tokens(
    node: dict,
    file_styles: Optional[Dict[str, dict]] = None,
) -> Dict[str, str]:
    """Extract design token references from a Figma node.

    Figma nodes may carry two kinds of token reference:
      1. ``boundVariables`` — links properties to Figma Variables
         (e.g. ``{"fills": [{"id": "VariableID:123", "type": "VARIABLE_ALIAS"}]}``)
      2. ``styles`` — links properties to named shared Styles
         (e.g. ``{"fill": "S:abcdef", "text": "S:ghijkl"}``)

    We resolve these into human-readable token names wherever possible.

    Args:
        node: The raw Figma node dict (before our own extraction).
        file_styles: The top-level ``figma_data["styles"]`` map that maps
                     style IDs to ``{"key", "name", "styleType", "description"}``.

    Returns:
        Dict mapping semantic property names to token names.
        Example: ``{"fill": "Primary/600", "text": "Heading/LG", "itemSpacing": "spacing/md"}``
    """
    file_styles = file_styles or {}
    tokens: Dict[str, str] = {}

    # 1. Resolve boundVariables
    bound_vars = node.get("boundVariables", {})
    for prop, binding in bound_vars.items():
        # binding can be a single dict or a list of dicts
        bindings = binding if isinstance(binding, list) else [binding]
        for b in bindings:
            if not isinstance(b, dict):
                continue
            var_id = b.get("id", "")
            var_type = b.get("type", "")
            if var_id:
                # Best effort: use the ID as a label; the actual variable name
                # requires a separate /v1/files/{key}/variables/local call which
                # we may not have here. Store the raw ID so downstream code can
                # detect that a token was used.
                tokens[prop] = var_id

    # 2. Resolve named styles
    style_refs = node.get("styles", {})
    for style_type, style_id in style_refs.items():
        # style_type is one of: "fill", "text", "effect", "grid", "stroke"
        style_meta = file_styles.get(style_id, {})
        style_name = style_meta.get("name", "")
        if style_name:
            tokens[style_type] = style_name
        elif style_id:
            tokens[style_type] = f"style:{style_id}"

    return tokens
