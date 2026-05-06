"""Visual comparison utilities for comparing generated websites with Figma designs."""
import asyncio
import json
import platform
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import subprocess
import time
import httpx

from backend.utils import get_npx_command


async def capture_page_screenshot(
    port: int,
    output_path: Path,
    timeout: int = 30,
    full_page: bool = True,
    viewport_width: int = 1440,
    viewport_height: int = 900,
) -> Optional[Path]:
    """
    Capture full page screenshot using Playwright via subprocess.

    Args:
        port: Port number where dev server is running
        output_path: Directory to save screenshot
        timeout: Maximum time to wait for screenshot
        full_page: Whether to capture full scrollable page
        viewport_width: Browser viewport width
        viewport_height: Browser viewport height

    Returns:
        Path to screenshot file or None if failed
    """
    output_path.mkdir(parents=True, exist_ok=True)
    screenshot_path = output_path / f"screenshot_{int(time.time())}.png"

    url = f"http://localhost:{port}"

    try:
        # Use Playwright CLI to capture screenshot with options
        args = [get_npx_command(), "playwright", "screenshot", url, str(screenshot_path)]
        if full_page:
            args.append("--full-page")
        args.extend(["--viewport-size", f"{viewport_width},{viewport_height}"])

        print(f"[Visual Comparison] Running: {' '.join(args)}")

        # On Windows, use shell=True for better .cmd file handling
        use_shell = platform.system() == "Windows"

        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=use_shell,
        )

        if result.returncode == 0 and screenshot_path.exists():
            print(f"[Visual Comparison] Screenshot saved to {screenshot_path}")
            return screenshot_path
        else:
            print(f"[Visual Comparison] Screenshot capture failed (code {result.returncode}): {result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        print(f"[Visual Comparison] Screenshot capture timed out after {timeout}s")
        return None
    except Exception as e:
        print(f"[Visual Comparison] Error capturing screenshot: {e}")
        return None


async def compare_with_figma_design(
    screenshot_path: Path,
    design_data: dict,
    project_path: Path
) -> dict:
    """
    Compare screenshot with Figma design data and return discrepancies.

    Performs comprehensive comparison:
    - Text content presence (across all source files)
    - Color values usage
    - Layout structure (components, nesting)
    - Font usage
    - Image assets

    Args:
        screenshot_path: Path to captured screenshot
        design_data: Complete Figma design data (from plugin or REST API)
        project_path: Path to generated project

    Returns:
        Dictionary with comparison results:
        {
            "matches": bool,
            "discrepancies": list,
            "confidence": float (0.0 to 1.0),
            "details": dict  # Detailed breakdown
        }
    """
    if not screenshot_path.exists():
        return {
            "matches": False,
            "discrepancies": [{"type": "error", "message": "Screenshot file not found"}],
            "confidence": 0.0,
            "details": {},
        }

    discrepancies = []
    confidence_score = 1.0
    details = {
        "texts_checked": 0,
        "texts_found": 0,
        "colors_checked": 0,
        "colors_found": 0,
        "components_expected": 0,
        "components_found": 0,
    }

    # Extract design elements
    design_texts = _extract_text_from_design(design_data)
    design_colors = _extract_colors_from_design(design_data)
    design_fonts = _extract_fonts_from_design(design_data)

    # Collect all source code content for text/color matching
    all_source_content = _collect_source_content(project_path)

    # === TEXT CONTENT CHECK ===
    details["texts_checked"] = len(design_texts)
    missing_texts = []
    found_texts = []

    for text in design_texts:
        if text and text.strip() and len(text.strip()) > 2:
            # Check in all source files
            if text in all_source_content:
                found_texts.append(text)
            else:
                # Try partial match for longer texts
                if len(text) > 20:
                    words = text.split()
                    if len(words) >= 3:
                        # Check if first 3 words appear together
                        partial = " ".join(words[:3])
                        if partial in all_source_content:
                            found_texts.append(text)
                            continue
                missing_texts.append(text)

    details["texts_found"] = len(found_texts)

    if missing_texts:
        # Only report significant missing text
        significant_missing = [t for t in missing_texts if len(t) > 3]
        if significant_missing:
            discrepancies.append({
                "type": "text",
                "issue": "missing_text",
                "missing_texts": significant_missing[:10],
                "total_missing": len(significant_missing),
                "severity": "high" if len(significant_missing) > 5 else "medium",
            })
            # Penalty based on percentage missing
            if design_texts:
                missing_ratio = len(significant_missing) / len(design_texts)
                confidence_score -= min(0.3, missing_ratio * 0.5)

    # === COLOR CHECK ===
    details["colors_checked"] = len(design_colors)
    missing_colors = []
    found_colors = []

    for color in design_colors:
        color_upper = color.upper()
        color_lower = color.lower()
        color_no_hash = color.replace("#", "").lower()

        # Check various color formats
        if (color_upper in all_source_content or
            color_lower in all_source_content or
            color_no_hash in all_source_content or
            _color_in_tailwind(color, all_source_content)):
            found_colors.append(color)
        else:
            missing_colors.append(color)

    details["colors_found"] = len(found_colors)

    if missing_colors and len(missing_colors) > 2:
        discrepancies.append({
            "type": "color",
            "issue": "missing_colors",
            "missing_colors": missing_colors[:10],
            "total_missing": len(missing_colors),
            "severity": "medium",
        })
        if design_colors:
            missing_ratio = len(missing_colors) / len(design_colors)
            confidence_score -= min(0.15, missing_ratio * 0.3)

    # === COMPONENT STRUCTURE CHECK ===
    components_dir = project_path / "src" / "components"
    component_files = []

    if components_dir.exists():
        component_files = list(components_dir.glob("**/*.tsx"))
        component_files.extend(components_dir.glob("**/*.jsx"))

    details["components_found"] = len(component_files)

    # Estimate expected components from design structure
    expected_components = _estimate_component_count(design_data)
    details["components_expected"] = expected_components

    if not component_files:
        discrepancies.append({
            "type": "structure",
            "issue": "no_components",
            "message": "No component files found in src/components",
            "severity": "high",
        })
        confidence_score -= 0.25
    elif len(component_files) < expected_components * 0.5:
        discrepancies.append({
            "type": "structure",
            "issue": "few_components",
            "message": f"Only {len(component_files)} components found, expected ~{expected_components}",
            "severity": "medium",
        })
        confidence_score -= 0.1

    # === FONT CHECK ===
    if design_fonts:
        missing_fonts = []
        for font in design_fonts:
            font_lower = font.lower()
            if font_lower not in all_source_content.lower():
                # Check common alternatives
                if not _has_font_alternative(font, all_source_content):
                    missing_fonts.append(font)

        if missing_fonts:
            discrepancies.append({
                "type": "font",
                "issue": "missing_fonts",
                "missing_fonts": missing_fonts[:5],
                "severity": "low",
            })
            confidence_score -= 0.05 * min(len(missing_fonts), 3)

    # === LAYOUT INTEGRITY CHECK ===
    layout_issues = _check_layout_integrity(project_path, design_data)
    if layout_issues:
        discrepancies.extend(layout_issues)
        confidence_score -= 0.05 * len(layout_issues)

    # Ensure confidence is between 0 and 1
    confidence_score = max(0.0, min(1.0, confidence_score))

    # Match threshold - more lenient for initial generation
    matches = confidence_score >= 0.85 and not any(
        d.get("severity") == "high" for d in discrepancies
    )

    return {
        "matches": matches,
        "discrepancies": discrepancies,
        "confidence": confidence_score,
        "details": details,
    }


def _collect_source_content(project_path: Path) -> str:
    """Collect all source file content for matching."""
    content_parts = []

    src_dir = project_path / "src"
    if src_dir.exists():
        for ext in ["*.tsx", "*.jsx", "*.ts", "*.js", "*.css"]:
            for file in src_dir.glob(f"**/{ext}"):
                try:
                    content_parts.append(file.read_text(encoding="utf-8"))
                except Exception:
                    pass

    # Also check index.html
    index_html = project_path / "index.html"
    if index_html.exists():
        try:
            content_parts.append(index_html.read_text(encoding="utf-8"))
        except Exception:
            pass

    return "\n".join(content_parts)


def _color_in_tailwind(hex_color: str, content: str) -> bool:
    """Check if a color might be represented via Tailwind classes."""
    # Common Tailwind color mappings
    hex_lower = hex_color.lower().replace("#", "")

    # Check for common color names in Tailwind format
    tailwind_colors = {
        "000000": ["black", "slate-900", "gray-900", "zinc-900"],
        "ffffff": ["white"],
        "f3f4f6": ["gray-100"],
        "e5e7eb": ["gray-200"],
        "d1d5db": ["gray-300"],
        "9ca3af": ["gray-400"],
        "6b7280": ["gray-500"],
        "4b5563": ["gray-600"],
        "374151": ["gray-700"],
        "1f2937": ["gray-800"],
        "111827": ["gray-900"],
    }

    if hex_lower in tailwind_colors:
        for tw_class in tailwind_colors[hex_lower]:
            if tw_class in content:
                return True

    return False


def _has_font_alternative(font: str, content: str) -> bool:
    """Check if a font has a common alternative in the content."""
    font_lower = font.lower()
    alternatives = {
        "inter": ["system-ui", "sans-serif", "ui-sans-serif"],
        "roboto": ["system-ui", "sans-serif"],
        "open sans": ["system-ui", "sans-serif"],
        "sf pro": ["system-ui", "-apple-system"],
        "helvetica": ["arial", "sans-serif"],
    }

    if font_lower in alternatives:
        content_lower = content.lower()
        return any(alt in content_lower for alt in alternatives[font_lower])

    return False


def _estimate_component_count(design_data: dict) -> int:
    """Estimate how many components should be created from design."""
    count = 0

    def count_frames(node: dict, depth: int = 0):
        nonlocal count
        node_type = node.get("type", "")

        # Count significant frames as potential components
        if node_type in ("FRAME", "COMPONENT", "INSTANCE") and depth <= 3:
            if node.get("name", "").strip() and not node.get("name", "").startswith("_"):
                count += 1

        # Recurse into children
        for child in node.get("children", []):
            count_frames(child, depth + 1)

    # Process all pages and frames
    pages = design_data.get("pages", [])
    for page in pages:
        for frame in page.get("frames", []):
            count_frames(frame)

    # Minimum of 3, cap at reasonable number
    return max(3, min(count, 20))


def _check_layout_integrity(project_path: Path, design_data: dict) -> List[dict]:
    """Check for common layout issues."""
    issues = []

    # Check if App.tsx exists and has content
    app_tsx = project_path / "src" / "App.tsx"
    if app_tsx.exists():
        content = app_tsx.read_text(encoding="utf-8")

        # Check for empty return
        if "return null" in content or "return <></>" in content:
            issues.append({
                "type": "layout",
                "issue": "empty_render",
                "message": "App component returns empty content",
                "severity": "high",
            })

        # Check for basic structure
        if "className" not in content and "style=" not in content:
            issues.append({
                "type": "layout",
                "issue": "no_styling",
                "message": "No styling found in App component",
                "severity": "medium",
            })

    return issues


def _extract_fonts_from_design(design_data: dict) -> List[str]:
    """Extract unique font families from design data."""
    fonts = set()

    def extract_from_node(node: dict):
        # Check text style
        if "style" in node:
            font_family = node["style"].get("fontFamily")
            if font_family:
                fonts.add(font_family)

        # Check children
        for child in node.get("children", []):
            extract_from_node(child)

    # Extract from pages/frames
    pages = design_data.get("pages", [])
    for page in pages:
        for frame in page.get("frames", []):
            extract_from_node(frame)

    # Also check fonts array if available (from plugin)
    for font_info in design_data.get("fonts", []):
        if isinstance(font_info, dict) and "family" in font_info:
            fonts.add(font_info["family"])
        elif isinstance(font_info, str):
            fonts.add(font_info)

    return list(fonts)


def _extract_text_from_design(design_data: dict) -> List[str]:
    """Extract all text content from design data."""
    texts = []
    
    def extract_from_node(node: dict):
        if "characters" in node:
            text = node["characters"]
            if text and text.strip():
                texts.append(text.strip())
        
        if "children" in node:
            for child in node["children"]:
                extract_from_node(child)
    
    # Extract from all pages and frames
    pages = design_data.get("pages", [])
    for page in pages:
        frames = page.get("frames", [])
        for frame in frames:
            extract_from_node(frame)
    
    return texts


def _extract_colors_from_design(design_data: dict) -> List[str]:
    """Extract all unique colors from design data."""
    colors = set()
    
    def extract_from_node(node: dict):
        # Check fills
        if "fills" in node:
            for fill in node["fills"]:
                if "color" in fill:
                    color = fill["color"]
                    if isinstance(color, dict):
                        # Convert RGBA to hex
                        r = int(color.get("r", 0) * 255)
                        g = int(color.get("g", 0) * 255)
                        b = int(color.get("b", 0) * 255)
                        hex_color = f"#{r:02x}{g:02x}{b:02x}"
                        colors.add(hex_color.upper())
                    elif isinstance(color, str) and color.startswith("#"):
                        colors.add(color.upper())
        
        # Check children
        if "children" in node:
            for child in node["children"]:
                extract_from_node(child)
    
    # Extract from all pages and frames
    pages = design_data.get("pages", [])
    for page in pages:
        frames = page.get("frames", [])
        for frame in frames:
            extract_from_node(frame)
    
    return list(colors)


async def wait_for_server_ready(port: int, max_wait: int = 30) -> bool:
    """Wait for dev server to be ready by checking if it responds."""
    url = f"http://localhost:{port}"
    
    for _ in range(max_wait):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return True
        except Exception:
            pass
        
        await asyncio.sleep(1)
    
    return False
