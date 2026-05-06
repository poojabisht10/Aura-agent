"""Element-level screenshot capture and comparison for Figma-to-code verification.

Pipeline:
  1. Playwright subprocess → screenshot every [data-figma-id] element from the running app
  2. Figma REST API → export the same node IDs as PNGs
  3. Per-element comparison: dimension match + optional pixel diff
  4. Returns a structured report: per-element visual accuracy scores
"""

import asyncio
import json
import platform
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.config import settings
from backend.utils import get_npx_command


# ---------------------------------------------------------------------------
# JavaScript: capture screenshots of every data-figma-id element
# ---------------------------------------------------------------------------

def _build_element_capture_script(url: str, output_dir: str, viewport_width: int = 1440, viewport_height: int = 900) -> str:
    """Build a Node.js script that screenshots every [data-figma-id] element."""
    # Escape backslashes for Windows paths
    safe_dir = output_dir.replace("\\", "/")
    return f"""
const {{ chromium }} = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {{
  const browser = await chromium.launch({{ headless: true }});
  const page = await browser.newPage({{ viewport: {{ width: {viewport_width}, height: {viewport_height} }} }});
  try {{
    await page.goto('{url}', {{ waitUntil: 'networkidle', timeout: 30000 }});
    await page.waitForTimeout(1000);

    const elements = await page.$$('[data-figma-id]');
    const results = {{}};

    for (const el of elements) {{
      const figmaId = await el.getAttribute('data-figma-id');
      const bbox = await el.boundingBox();

      if (!figmaId || !bbox || bbox.width <= 0 || bbox.height <= 0) {{
        continue;
      }}

      // Sanitize ID for use as filename
      const safeId = figmaId.replace(/[^a-zA-Z0-9_\\-]/g, '_');
      const screenshotPath = path.join('{safe_dir}', safeId + '.png');

      try {{
        await el.screenshot({{ path: screenshotPath, type: 'png' }});
        results[figmaId] = {{
          path: screenshotPath,
          width: Math.round(bbox.width),
          height: Math.round(bbox.height),
          x: Math.round(bbox.x),
          y: Math.round(bbox.y),
        }};
      }} catch (err) {{
        // Element may have scrolled off or been unmounted — skip
      }}
    }}

    process.stdout.write(JSON.stringify(results));
  }} catch (err) {{
    process.stderr.write('Error: ' + err.message);
    process.exit(1);
  }} finally {{
    await browser.close();
  }}
}})();
"""


async def capture_element_screenshots(
    port: int,
    output_dir: Path,
    viewport: Optional[Dict[str, int]] = None,
) -> Dict[str, dict]:
    """
    Navigate to localhost:{port} and capture a PNG screenshot of every
    element that has a `data-figma-id` attribute.

    Args:
        port: Dev server port.
        output_dir: Directory where element PNGs will be saved.
        viewport: Optional {width, height} for Playwright viewport.

    Returns:
        Dict mapping figma_id → {path, width, height, x, y}
    """
    vp = viewport or {"width": 1440, "height": 900}
    output_dir.mkdir(parents=True, exist_ok=True)
    url = f"http://localhost:{port}"
    script = _build_element_capture_script(url, str(output_dir), vp["width"], vp["height"])

    # Write script INTO the project root so Node.js require() walks up and
    # finds node_modules/playwright (system temp is outside the project tree).
    project_root = Path(__file__).resolve().parents[2]
    import os as _os
    script_path = project_root / f"_aura2_elemcap_{_os.getpid()}_{time.time_ns()}.cjs"
    script_path.write_text(script, encoding="utf-8")

    try:
        use_shell = platform.system() == "Windows"
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                ["node", str(script_path)],
                capture_output=True,
                text=True,
                timeout=60,
                shell=use_shell,
            ),
        )

        if result.returncode != 0:
            print(f"[ElemCap] Script failed: {result.stderr[:400]}", flush=True)
            return {}

        raw = result.stdout.strip()
        if not raw:
            return {}

        data: dict = json.loads(raw)
        print(f"[ElemCap] Captured {len(data)} element screenshots", flush=True)
        return data

    except subprocess.TimeoutExpired:
        print("[ElemCap] Script timed out", flush=True)
        return {}
    except json.JSONDecodeError as exc:
        print(f"[ElemCap] JSON parse error: {exc}", flush=True)
        return {}
    except Exception as exc:
        print(f"[ElemCap] Error: {exc}", flush=True)
        return {}
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Figma node image export
# ---------------------------------------------------------------------------

async def export_figma_node_images(
    design_data: dict,
    figma_token: str,
    file_key: str,
    output_dir: Path,
    max_nodes: int = 30,
) -> Dict[str, Path]:
    """
    Export Figma node images for all node IDs found in design_data.

    Args:
        design_data: Design data (used to collect node IDs).
        figma_token: Figma personal access token.
        file_key: Figma file key.
        output_dir: Directory to save PNGs.
        max_nodes: Maximum nodes to export (API has rate limits).

    Returns:
        Dict mapping node_id → local PNG path.
    """
    from backend.utils.figma_screenshot import export_figma_design_image

    # Collect all node IDs from design_data
    node_ids = _collect_node_ids(design_data, max_nodes)
    if not node_ids:
        print("[ElemCap] No node IDs found in design data", flush=True)
        return {}

    print(f"[ElemCap] Exporting {len(node_ids)} Figma nodes as PNGs...", flush=True)
    return await export_figma_design_image(
        file_key=file_key,
        node_ids=node_ids,
        figma_token=figma_token,
        output_dir=output_dir,
        scale=1,
        format="png",
    )


# Node types eligible for pixel comparison. TEXT is excluded: text widths vary
# across renderers (font fallback, subpixel antialiasing) so pixel diff is noisy.
_PIXEL_DIFF_NODE_TYPES = {"FRAME", "GROUP", "COMPONENT", "INSTANCE", "RECTANGLE"}
# Minimum pixel area: below this, icons/badges produce noisy pixel diffs.
_MIN_NODE_SIDE_PX = 40


def _collect_node_ids(design_data: dict, max_nodes: int) -> List[str]:
    """Walk design tree and collect node IDs for pixel comparison.

    Filters:
      - Only FRAME / GROUP / COMPONENT / INSTANCE / RECTANGLE node types.
      - Skip nodes smaller than _MIN_NODE_SIDE_PX on either side.
      - Skip nodes without meaningful bounds.
    """
    ids: List[str] = []

    def _walk(node: dict):
        if len(ids) >= max_nodes:
            return
        nid = node.get("id", "")
        ntype = node.get("type", "")
        bounds = node.get("layout", {}).get("bounds", {}) or {}
        width = bounds.get("width") or 0
        height = bounds.get("height") or 0

        eligible = (
            nid
            and ntype in _PIXEL_DIFF_NODE_TYPES
            and width >= _MIN_NODE_SIDE_PX
            and height >= _MIN_NODE_SIDE_PX
        )
        if eligible:
            ids.append(nid)

        for child in node.get("children", []):
            _walk(child)

    for page in design_data.get("pages", []):
        for frame in page.get("frames", []):
            _walk(frame)
            if len(ids) >= max_nodes:
                break

    return ids


# ---------------------------------------------------------------------------
# Dimension-based element comparison (no external dependencies)
# ---------------------------------------------------------------------------

def compare_element_dimensions(
    dom_elements: Dict[str, dict],
    figma_props: Optional[Dict[str, dict]] = None,
    tolerance_px: int = 4,
) -> List[dict]:
    """
    Compare rendered element dimensions against Figma design specs.

    This is the lightweight comparison (no pixel diff required): it checks
    that each element's width and height match the Figma bounding box within
    the given tolerance.

    Args:
        dom_elements: Result from capture_element_screenshots() — {figma_id: {width, height, ...}}
        figma_props: Result from _extract_figma_properties() — keyed by figma_id.
        tolerance_px: Pixel tolerance for dimension matching.

    Returns:
        List of per-element dimension check dicts.
    """
    results = []

    for figma_id, dom_info in dom_elements.items():
        entry: dict = {
            "figma_id": figma_id,
            "dom_width": dom_info.get("width", 0),
            "dom_height": dom_info.get("height", 0),
            "screenshot_path": dom_info.get("path", ""),
        }

        if figma_props:
            figma_info = figma_props.get(figma_id)
            if figma_info:
                entry["element_name"] = figma_info.get("name", figma_id)
                fw = figma_info.get("width")
                fh = figma_info.get("height")
                if fw is not None:
                    diff_w = abs(fw - dom_info.get("width", 0))
                    entry["figma_width"] = fw
                    entry["width_match"] = diff_w <= tolerance_px
                    entry["width_diff_px"] = round(diff_w, 1)
                if fh is not None:
                    diff_h = abs(fh - dom_info.get("height", 0))
                    entry["figma_height"] = fh
                    entry["height_match"] = diff_h <= tolerance_px
                    entry["height_diff_px"] = round(diff_h, 1)

                # Overall match
                w_ok = entry.get("width_match", True)
                h_ok = entry.get("height_match", True)
                entry["match"] = w_ok and h_ok

        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Pixel-level comparison (optional, uses Pillow if available)
# ---------------------------------------------------------------------------

# ΔE2000 perceptual threshold: values below 3.0 are indistinguishable to most
# observers (CIE "just noticeable difference" is ~2.3).
_PIXEL_DELTA_E_THRESHOLD = 3.0


def compare_element_pixels(
    dom_shot_path: Path,
    figma_shot_path: Path,
) -> dict:
    """
    Compare two element screenshots pixel-by-pixel using ΔE2000 perceptual
    distance (more accurate than raw RGB channel diff).

    Uses Pillow if available; falls back to a size-only check.

    Args:
        dom_shot_path: Path to the rendered DOM element screenshot.
        figma_shot_path: Path to the Figma-exported element PNG.

    Returns:
        {
            "pixel_match_ratio": float,  # 0.0–1.0 (1.0 = identical)
            "dimension_match": bool,
            "method": "pillow" | "size_only"
        }
    """
    try:
        from PIL import Image  # type: ignore
        from backend.utils.structural_comparison import _color_delta_e

        img1 = Image.open(dom_shot_path).convert("RGBA")
        img2 = Image.open(figma_shot_path).convert("RGBA")

        # Resize to same dimensions for comparison
        if img1.size != img2.size:
            img2 = img2.resize(img1.size, Image.LANCZOS)
            dimension_match = False
        else:
            dimension_match = True

        pixels1 = list(img1.getdata())
        pixels2 = list(img2.getdata())

        if not pixels1:
            return {"pixel_match_ratio": 0.0, "dimension_match": dimension_match, "method": "pillow"}

        # Perceptual match using ΔE2000. Threshold 3.0 ≈ "imperceptible to most."
        # Fast-path: exact or near-exact RGB matches skip the expensive ΔE calc.
        matching = 0
        for p1, p2 in zip(pixels1, pixels2):
            r1, g1, b1 = p1[0], p1[1], p1[2]
            r2, g2, b2 = p2[0], p2[1], p2[2]
            if abs(r1 - r2) <= 2 and abs(g1 - g2) <= 2 and abs(b1 - b2) <= 2:
                matching += 1
                continue
            if _color_delta_e((r1, g1, b1), (r2, g2, b2)) <= _PIXEL_DELTA_E_THRESHOLD:
                matching += 1

        ratio = matching / len(pixels1)
        return {
            "pixel_match_ratio": round(ratio, 4),
            "dimension_match": dimension_match,
            "method": "pillow_deltaE",
        }

    except ImportError:
        # Pillow not installed — do size-only comparison
        try:
            s1 = dom_shot_path.stat().st_size
            s2 = figma_shot_path.stat().st_size
            # Heuristic: file sizes within 20% suggest similar content
            if s2 > 0:
                ratio = min(s1, s2) / max(s1, s2)
                return {"pixel_match_ratio": round(ratio, 4), "dimension_match": True, "method": "size_only"}
        except Exception:
            pass
        return {"pixel_match_ratio": 0.0, "dimension_match": False, "method": "size_only"}

    except Exception as exc:
        print(f"[ElemCap] Pixel comparison error: {exc}", flush=True)
        return {"pixel_match_ratio": 0.0, "dimension_match": False, "method": "error"}


# ---------------------------------------------------------------------------
# Full element-level comparison pipeline
# ---------------------------------------------------------------------------

async def run_element_comparison(
    port: int,
    design_data: dict,
    screenshots_dir: Path,
    figma_token: str = "",
    file_key: str = "",
    viewport: Optional[Dict[str, int]] = None,
) -> dict:
    """
    Run the full element-level screenshot comparison pipeline.

    1. Capture DOM element screenshots
    2. Optionally export Figma node images (if token + file_key available)
    3. Compare dimensions (always) and pixels (if Figma images available)

    Args:
        port: Running dev server port.
        design_data: Figma design data.
        screenshots_dir: Directory for saving screenshots.
        figma_token: Figma API token (optional — enables Figma export).
        file_key: Figma file key (optional — enables Figma export).

    Returns:
        {
            "element_count": int,
            "elements": [...per-element results...],
            "overall_dimension_accuracy": float,
            "overall_pixel_accuracy": float | None,
            "screenshots_dir": str,
        }
    """
    dom_dir = screenshots_dir / "dom_elements"
    figma_dir = screenshots_dir / "figma_elements"

    # Step 1: Capture DOM element screenshots
    print("[ElemCap] Capturing DOM element screenshots...", flush=True)
    dom_elements = await capture_element_screenshots(port, dom_dir, viewport=viewport)

    if not dom_elements:
        print("[ElemCap] No elements with data-figma-id found — skipping element comparison", flush=True)
        return {
            "element_count": 0,
            "elements": [],
            "overall_dimension_accuracy": 0.0,
            "overall_pixel_accuracy": None,
            "screenshots_dir": str(screenshots_dir),
        }

    # Step 2: Extract Figma props for dimension comparison
    from backend.utils.structural_comparison import _extract_figma_properties
    figma_props = _extract_figma_properties(design_data)

    # Step 3: Compare dimensions
    dimension_results = compare_element_dimensions(dom_elements, figma_props)

    # Step 4: Export Figma node images and compare pixels (if API access available)
    figma_images: Dict[str, Path] = {}
    if figma_token and file_key:
        try:
            figma_images = await export_figma_node_images(
                design_data=design_data,
                figma_token=figma_token,
                file_key=file_key,
                output_dir=figma_dir,
            )
            print(f"[ElemCap] Exported {len(figma_images)} Figma node images", flush=True)
        except Exception as exc:
            print(f"[ElemCap] Failed to export Figma images: {exc}", flush=True)

    # Step 5: Build per-element results
    elements = []
    dim_scores = []
    pixel_scores = []

    for dim_result in dimension_results:
        figma_id = dim_result["figma_id"]
        entry = dict(dim_result)

        # Add pixel comparison if Figma image available
        if figma_id in figma_images and dim_result.get("screenshot_path"):
            dom_path = Path(dim_result["screenshot_path"])
            figma_path = figma_images[figma_id]
            if dom_path.exists() and figma_path.exists():
                pixel_result = compare_element_pixels(dom_path, figma_path)
                entry["pixel_comparison"] = pixel_result
                pixel_scores.append(pixel_result["pixel_match_ratio"])

        # Compute element accuracy
        w_ok = entry.get("width_match", True)
        h_ok = entry.get("height_match", True)
        dim_score = 1.0 if (w_ok and h_ok) else (0.5 if (w_ok or h_ok) else 0.0)
        entry["dimension_score"] = dim_score
        dim_scores.append(dim_score)

        elements.append(entry)

    overall_dim = sum(dim_scores) / len(dim_scores) if dim_scores else 0.0
    overall_pixel = sum(pixel_scores) / len(pixel_scores) if pixel_scores else None

    print(
        f"[ElemCap] Element comparison complete: {len(elements)} elements, "
        f"dim_accuracy={overall_dim:.2%}"
        + (f", pixel_accuracy={overall_pixel:.2%}" if overall_pixel is not None else ""),
        flush=True,
    )

    return {
        "element_count": len(elements),
        "elements": elements,
        "overall_dimension_accuracy": round(overall_dim, 4),
        "overall_pixel_accuracy": round(overall_pixel, 4) if overall_pixel is not None else None,
        "screenshots_dir": str(screenshots_dir),
    }
