"""Structural comparison: compares Figma design properties against rendered DOM computed styles."""

import asyncio
import json
import math
import platform
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.config import settings
from backend.utils import get_npx_command


# ---------------------------------------------------------------------------
# JavaScript snippet executed inside the browser via Playwright CLI
# ---------------------------------------------------------------------------

_DOM_EXTRACTION_JS = r"""
(() => {
  const elements = document.querySelectorAll('[data-figma-id]');
  const results = {};

  elements.forEach(el => {
    const figmaId = el.getAttribute('data-figma-id');
    const cs = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();

    results[figmaId] = {
      // Dimensions
      width: rect.width,
      height: rect.height,
      // Padding
      paddingTop: parseFloat(cs.paddingTop) || 0,
      paddingRight: parseFloat(cs.paddingRight) || 0,
      paddingBottom: parseFloat(cs.paddingBottom) || 0,
      paddingLeft: parseFloat(cs.paddingLeft) || 0,
      // Margin
      marginTop: parseFloat(cs.marginTop) || 0,
      marginRight: parseFloat(cs.marginRight) || 0,
      marginBottom: parseFloat(cs.marginBottom) || 0,
      marginLeft: parseFloat(cs.marginLeft) || 0,
      // Colors
      backgroundColor: cs.backgroundColor,
      color: cs.color,
      // Typography
      fontSize: parseFloat(cs.fontSize) || 0,
      fontWeight: cs.fontWeight,
      fontFamily: cs.fontFamily,
      lineHeight: cs.lineHeight,
      letterSpacing: cs.letterSpacing,
      // Border radius
      borderRadius: cs.borderRadius,
      // Shadow
      boxShadow: cs.boxShadow,
      // Borders
      borderTopWidth: parseFloat(cs.borderTopWidth) || 0,
      borderTopColor: cs.borderTopColor,
      borderTopStyle: cs.borderTopStyle,
      // Opacity
      opacity: parseFloat(cs.opacity !== undefined ? cs.opacity : 1),
      // Flex / layout
      gap: parseFloat(cs.gap) || 0,
      display: cs.display,
      flexDirection: cs.flexDirection,
      alignItems: cs.alignItems,
      justifyContent: cs.justifyContent,
      // Text
      textAlign: cs.textAlign,
    };
  });

  // CSS Custom Properties from :root (design tokens)
  const customProps = {};
  try {
    for (const sheet of document.styleSheets) {
      try {
        for (const rule of sheet.cssRules) {
          if (rule.selectorText === ':root') {
            for (const prop of rule.style) {
              if (prop.startsWith('--')) {
                customProps[prop] = rule.style.getPropertyValue(prop).trim();
              }
            }
          }
        }
      } catch(e) { /* cross-origin sheets throw */ }
    }
  } catch(e) {}

  return JSON.stringify({ elements: results, customProps: customProps });
})();
"""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def compare_structural_properties(
    port: int,
    design_data: dict,
    project_path: Path,
    viewport: Optional[Dict[str, int]] = None,
) -> dict:
    """Compare Figma design properties against rendered DOM computed styles.

    Args:
        port: Port number where the dev server is running.
        design_data: Complete Figma design data (from plugin or REST API).
        project_path: Path to the generated project.
        viewport: Optional {width, height} to use for Playwright. If None,
                  auto-detected from the Figma root frame dimensions.

    Returns:
        Structured report with per-property checks, per-element screenshots, and aggregate scores.
    """
    print("[Structural] Starting structural comparison...", flush=True)

    # 1. Extract Figma node properties and detect root frame IDs
    figma_props = _extract_figma_properties(design_data)
    if not figma_props:
        print("[Structural] No Figma nodes found in design data", flush=True)
        return _empty_result()

    root_frame_ids = _detect_root_frame_ids(design_data)
    if root_frame_ids:
        print(f"[Structural] Root frames (skipped): {root_frame_ids}", flush=True)

    # Auto-detect viewport from root frame if not explicitly provided
    if viewport is None:
        viewport = _get_design_viewport(design_data)
    print(f"[Structural] Viewport: {viewport['width']}x{viewport['height']}", flush=True)

    # 2. Extract DOM computed styles via Playwright subprocess
    dom_extraction = await _extract_dom_properties(port, viewport=viewport)
    dom_props = dom_extraction.get("elements", dom_extraction) if isinstance(dom_extraction, dict) and "elements" in dom_extraction else dom_extraction
    css_custom_props = dom_extraction.get("customProps", {}) if isinstance(dom_extraction, dict) and "customProps" in dom_extraction else {}

    if not dom_props:
        print("[Structural] No data-figma-id elements found in DOM — skipping structural comparison", flush=True)
        return _empty_result()

    if css_custom_props:
        print(f"[Structural] Found {len(css_custom_props)} CSS custom properties (design tokens)", flush=True)

    print(f"[Structural] Found {len(dom_props)} DOM elements with data-figma-id", flush=True)

    # 3. Compare
    tolerance_px = settings.structural_comparison_tolerance_px
    # delta_e threshold: ΔE2000 < 3.0 is "acceptable" for design verification
    delta_e_threshold = 3.0

    property_checks = _compare_properties(figma_props, dom_props, tolerance_px, delta_e_threshold, root_frame_ids=root_frame_ids)

    if not property_checks:
        print("[Structural] No matching elements to compare", flush=True)
        return _empty_result()

    # 4. Aggregate scores by category
    # Exclude "mapping" issues (info-only) from pass/fail scoring
    scorable_checks = [c for c in property_checks if c.get("category") != "mapping"]
    mapping_issues = [c for c in property_checks if c.get("category") == "mapping"]

    if mapping_issues:
        print(
            f"[Structural] ⚠ {len(mapping_issues)} element(s) have data-figma-id on wrong DOM element (skipped from scoring)",
            flush=True,
        )

    total = len(scorable_checks)
    passed = sum(1 for c in scorable_checks if c["match"])
    confidence = passed / total if total > 0 else 0.0

    # Category-specific accuracy (grouped by property category)
    dimension_checks = [c for c in scorable_checks if c["category"] == "dimension"]
    color_checks = [c for c in scorable_checks if c["category"] == "color"]
    spacing_checks = [c for c in scorable_checks if c["category"] == "spacing"]
    typography_checks = [c for c in scorable_checks if c["category"] == "typography"]
    effects_checks = [c for c in scorable_checks if c["category"] == "effects"]

    def _accuracy(checks: list) -> float:
        return sum(1 for c in checks if c["match"]) / len(checks) if checks else 1.0

    dimension_accuracy = _accuracy(dimension_checks)
    color_accuracy = _accuracy(color_checks)
    spacing_accuracy = _accuracy(spacing_checks)
    typography_accuracy = _accuracy(typography_checks)
    effects_accuracy = _accuracy(effects_checks)

    # Build per-element summary (group checks by element)
    element_summaries = _build_element_summaries(property_checks)

    result = {
        "matches": confidence > 0.9,
        "confidence": round(confidence, 4),
        "total_checks": total,
        "css_custom_props": css_custom_props,
        "passed_checks": passed,
        "property_checks": property_checks,
        "element_summaries": element_summaries,
        "dimension_accuracy": round(dimension_accuracy, 4),
        "color_accuracy": round(color_accuracy, 4),
        "spacing_accuracy": round(spacing_accuracy, 4),
        "typography_accuracy": round(typography_accuracy, 4),
        "effects_accuracy": round(effects_accuracy, 4),
    }

    print(
        f"[Structural] Confidence: {confidence:.2%} ({passed}/{total} checks passed)\n"
        f"  dims={dimension_accuracy:.2%}, colors={color_accuracy:.2%}, "
        f"spacing={spacing_accuracy:.2%}, typo={typography_accuracy:.2%}, effects={effects_accuracy:.2%}",
        flush=True,
    )

    # Log top mismatches
    failures = [c for c in property_checks if not c["match"] and c["severity"] == "high"]
    if failures:
        print(f"[Structural] Top {min(5, len(failures))} high-severity mismatches:", flush=True)
        for f in failures[:5]:
            print(
                f"  ✗ [{f['element']}] {f['property']}: "
                f"expected={f['figma_value']} actual={f['dom_value']}",
                flush=True,
            )

    return result


# ---------------------------------------------------------------------------
# Figma property extraction
# ---------------------------------------------------------------------------

def _extract_figma_properties(design_data: dict) -> Dict[str, dict]:
    """Walk the Figma design tree and collect node properties keyed by node ID."""
    props: Dict[str, dict] = {}

    def _walk(node: dict):
        node_id = node.get("id", "")
        if not node_id:
            for child in node.get("children", []):
                _walk(child)
            return

        entry: Dict[str, Any] = {
            "name": node.get("name", ""),
            "nodeType": node.get("type", ""),
        }

        # Design tokens (Figma Variables / named Styles)
        if node.get("designTokens"):
            entry["designTokens"] = node["designTokens"]

        # Bounds / dimensions
        layout = node.get("layout", {})
        bounds = layout.get("bounds", {})
        if bounds:
            entry["width"] = bounds.get("width")
            entry["height"] = bounds.get("height")

        # Padding (from auto-layout)
        padding = layout.get("padding", {})
        if padding:
            entry["paddingTop"] = padding.get("top", 0)
            entry["paddingRight"] = padding.get("right", 0)
            entry["paddingBottom"] = padding.get("bottom", 0)
            entry["paddingLeft"] = padding.get("left", 0)

        # Item spacing → gap
        if layout.get("itemSpacing") is not None:
            entry["gap"] = layout["itemSpacing"]

        # Layout mode → flex direction
        mode = layout.get("mode")
        if mode:
            entry["flexDirection"] = "column" if mode == "VERTICAL" else "row"

        # Fills → background color or text color
        fills = node.get("fills", [])
        for fill in fills:
            if fill.get("type") == "SOLID":
                color_val = fill.get("color")
                if isinstance(color_val, dict):
                    r = int(color_val.get("r", 0) * 255)
                    g = int(color_val.get("g", 0) * 255)
                    b = int(color_val.get("b", 0) * 255)
                    if node.get("type") == "TEXT":
                        entry["color"] = (r, g, b)
                    else:
                        entry["backgroundColor"] = (r, g, b)
                elif isinstance(color_val, str) and color_val.startswith("#"):
                    rgb = _hex_to_rgb(color_val)
                    if node.get("type") == "TEXT":
                        entry["color"] = rgb
                    else:
                        entry["backgroundColor"] = rgb

        # Text style
        style = node.get("style", {})
        if style:
            if style.get("fontSize"):
                entry["fontSize"] = float(style["fontSize"])
            if style.get("fontWeight"):
                entry["fontWeight"] = str(int(style["fontWeight"]))
            if style.get("fontFamily"):
                entry["fontFamily"] = style["fontFamily"]
            # Line height — prefer px value, fall back to percent/auto
            lh = style.get("lineHeightPx")
            if lh:
                entry["lineHeightPx"] = float(lh)
            elif style.get("lineHeightUnit") == "FONT_SIZE_PERCENT":
                pct = style.get("lineHeightPercent", 0)
                fs = style.get("fontSize")
                if pct and fs:
                    entry["lineHeightPx"] = float(fs) * float(pct) / 100.0
            # Letter spacing (Figma stores it in em/100 or px depending on unit)
            ls = style.get("letterSpacing")
            ls_unit = style.get("letterSpacingUnit", "PIXELS")
            if ls is not None:
                if ls_unit == "PERCENT" and style.get("fontSize"):
                    # Convert % of font-size to px
                    entry["letterSpacingPx"] = float(ls) / 100.0 * float(style["fontSize"])
                else:
                    entry["letterSpacingPx"] = float(ls)

        # Opacity
        opacity = node.get("opacity")
        if opacity is not None and opacity < 1.0:
            entry["opacity"] = float(opacity)

        # Corner radius
        radius = node.get("cornerRadius")
        if isinstance(radius, (int, float)) and radius:
            entry["borderRadius"] = float(radius)
        elif isinstance(radius, dict) and radius:
            if "all" in radius:
                entry["borderRadius"] = float(radius["all"])
            else:
                vals = [
                    radius.get("topLeft", 0),
                    radius.get("topRight", 0),
                    radius.get("bottomLeft", 0),
                    radius.get("bottomRight", 0),
                ]
                entry["borderRadius"] = float(max(vals)) if any(v > 0 for v in vals) else 0.0

        # Strokes → border
        strokes = node.get("strokes", [])
        stroke_weight = node.get("strokeWeight")
        if strokes and stroke_weight:
            for stroke in strokes:
                if stroke.get("type") == "SOLID":
                    color_val = stroke.get("color")
                    if isinstance(color_val, dict):
                        r = int(color_val.get("r", 0) * 255)
                        g = int(color_val.get("g", 0) * 255)
                        b = int(color_val.get("b", 0) * 255)
                        entry["borderColor"] = (r, g, b)
                    entry["borderWidth"] = float(stroke_weight)

        # Effects (shadow)
        effects = node.get("effects", [])
        for effect in effects:
            if effect.get("type") in ("DROP_SHADOW", "INNER_SHADOW"):
                entry["hasBoxShadow"] = True

        props[node_id] = entry

        # Recurse
        for child in node.get("children", []):
            _walk(child)

    pages = design_data.get("pages", [])
    for page in pages:
        for frame in page.get("frames", []):
            _walk(frame)

    return props


# ---------------------------------------------------------------------------
# DOM property extraction via Playwright subprocess
# ---------------------------------------------------------------------------

async def _extract_dom_properties(
    port: int,
    viewport: Optional[Dict[str, int]] = None,
) -> Dict[str, dict]:
    """Run Playwright in a subprocess to extract computed styles from the page."""
    vp = viewport or {"width": 1440, "height": 900}
    url = f"http://localhost:{port}"

    node_script = (
        "const { chromium } = require('playwright');\n\n"
        "(async () => {\n"
        "  const browser = await chromium.launch({ headless: true });\n"
        f"  const page = await browser.newPage({{ viewport: {{ width: {vp['width']}, height: {vp['height']} }} }});\n"
        "  try {\n"
        "    await page.goto('" + url + "', { waitUntil: 'networkidle', timeout: 30000 });\n"
        "    await page.waitForTimeout(1000);\n"
        "    const result = await page.evaluate(() => {\n"
        "      return " + _DOM_EXTRACTION_JS.strip() + "\n"
        "    });\n"
        "    process.stdout.write(result);\n"
        "  } catch (err) {\n"
        "    process.stderr.write('Error: ' + err.message);\n"
        "    process.exit(1);\n"
        "  } finally {\n"
        "    await browser.close();\n"
        "  }\n"
        "})();\n"
    )

    # Write script INTO the project root so Node.js require() walks up and
    # finds node_modules/playwright (system temp is outside the project tree).
    project_root = Path(__file__).resolve().parents[2]
    import os
    script_path = project_root / f"_aura2_structural_{os.getpid()}_{time.time_ns()}.cjs"
    script_path.write_text(node_script, encoding="utf-8")

    try:
        use_shell = platform.system() == "Windows"
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                ["node", str(script_path)],
                capture_output=True,
                text=True,
                timeout=45,
                shell=use_shell,
            ),
        )

        if result.returncode != 0:
            print(f"[Structural] Playwright script failed: {result.stderr[:500]}", flush=True)
            return {}

        raw = result.stdout.strip()
        if not raw:
            return {}

        dom_data: dict = json.loads(raw)
        return dom_data

    except subprocess.TimeoutExpired:
        print("[Structural] Playwright script timed out", flush=True)
        return {}
    except json.JSONDecodeError as exc:
        print(f"[Structural] Failed to parse DOM extraction JSON: {exc}", flush=True)
        return {}
    except Exception as exc:
        print(f"[Structural] Error extracting DOM properties: {exc}", flush=True)
        return {}
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Property comparison
# ---------------------------------------------------------------------------

def _compare_properties(
    figma_props: Dict[str, dict],
    dom_props: Dict[str, dict],
    tolerance_px: int = 2,
    delta_e_threshold: float = 3.0,
    root_frame_ids: Optional[set] = None,
) -> List[dict]:
    """Compare matched Figma/DOM elements and return per-property check results."""
    checks: List[dict] = []
    skip_ids = root_frame_ids or set()

    for figma_id, dom_vals in dom_props.items():
        figma_vals = figma_props.get(figma_id)
        if figma_vals is None:
            continue

        # Skip root frames — they represent Figma artboards/canvases,
        # not individual DOM elements
        if figma_id in skip_ids:
            continue

        element_name = figma_vals.get("name", figma_id)

        # Detect severe mapping mismatch — flag when the data-figma-id
        # is probably on the wrong DOM element.
        #
        # Width is lenient (3x) because responsive layouts legitimately
        # stretch elements (e.g. 200px card → 600px on wider viewport).
        # Height is stricter (5x) since vertical size rarely changes that much.
        # Both must exceed threshold to be flagged — a single axis mismatch
        # can happen in legitimate responsive scenarios.
        mapping_suspect = False
        fw = figma_vals.get("width")
        fh = figma_vals.get("height")
        dw = dom_vals.get("width", 0)
        dh = dom_vals.get("height", 0)
        w_ratio = max(fw, dw) / max(min(fw, dw), 1) if fw and dw else 1
        h_ratio = max(fh, dh) / max(min(fh, dh), 1) if fh and dh else 1
        # Flag only when BOTH axes are severely off, or height alone is extreme
        if (w_ratio > 3 and h_ratio > 3) or h_ratio > 8:
            mapping_suspect = True

        if mapping_suspect:
            checks.append({
                "element": element_name,
                "figma_id": figma_id,
                "property": "element-mapping",
                "category": "mapping",
                "figma_value": f"{fw:.0f}x{fh:.0f}px" if fw and fh else "?",
                "dom_value": f"{dw:.0f}x{dh:.0f}px",
                "match": False,
                "severity": "info",
                "note": "data-figma-id appears to be on the wrong DOM element (>5x size difference)",
            })
            continue  # Skip property-level checks for mismatched elements

        # --- Dimensions (skip for TEXT nodes) ---
        # TEXT node dimensions depend entirely on browser font rendering and
        # are never fixable via CSS — comparing them adds noise without value.
        # Only FRAME/GROUP/COMPONENT containers have CSS-controlled dimensions.
        is_text_node = figma_vals.get("nodeType") == "TEXT"

        if not is_text_node:
            if figma_vals.get("width") is not None:
                checks.append(_check_numeric(
                    element_name, figma_id, "width", "dimension",
                    figma_vals["width"], dom_vals.get("width", 0),
                    tolerance_px, "high",
                ))

            if figma_vals.get("height") is not None:
                checks.append(_check_numeric(
                    element_name, figma_id, "height", "dimension",
                    figma_vals["height"], dom_vals.get("height", 0),
                    tolerance_px, "high",
                ))

        # --- Padding (medium severity, category: spacing) ---
        for side in ("Top", "Right", "Bottom", "Left"):
            key = f"padding{side}"
            if figma_vals.get(key) is not None:
                checks.append(_check_numeric(
                    element_name, figma_id, f"padding-{side.lower()}", "spacing",
                    figma_vals[key], dom_vals.get(key, 0),
                    tolerance_px, "medium",
                ))

        # --- Gap (medium severity, category: spacing) ---
        if figma_vals.get("gap") is not None:
            checks.append(_check_numeric(
                element_name, figma_id, "gap", "spacing",
                figma_vals["gap"], dom_vals.get("gap", 0),
                tolerance_px, "medium",
            ))

        # Resolve design tokens for this element
        tokens = figma_vals.get("designTokens", {})

        # --- Background color (high severity, category: color) ---
        if figma_vals.get("backgroundColor") is not None:
            dom_bg = _parse_css_color(dom_vals.get("backgroundColor", ""))
            if dom_bg is not None:
                delta_e = _color_delta_e(figma_vals["backgroundColor"], dom_bg)
                match = delta_e <= delta_e_threshold
                check_entry = {
                    "element": element_name,
                    "figma_id": figma_id,
                    "property": "background-color",
                    "category": "color",
                    "figma_value": _rgb_to_hex(figma_vals["backgroundColor"]),
                    "dom_value": _rgb_to_hex(dom_bg),
                    "delta_e": round(delta_e, 2),
                    "match": match,
                    "severity": "high",
                }
                # Add token reference if available
                fill_token = tokens.get("fill") or tokens.get("fills")
                if fill_token:
                    check_entry["design_token"] = fill_token
                checks.append(check_entry)

        # --- Text color (high severity, category: color) ---
        if figma_vals.get("color") is not None:
            dom_color = _parse_css_color(dom_vals.get("color", ""))
            if dom_color is not None:
                delta_e = _color_delta_e(figma_vals["color"], dom_color)
                match = delta_e <= delta_e_threshold
                checks.append({
                    "element": element_name,
                    "figma_id": figma_id,
                    "property": "color",
                    "category": "color",
                    "figma_value": _rgb_to_hex(figma_vals["color"]),
                    "dom_value": _rgb_to_hex(dom_color),
                    "delta_e": round(delta_e, 2),
                    "match": match,
                    "severity": "high",
                })

        # --- Border color (medium severity, category: color) ---
        if figma_vals.get("borderColor") is not None:
            dom_border_color = _parse_css_color(dom_vals.get("borderTopColor", ""))
            if dom_border_color is not None:
                delta_e = _color_delta_e(figma_vals["borderColor"], dom_border_color)
                match = delta_e <= delta_e_threshold
                checks.append({
                    "element": element_name,
                    "figma_id": figma_id,
                    "property": "border-color",
                    "category": "color",
                    "figma_value": _rgb_to_hex(figma_vals["borderColor"]),
                    "dom_value": _rgb_to_hex(dom_border_color),
                    "delta_e": round(delta_e, 2),
                    "match": match,
                    "severity": "medium",
                })

        # --- Font size (high severity, category: typography) ---
        if figma_vals.get("fontSize") is not None:
            checks.append(_check_numeric(
                element_name, figma_id, "font-size", "typography",
                figma_vals["fontSize"], dom_vals.get("fontSize", 0),
                1, "high",
            ))

        # --- Font weight (high severity, category: typography) ---
        if figma_vals.get("fontWeight") is not None:
            figma_fw = str(figma_vals["fontWeight"])
            dom_fw = str(dom_vals.get("fontWeight", ""))
            checks.append({
                "element": element_name,
                "figma_id": figma_id,
                "property": "font-weight",
                "category": "typography",
                "figma_value": figma_fw,
                "dom_value": dom_fw,
                "match": figma_fw == dom_fw,
                "severity": "high",
            })

        # --- Line height (medium severity, category: typography) ---
        if figma_vals.get("lineHeightPx") is not None:
            dom_lh_str = dom_vals.get("lineHeight", "normal")
            dom_lh = _parse_first_px(str(dom_lh_str))
            if dom_lh is not None:
                checks.append(_check_numeric(
                    element_name, figma_id, "line-height", "typography",
                    figma_vals["lineHeightPx"], dom_lh,
                    2, "medium",
                ))

        # --- Letter spacing (low severity, category: typography) ---
        if figma_vals.get("letterSpacingPx") is not None:
            dom_ls_str = dom_vals.get("letterSpacing", "normal")
            if dom_ls_str != "normal":
                dom_ls = _parse_first_px(str(dom_ls_str))
                if dom_ls is not None:
                    checks.append(_check_numeric(
                        element_name, figma_id, "letter-spacing", "typography",
                        figma_vals["letterSpacingPx"], dom_ls,
                        0.5, "low",
                    ))

        # --- Border radius (low severity, category: effects) ---
        if figma_vals.get("borderRadius") is not None and figma_vals["borderRadius"] > 0:
            dom_br_str = dom_vals.get("borderRadius", "0px")
            dom_br = _parse_first_px(str(dom_br_str)) or 0.0
            checks.append(_check_numeric(
                element_name, figma_id, "border-radius", "effects",
                figma_vals["borderRadius"], dom_br,
                tolerance_px, "low",
            ))

        # --- Border width (medium severity, category: effects) ---
        if figma_vals.get("borderWidth") is not None and figma_vals["borderWidth"] > 0:
            dom_bw = dom_vals.get("borderTopWidth", 0)
            checks.append(_check_numeric(
                element_name, figma_id, "border-width", "effects",
                figma_vals["borderWidth"], dom_bw,
                1, "medium",
            ))

        # --- Box shadow presence (low severity, category: effects) ---
        if figma_vals.get("hasBoxShadow"):
            dom_shadow = dom_vals.get("boxShadow", "none")
            has_shadow = bool(dom_shadow and dom_shadow != "none")
            checks.append({
                "element": element_name,
                "figma_id": figma_id,
                "property": "box-shadow",
                "category": "effects",
                "figma_value": "present",
                "dom_value": "present" if has_shadow else "none",
                "match": has_shadow,
                "severity": "low",
            })

        # --- Opacity (medium severity, category: effects) ---
        if figma_vals.get("opacity") is not None:
            dom_opacity = float(dom_vals.get("opacity", 1.0))
            figma_opacity = figma_vals["opacity"]
            match = abs(figma_opacity - dom_opacity) <= 0.05
            checks.append({
                "element": element_name,
                "figma_id": figma_id,
                "property": "opacity",
                "category": "effects",
                "figma_value": f"{figma_opacity:.2f}",
                "dom_value": f"{dom_opacity:.2f}",
                "match": match,
                "severity": "medium",
            })

        # --- Flex direction (high severity, category: dimension) ---
        if figma_vals.get("flexDirection") is not None:
            dom_display = dom_vals.get("display", "")
            dom_fd = dom_vals.get("flexDirection", "")
            is_flex = "flex" in dom_display
            if is_flex:
                match = dom_fd == figma_vals["flexDirection"]
            else:
                match = False
            checks.append({
                "element": element_name,
                "figma_id": figma_id,
                "property": "flex-direction",
                "category": "dimension",
                "figma_value": figma_vals["flexDirection"],
                "dom_value": dom_fd if is_flex else f"(display: {dom_display})",
                "match": match,
                "severity": "high",
            })

    return checks


# ---------------------------------------------------------------------------
# Root frame detection (structural, not heuristic)
# ---------------------------------------------------------------------------

def _detect_root_frame_ids(design_data: dict) -> set:
    """Detect root frame IDs from the Figma design tree structure.

    Top-level frames directly under pages represent Figma artboards / canvases.
    These should never be compared against individual DOM elements because they
    represent the full page, not a component.

    Works for any design — single page, multi-page, mobile, desktop, etc.
    """
    root_ids: set = set()
    for page in design_data.get("pages", []):
        for frame in page.get("frames", []):
            fid = frame.get("id", "")
            if fid:
                root_ids.add(fid)
    return root_ids


def _get_design_viewport(design_data: dict) -> Dict[str, int]:
    """Extract viewport dimensions from the Figma root frame.

    Uses the first root frame's bounds as the intended viewport.
    Falls back to 1440x900 if no bounds are found.

    This handles mobile (375px), tablet (768px), desktop (1440px),
    and any custom canvas size. Clamped to 3840px max to avoid
    Playwright allocating multi-gigabyte framebuffers.
    """
    MAX_VP = 3840  # Playwright struggles above ~16384; 4K is a safe upper bound
    for page in design_data.get("pages", []):
        for frame in page.get("frames", []):
            bounds = frame.get("layout", {}).get("bounds", {})
            w = bounds.get("width")
            h = bounds.get("height")
            if w and h and w > 0 and h > 0:
                return {"width": min(int(w), MAX_VP), "height": min(int(h), MAX_VP)}
    # Fallback for designs without bounds data
    return {"width": 1440, "height": 900}


# ---------------------------------------------------------------------------

def _build_element_summaries(property_checks: List[dict]) -> List[dict]:
    """Group property checks by element and compute per-element pass rate."""
    by_element: Dict[str, dict] = {}

    for check in property_checks:
        eid = check["figma_id"]
        if eid not in by_element:
            by_element[eid] = {
                "element": check["element"],
                "figma_id": eid,
                "total": 0,
                "passed": 0,
                "failures": [],
            }
        by_element[eid]["total"] += 1
        if check["match"]:
            by_element[eid]["passed"] += 1
        else:
            by_element[eid]["failures"].append({
                "property": check["property"],
                "severity": check["severity"],
                "expected": check["figma_value"],
                "actual": check["dom_value"],
            })

    summaries = []
    for eid, data in by_element.items():
        total = data["total"]
        passed = data["passed"]
        summaries.append({
            "element": data["element"],
            "figma_id": eid,
            "accuracy": round(passed / total, 4) if total > 0 else 1.0,
            "passed": passed,
            "total": total,
            "failures": data["failures"],
        })

    # Sort by accuracy ascending (worst elements first)
    summaries.sort(key=lambda x: x["accuracy"])
    return summaries


# ---------------------------------------------------------------------------
# ΔE2000 perceptual color comparison
# ---------------------------------------------------------------------------

def _rgb_to_lab(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """Convert RGB (0-255) to CIE L*a*b* color space (D65 illuminant)."""
    # Normalize to [0, 1]
    r, g, b = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0

    # Gamma correction: sRGB → linear
    def _linearize(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _linearize(r), _linearize(g), _linearize(b)

    # Linear RGB → XYZ (D65)
    X = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    Y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    Z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041

    # Normalize by D65 white point
    X /= 0.95047
    Y /= 1.00000
    Z /= 1.08883

    # XYZ → Lab
    def _f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else (7.787 * t) + (16.0 / 116.0)

    L = 116.0 * _f(Y) - 16.0
    a = 500.0 * (_f(X) - _f(Y))
    b_ = 200.0 * (_f(Y) - _f(Z))

    return (L, a, b_)


def _delta_e_2000(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
    """Compute ΔE2000 perceptual color difference between two CIE Lab colors.

    Returns a value where:
      < 1.0  → imperceptible difference
      1–2    → slight difference
      2–3    → noticeable difference
      > 3    → clearly visible difference
    """
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    C1 = math.sqrt(a1 ** 2 + b1 ** 2)
    C2 = math.sqrt(a2 ** 2 + b2 ** 2)
    C_avg = (C1 + C2) / 2.0
    C_avg_7 = C_avg ** 7
    _25_7 = 25.0 ** 7
    G = 0.5 * (1.0 - math.sqrt(C_avg_7 / (C_avg_7 + _25_7)))

    a1p = a1 * (1.0 + G)
    a2p = a2 * (1.0 + G)
    C1p = math.sqrt(a1p ** 2 + b1 ** 2)
    C2p = math.sqrt(a2p ** 2 + b2 ** 2)

    def _hprime(bp: float, ap: float) -> float:
        if ap == 0.0 and bp == 0.0:
            return 0.0
        h = math.degrees(math.atan2(bp, ap))
        return h + 360.0 if h < 0 else h

    h1p = _hprime(b1, a1p)
    h2p = _hprime(b2, a2p)

    dLp = L2 - L1
    dCp = C2p - C1p

    if C1p * C2p == 0.0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180.0:
        dhp = h2p - h1p
    elif h2p - h1p > 180.0:
        dhp = h2p - h1p - 360.0
    else:
        dhp = h2p - h1p + 360.0

    dHp = 2.0 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2.0))

    Lp_avg = (L1 + L2) / 2.0
    Cp_avg = (C1p + C2p) / 2.0

    if C1p * C2p == 0.0:
        hp_avg = h1p + h2p
    elif abs(h1p - h2p) <= 180.0:
        hp_avg = (h1p + h2p) / 2.0
    elif h1p + h2p < 360.0:
        hp_avg = (h1p + h2p + 360.0) / 2.0
    else:
        hp_avg = (h1p + h2p - 360.0) / 2.0

    T = (1.0
         - 0.17 * math.cos(math.radians(hp_avg - 30.0))
         + 0.24 * math.cos(math.radians(2.0 * hp_avg))
         + 0.32 * math.cos(math.radians(3.0 * hp_avg + 6.0))
         - 0.20 * math.cos(math.radians(4.0 * hp_avg - 63.0)))

    Lp50sq = (Lp_avg - 50.0) ** 2
    SL = 1.0 + 0.015 * Lp50sq / math.sqrt(20.0 + Lp50sq)
    SC = 1.0 + 0.045 * Cp_avg
    SH = 1.0 + 0.015 * Cp_avg * T

    Cp_avg_7 = Cp_avg ** 7
    RC = 2.0 * math.sqrt(Cp_avg_7 / (Cp_avg_7 + _25_7))
    d_theta = 30.0 * math.exp(-((hp_avg - 275.0) / 25.0) ** 2)
    RT = -math.sin(math.radians(2.0 * d_theta)) * RC

    # Guard against floating-point rounding pushing the sum slightly negative
    # (can happen with the negative RT rotation term for blue hues)
    return math.sqrt(max(0.0,
        (dLp / SL) ** 2
        + (dCp / SC) ** 2
        + (dHp / SH) ** 2
        + RT * (dCp / SC) * (dHp / SH)
    ))


def _color_delta_e(
    color1: Tuple[int, int, int],
    color2: Tuple[int, int, int],
) -> float:
    """Return the ΔE2000 perceptual difference between two RGB colors."""
    lab1 = _rgb_to_lab(color1)
    lab2 = _rgb_to_lab(color2)
    return _delta_e_2000(lab1, lab2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_numeric(
    element: str,
    figma_id: str,
    prop: str,
    category: str,
    figma_val: float,
    dom_val: float,
    tolerance: float,
    severity: str,
) -> dict:
    """Compare two numeric values with tolerance."""
    diff = abs(figma_val - dom_val)
    return {
        "element": element,
        "figma_id": figma_id,
        "property": prop,
        "category": category,
        "figma_value": f"{figma_val:.1f}px",
        "dom_value": f"{dom_val:.1f}px",
        "diff_px": round(diff, 2),
        "match": diff <= tolerance,
        "severity": severity,
    }


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to (R, G, B) tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    if len(hex_color) < 6:
        hex_color = hex_color.ljust(6, "0")
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert (R, G, B) tuple to hex string."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


# Matches legacy `rgb(255, 128, 0)` / `rgba(255, 128, 0, 1)`
_CSS_RGB_LEGACY_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
# Matches CSS Color Level 4 `rgb(255 128 0)` / `rgb(255 128 0 / 0.5)`
_CSS_RGB_L4_RE = re.compile(r"rgba?\(\s*(\d+)\s+(\d+)\s+(\d+)")
# Matches `color(srgb 1.0 0.5 0.0)` (normalized 0–1 floats)
_CSS_COLOR_SRGB_RE = re.compile(r"color\(\s*srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)")


def _parse_css_color(css_value: str) -> Optional[Tuple[int, int, int]]:
    """Parse CSS color value (rgb/rgba/hex/color(srgb)) into (R, G, B) tuple."""
    if not css_value:
        return None
    # Legacy comma-separated: rgb(R, G, B) / rgba(R, G, B, A)
    m = _CSS_RGB_LEGACY_RE.search(css_value)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # CSS Color Level 4 space-separated: rgb(R G B) / rgb(R G B / A)
    m = _CSS_RGB_L4_RE.search(css_value)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # color(srgb r g b) with normalized 0–1 floats
    m = _CSS_COLOR_SRGB_RE.search(css_value)
    if m:
        return (
            round(float(m.group(1)) * 255),
            round(float(m.group(2)) * 255),
            round(float(m.group(3)) * 255),
        )
    if css_value.startswith("#"):
        return _hex_to_rgb(css_value)
    return None


def _parse_first_px(value: str) -> Optional[float]:
    """Extract the first numeric px value from a CSS string.

    Returns None if no 'px' token is found (e.g. 'normal', '0', 'em' units),
    so callers can skip the check rather than compare against a bogus 0.0.
    """
    m = re.search(r"([\d.]+)px", str(value))
    return float(m.group(1)) if m else None


def _empty_result() -> dict:
    """Return an empty / no-op structural comparison result."""
    return {
        "matches": False,
        "confidence": 0.0,
        "total_checks": 0,
        "passed_checks": 0,
        "property_checks": [],
        "element_summaries": [],
        "dimension_accuracy": 0.0,
        "color_accuracy": 0.0,
        "spacing_accuracy": 0.0,
        "typography_accuracy": 0.0,
        "effects_accuracy": 0.0,
    }
