"""Responsive design breakpoint detection and extraction from Figma designs."""

from typing import List, Dict, Any, Optional


# Common viewport sizes
COMMON_VIEWPORTS = {
    "mobile": {"name": "mobile", "maxWidth": 640, "minWidth": 320},
    "tablet": {"name": "tablet", "maxWidth": 1024, "minWidth": 641},
    "desktop": {"name": "desktop", "maxWidth": 1920, "minWidth": 1025},
}


def detect_breakpoints(design_data: dict) -> List[Dict[str, Any]]:
    """
    Analyze frame widths and common viewport sizes to infer breakpoints.

    Args:
        design_data: Complete Figma design data

    Returns:
        List of detected breakpoints:
        [
            {"name": "mobile", "maxWidth": 768},
            {"name": "tablet", "maxWidth": 1024},
            {"name": "desktop", "maxWidth": 1440}
        ]
    """
    breakpoints = []
    frame_widths = set()

    # Collect all unique frame widths
    for frame in design_data.get("frames", []):
        bounds = frame.get("absoluteBoundingBox", {})
        width = bounds.get("width")
        if width:
            frame_widths.add(int(width))

    # Sort widths
    sorted_widths = sorted(frame_widths)

    if not sorted_widths:
        # Return default breakpoints if no frames found
        return [
            {"name": "mobile", "maxWidth": 768, "minWidth": 320},
            {"name": "tablet", "maxWidth": 1024, "minWidth": 769},
            {"name": "desktop", "maxWidth": 1920, "minWidth": 1025},
        ]

    # Detect breakpoints based on frame widths
    # Mobile: smallest frame or default 640px
    mobile_max = min(sorted_widths[0] if sorted_widths else 640, 768)
    breakpoints.append({
        "name": "mobile",
        "maxWidth": mobile_max,
        "minWidth": 320,
        "tailwind": "sm",
    })

    # Tablet: middle range
    if len(sorted_widths) > 1:
        tablet_max = sorted_widths[1] if len(sorted_widths) > 1 else 1024
        breakpoints.append({
            "name": "tablet",
            "maxWidth": min(tablet_max, 1024),
            "minWidth": mobile_max + 1,
            "tailwind": "md",
        })

    # Desktop: largest frame or default
    desktop_width = max(sorted_widths) if sorted_widths else 1440
    breakpoints.append({
        "name": "desktop",
        "maxWidth": max(desktop_width, 1440),
        "minWidth": breakpoints[-1]["maxWidth"] + 1 if breakpoints else 1025,
        "tailwind": "lg",
    })

    return breakpoints


def extract_responsive_constraints(node: dict, parent_width: Optional[int] = None) -> Dict[str, Any]:
    """
    Extract how elements should behave at different screen sizes.

    Args:
        node: Figma node
        parent_width: Parent container width for calculating proportions

    Returns:
        {
            "behavior": "stack_vertical|scale|hide",
            "proportions": {"width": "50%", "height": "auto"},
            "constraints": {"horizontal": "SCALE", "vertical": "MIN"}
        }
    """
    constraints = node.get("constraints", {})
    layout_mode = node.get("layoutMode")
    bounds = node.get("absoluteBoundingBox", {})
    width = bounds.get("width", 0)

    responsive = {
        "constraints": {
            "horizontal": constraints.get("horizontal", "LEFT"),
            "vertical": constraints.get("vertical", "TOP"),
        }
    }

    # Determine responsive behavior based on constraints
    h_constraint = constraints.get("horizontal", "LEFT")
    v_constraint = constraints.get("vertical", "TOP")

    # Horizontal behavior
    if h_constraint == "SCALE":
        responsive["behavior"] = "scale"
        if parent_width and parent_width > 0:
            responsive["proportions"] = {
                "width": f"{(width / parent_width) * 100:.1f}%"
            }
    elif h_constraint == "STRETCH":
        responsive["behavior"] = "stretch"
        responsive["proportions"] = {"width": "100%"}
    elif h_constraint == "CENTER":
        responsive["behavior"] = "center"

    # Auto-layout stacking behavior
    if layout_mode == "HORIZONTAL":
        responsive["stackDirection"] = "row"
        responsive["mobileStack"] = "column"  # Stack vertically on mobile
    elif layout_mode == "VERTICAL":
        responsive["stackDirection"] = "column"

    # Visibility hints (based on size)
    if width < 50:  # Very small elements might be decorative
        responsive["hideOnMobile"] = True

    return responsive


def generate_tailwind_breakpoints(breakpoints: List[Dict[str, Any]]) -> str:
    """
    Generate Tailwind config for custom breakpoints.

    Args:
        breakpoints: List of breakpoint definitions

    Returns:
        Tailwind config string for tailwind.config.js
    """
    config_lines = ["theme: {", "  screens: {"]

    for bp in breakpoints:
        name = bp.get("tailwind", bp["name"])
        max_width = bp["maxWidth"]
        config_lines.append(f"    '{name}': '{max_width}px',")

    config_lines.append("  },")
    config_lines.append("},")

    return "\n".join(config_lines)


def analyze_responsive_patterns(design_data: dict) -> Dict[str, Any]:
    """
    Analyze design patterns for responsive behavior.

    Args:
        design_data: Complete Figma design data

    Returns:
        {
            "breakpoints": [...],
            "patterns": {
                "has_mobile_layout": bool,
                "has_tablet_layout": bool,
                "grid_columns": {"mobile": 1, "tablet": 2, "desktop": 3},
                "navigation_type": "hamburger|tabs|full"
            }
        }
    """
    breakpoints = detect_breakpoints(design_data)

    # Analyze patterns
    patterns = {
        "has_mobile_layout": False,
        "has_tablet_layout": False,
        "has_desktop_layout": True,
        "grid_columns": {"mobile": 1, "tablet": 2, "desktop": 3},
    }

    # Detect frame widths to infer layout variants
    frame_widths = []
    for frame in design_data.get("frames", []):
        bounds = frame.get("absoluteBoundingBox", {})
        width = bounds.get("width")
        if width:
            frame_widths.append(int(width))

    if frame_widths:
        min_width = min(frame_widths)
        max_width = max(frame_widths)

        # Mobile layout exists if we have frames < 768px
        patterns["has_mobile_layout"] = min_width < 768

        # Tablet layout exists if we have frames between 768-1024px
        patterns["has_tablet_layout"] = any(768 <= w <= 1024 for w in frame_widths)

        # Desktop layout
        patterns["has_desktop_layout"] = max_width >= 1024

    # Detect navigation pattern (simplified heuristic)
    # If mobile layout exists, likely uses hamburger menu
    if patterns["has_mobile_layout"]:
        patterns["navigation_type"] = "hamburger"
    else:
        patterns["navigation_type"] = "full"

    return {
        "breakpoints": breakpoints,
        "patterns": patterns,
        "tailwind_config": generate_tailwind_breakpoints(breakpoints),
    }


def get_responsive_class_names(
    node: dict,
    breakpoints: List[Dict[str, Any]]
) -> Dict[str, str]:
    """
    Generate responsive Tailwind class names for a node.

    Args:
        node: Figma node
        breakpoints: Detected breakpoints

    Returns:
        {
            "base": "flex items-center",
            "mobile": "sm:flex-col",
            "tablet": "md:flex-row md:gap-4",
            "desktop": "lg:gap-8"
        }
    """
    layout = node.get("layoutMode")
    item_spacing = node.get("itemSpacing", 0)

    classes = {"base": ""}

    # Base classes
    if layout == "HORIZONTAL":
        classes["base"] = "flex flex-row"
        # Stack vertically on mobile
        classes["mobile"] = "sm:flex-col"
        classes["tablet"] = "md:flex-row"
    elif layout == "VERTICAL":
        classes["base"] = "flex flex-col"

    # Spacing
    if item_spacing > 0:
        # Map spacing to Tailwind gap classes
        gap_class = _get_gap_class(item_spacing)
        classes["base"] += f" {gap_class}"

        # Smaller gap on mobile
        mobile_gap = _get_gap_class(item_spacing // 2)
        classes["mobile"] = f"sm:{mobile_gap}"

    return classes


def _get_gap_class(spacing: float) -> str:
    """Convert spacing value to Tailwind gap class."""
    # Tailwind spacing scale: 4px increments
    if spacing <= 4:
        return "gap-1"
    elif spacing <= 8:
        return "gap-2"
    elif spacing <= 12:
        return "gap-3"
    elif spacing <= 16:
        return "gap-4"
    elif spacing <= 24:
        return "gap-6"
    elif spacing <= 32:
        return "gap-8"
    else:
        return f"gap-[{int(spacing)}px]"
