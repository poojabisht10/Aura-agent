"""Accessibility utilities for WCAG compliance and ARIA support."""
from typing import Tuple, Optional, Dict, Any
import math


def get_contrast_ratio(color1: str, color2: str) -> float:
    """
    Calculate WCAG contrast ratio between two colors.
    
    Args:
        color1: First color in hex format (e.g., "#FFFFFF")
        color2: Second color in hex format (e.g., "#000000")
        
    Returns:
        Contrast ratio (1.0 to 21.0)
    """
    def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join([c * 2 for c in hex_color])
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def get_luminance(rgb: Tuple[int, int, int]) -> float:
        """Calculate relative luminance according to WCAG."""
        r, g, b = rgb
        rsrgb = r / 255.0
        gsrgb = g / 255.0
        bsrgb = b / 255.0
        
        def adjust(c: float) -> float:
            if c <= 0.03928:
                return c / 12.92
            return math.pow((c + 0.055) / 1.055, 2.4)
        
        r = adjust(rsrgb)
        g = adjust(gsrgb)
        b = adjust(bsrgb)
        
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    
    try:
        rgb1 = hex_to_rgb(color1)
        rgb2 = hex_to_rgb(color2)
        
        lum1 = get_luminance(rgb1)
        lum2 = get_luminance(rgb2)
        
        lighter = max(lum1, lum2)
        darker = min(lum1, lum2)
        
        if darker == 0:
            return 0.0
        
        return (lighter + 0.05) / (darker + 0.05)
    except Exception:
        return 0.0


def check_contrast_ratio(
    text_color: str,
    background_color: str,
    is_large_text: bool = False
) -> Dict[str, Any]:
    """
    Check if color contrast meets WCAG standards.
    
    Args:
        text_color: Text color in hex format
        background_color: Background color in hex format
        is_large_text: Whether text is large (18pt+ or 14pt+ bold)
        
    Returns:
        Dictionary with pass status, ratio, and level
    """
    ratio = get_contrast_ratio(text_color, background_color)
    
    # WCAG AA: 4.5:1 for normal text, 3:1 for large text
    # WCAG AAA: 7:1 for normal text, 4.5:1 for large text
    aa_threshold = 3.0 if is_large_text else 4.5
    aaa_threshold = 4.5 if is_large_text else 7.0
    
    passes_aa = ratio >= aa_threshold
    passes_aaa = ratio >= aaa_threshold
    
    level = "AAA" if passes_aaa else ("AA" if passes_aa else "FAIL")
    
    return {
        "passes_aa": passes_aa,
        "passes_aaa": passes_aaa,
        "ratio": round(ratio, 2),
        "level": level,
        "text_color": text_color,
        "background_color": background_color,
    }


def suggest_accessible_color(
    text_color: str,
    background_color: str,
    is_large_text: bool = False
) -> Optional[str]:
    """
    Suggest an accessible color alternative if contrast is too low.
    
    Args:
        text_color: Current text color in hex format
        background_color: Background color in hex format
        is_large_text: Whether text is large
        
    Returns:
        Suggested color in hex format or None if already accessible
    """
    check = check_contrast_ratio(text_color, background_color, is_large_text)
    
    if check["passes_aa"]:
        return None
    
    # Try to adjust brightness to improve contrast
    def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join([c * 2 for c in hex_color])
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    
    def is_dark(color: str) -> bool:
        """Check if color is dark."""
        rgb = hex_to_rgb(color)
        luminance = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255
        return luminance < 0.5
    
    # If background is dark, suggest lighter text; if light, suggest darker text
    bg_is_dark = is_dark(background_color)
    
    if bg_is_dark:
        # Make text lighter
        rgb = hex_to_rgb(text_color)
        # Increase brightness
        new_rgb = tuple(min(255, int(c * 1.5)) for c in rgb)
    else:
        # Make text darker
        rgb = hex_to_rgb(text_color)
        # Decrease brightness
        new_rgb = tuple(max(0, int(c * 0.5)) for c in rgb)
    
    suggested = rgb_to_hex(new_rgb)
    
    # Verify the suggestion meets contrast requirements
    new_check = check_contrast_ratio(suggested, background_color, is_large_text)
    if new_check["passes_aa"]:
        return suggested
    
    # Fallback: use pure white or black
    return "#FFFFFF" if bg_is_dark else "#000000"


def generate_alt_text(
    image_name: str,
    semantic_type: str,
    surrounding_text: str = "",
    is_decorative: bool = False
) -> str:
    """
    Generate accessible alt text for images.
    
    Args:
        image_name: Name of the image from Figma
        semantic_type: Semantic type of the image (logo, product, decorative, etc.)
        surrounding_text: Text near the image for context
        is_decorative: Whether the image is purely decorative
        
    Returns:
        Alt text string (empty string for decorative images)
    """
    if is_decorative:
        return ""
    
    # Clean up image name
    name = image_name.lower().replace("_", " ").replace("-", " ").strip()
    
    # Generate based on semantic type
    if semantic_type == "logo":
        # Extract brand name from image name or surrounding text
        brand_name = name.replace("logo", "").strip()
        if not brand_name and surrounding_text:
            # Try to extract from surrounding text
            words = surrounding_text.split()
            if words:
                brand_name = words[0]
        return f"{brand_name} logo" if brand_name else "Company logo"
    
    elif semantic_type == "product":
        product_name = name.replace("product", "").replace("image", "").strip()
        return product_name if product_name else "Product image"
    
    elif semantic_type == "icon":
        icon_name = name.replace("icon", "").strip()
        return icon_name if icon_name else "Icon"
    
    elif "avatar" in name or "profile" in name:
        return "Profile picture"
    
    elif "thumbnail" in name:
        return "Thumbnail image"
    
    # Use image name as base, clean it up
    if name:
        # Capitalize first letter
        alt_text = name[0].upper() + name[1:] if len(name) > 1 else name.upper()
        return alt_text
    
    # Fallback
    return "Image"
