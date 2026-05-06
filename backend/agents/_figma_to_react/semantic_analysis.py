"""Semantic type inference and ARIA role mapping for Figma nodes."""

from typing import Optional


def infer_semantic_type(node: dict) -> tuple[str, str]:
    """
    Infer the semantic type of a node based on its name, structure, and properties.

    Args:
        node: Figma node dictionary

    Returns:
        Tuple of (semantic_type, suggested_html_element)
    """
    name = node.get("name", "").lower()
    node_type = node.get("type", "")
    children = node.get("children", [])
    layout = node.get("layout", {})
    fills = node.get("fills", [])
    bounds = layout.get("bounds", {})
    width = bounds.get("width", 0)
    height = bounds.get("height", 0)

    # Check for button patterns
    button_keywords = ["button", "btn", "cta", "submit", "action", "learn more", "get started", "sign up", "log in", "buy", "shop"]
    if any(kw in name for kw in button_keywords):
        return ("button", "button")

    # Small clickable frame with text and background = likely button
    if node_type in ("FRAME", "INSTANCE", "COMPONENT"):
        has_text_child = any(c.get("type") == "TEXT" for c in children)
        has_background = len(fills) > 0 and fills[0].get("type") == "SOLID"
        is_small = width < 400 and height < 100
        if has_text_child and has_background and is_small and len(children) <= 3:
            return ("button", "button")

    # Check for header/navigation patterns
    header_keywords = ["header", "navbar", "nav", "navigation", "topbar", "top-bar", "menu-bar"]
    if any(kw in name for kw in header_keywords):
        return ("header", "header")

    # Top of page, contains logo or multiple links = likely header
    if node_type in ("FRAME", "INSTANCE", "COMPONENT"):
        y_pos = bounds.get("y", 0)
        if y_pos < 100 and width > 800:
            has_logo = any("logo" in c.get("name", "").lower() for c in children)
            link_count = sum(1 for c in children if any(kw in c.get("name", "").lower() for kw in ["link", "nav", "menu"]))
            if has_logo or link_count >= 3:
                return ("header", "header")

    # Check for footer patterns
    footer_keywords = ["footer", "bottom-bar", "bottombar"]
    if any(kw in name for kw in footer_keywords):
        return ("footer", "footer")

    # Check for sidebar patterns
    sidebar_keywords = ["sidebar", "side-bar", "sidenav", "side-nav", "drawer", "panel"]
    if any(kw in name for kw in sidebar_keywords):
        return ("sidebar", "aside")

    # Narrow vertical panel = likely sidebar
    if node_type in ("FRAME", "INSTANCE", "COMPONENT"):
        is_narrow = width < 350 and height > 400
        is_vertical = layout.get("mode") == "VERTICAL"
        if is_narrow and is_vertical:
            return ("sidebar", "aside")

    # Check for card patterns
    card_keywords = ["card", "tile", "item", "product", "article"]
    if any(kw in name for kw in card_keywords):
        return ("card", "article")

    # Contained box with image and text = likely card
    if node_type in ("FRAME", "INSTANCE", "COMPONENT"):
        has_image = any(
            c.get("type") == "RECTANGLE" and
            any(f.get("type") == "IMAGE" for f in c.get("fills", []))
            for c in children
        ) or any(f.get("type") == "IMAGE" for f in fills)
        has_text = any(c.get("type") == "TEXT" for c in children)
        has_border_radius = node.get("cornerRadius", {}).get("all", 0) > 0
        is_contained = 200 < width < 600 and 200 < height < 600
        if has_image and has_text and is_contained:
            return ("card", "article")

    # Check for input/form field patterns
    input_keywords = ["input", "field", "textfield", "text-field", "search", "email", "password", "form"]
    if any(kw in name for kw in input_keywords):
        return ("input", "input")

    # Check for hero section patterns
    hero_keywords = ["hero", "banner", "jumbotron", "showcase", "spotlight"]
    if any(kw in name for kw in hero_keywords):
        return ("hero", "section")

    # Large section at top with CTA = likely hero
    if node_type in ("FRAME", "INSTANCE", "COMPONENT"):
        y_pos = bounds.get("y", 0)
        is_large = width > 800 and height > 300
        has_cta = any(
            any(kw in c.get("name", "").lower() for kw in button_keywords)
            for c in children
        )
        if y_pos < 200 and is_large and has_cta:
            return ("hero", "section")

    # Check for section patterns
    section_keywords = ["section", "block", "container", "wrapper", "content"]
    if any(kw in name for kw in section_keywords):
        return ("section", "section")

    # Check for image patterns
    image_keywords = ["image", "img", "photo", "picture", "thumbnail", "avatar", "icon"]
    if any(kw in name for kw in image_keywords) or node_type == "RECTANGLE":
        if any(f.get("type") == "IMAGE" for f in fills):
            return ("image", "img")

    # Check for text/heading patterns
    if node_type == "TEXT":
        text_content = node.get("text", "")
        style = node.get("style", {})
        font_size = style.get("fontSize", 16)
        font_weight = style.get("fontWeight", 400)

        # Large bold text = heading
        if font_size >= 24 or font_weight >= 600:
            if font_size >= 32:
                return ("heading", "h1")
            elif font_size >= 24:
                return ("heading", "h2")
            else:
                return ("heading", "h3")

        # Check for link patterns
        link_keywords = ["link", "learn more", "read more", "view", "see all", "explore"]
        if any(kw in text_content.lower() for kw in link_keywords):
            return ("link", "a")

        return ("text", "p")

    # Check for list patterns
    list_keywords = ["list", "items", "menu", "options"]
    if any(kw in name for kw in list_keywords):
        return ("list", "ul")

    # Check if contains repeated similar children = likely list
    if len(children) >= 3:
        child_types = [c.get("type") for c in children]
        if len(set(child_types)) == 1:  # All same type
            child_names = [c.get("name", "").lower() for c in children]
            # Check if names follow a pattern (e.g., "item 1", "item 2")
            if all("item" in n or "card" in n for n in child_names):
                return ("list", "ul")

    # Check for interactive elements: carousel/slider
    carousel_keywords = ["carousel", "slider", "slideshow", "gallery", "swiper", "carousel-container"]
    if any(kw in name for kw in carousel_keywords):
        return ("carousel", "div")

    # Detect carousel by structure: multiple similar items with navigation arrows
    if node_type in ("FRAME", "INSTANCE", "COMPONENT"):
        has_arrows = any(
            "arrow" in c.get("name", "").lower() or
            "prev" in c.get("name", "").lower() or
            "next" in c.get("name", "").lower() or
            "left" in c.get("name", "").lower() or
            "right" in c.get("name", "").lower()
            for c in children
        )
        has_multiple_items = len([c for c in children if c.get("type") in ("FRAME", "INSTANCE", "COMPONENT")]) >= 2
        if has_arrows and has_multiple_items:
            return ("carousel", "div")

    # Check for modal/dialog patterns
    modal_keywords = ["modal", "dialog", "popup", "overlay", "lightbox"]
    if any(kw in name for kw in modal_keywords):
        return ("modal", "div")

    # Check for dropdown/select patterns
    dropdown_keywords = ["dropdown", "select", "menu", "options", "picker"]
    if any(kw in name for kw in dropdown_keywords) and node_type in ("FRAME", "INSTANCE", "COMPONENT"):
        has_options = len(children) > 1
        if has_options:
            return ("dropdown", "select")

    # Check for accordion patterns
    accordion_keywords = ["accordion", "collapse", "expandable", "faq"]
    if any(kw in name for kw in accordion_keywords):
        return ("accordion", "div")

    # Check for tab patterns
    tab_keywords = ["tab", "tabs", "tabbed", "tab-panel"]
    if any(kw in name for kw in tab_keywords):
        return ("tabs", "div")

    # Check for navigation/menu patterns
    nav_keywords = ["nav", "navigation", "menu", "links"]
    if any(kw in name for kw in nav_keywords) and node_type in ("FRAME", "INSTANCE", "COMPONENT"):
        has_links = sum(1 for c in children if "link" in c.get("name", "").lower() or c.get("type") == "TEXT")
        if has_links >= 2:
            return ("navigation", "nav")

    # Default: generic container
    if node_type in ("FRAME", "GROUP", "COMPONENT", "INSTANCE"):
        return ("container", "div")

    return ("unknown", "div")


def get_aria_role(semantic_type: str, node_data: dict = None) -> Optional[str]:
    """
    Map semantic type to ARIA role.

    Args:
        semantic_type: Detected semantic type
        node_data: Node data dictionary (optional, for future use)

    Returns:
        ARIA role string or None
    """
    role_map = {
        "header": "banner",
        "footer": "contentinfo",
        "navigation": "navigation",
        "main": "main",
        "button": "button",
        "link": "link",
        "input": "textbox",
        "search": "search",
        "form": "form",
        "list": "list",
        "article": "article",
        "card": "article",
        "aside": "complementary",
        "sidebar": "complementary",
        "section": "region",
        "hero": "region",
        "carousel": "region",
        "modal": "dialog",
        "dropdown": "combobox",
        "accordion": "region",
        "tabs": "tablist",
    }
    return role_map.get(semantic_type)
