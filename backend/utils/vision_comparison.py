"""Vision-based comparison using Claude Vision API for pixel-perfect verification."""

import asyncio
import base64
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import anthropic
from backend.config import settings


async def compare_with_vision_api(
    figma_screenshot_path: Path,
    generated_screenshot_path: Path,
    design_data: dict,
    project_path: Optional[Path] = None,
    focus_areas: Optional[List[str]] = None,
) -> dict:
    """
    Use Claude Vision API to compare Figma design with generated output.

    Args:
        figma_screenshot_path: Path to Figma design screenshot/export
        generated_screenshot_path: Path to generated website screenshot
        design_data: Complete design data for context
        focus_areas: Optional list of areas to focus on (e.g., ["header", "hero"])

    Returns:
        {
            "matches": bool,
            "confidence": float,
            "discrepancies": [
                {
                    "type": "spacing",
                    "location": "Header section",
                    "severity": "high",
                    "expected": "24px padding",
                    "actual": "16px padding",
                    "coordinates": {"x": 100, "y": 50, "width": 200, "height": 80},
                    "fix": {
                        "file": "src/components/Header.tsx",
                        "change": "Update padding from 'p-4' to 'p-6'"
                    }
                }
            ],
            "layout_accuracy": 0.92,
            "color_accuracy": 0.98,
            "spacing_accuracy": 0.85,
            "visual_explanation": "The header has correct colors but padding is..."
        }
    """
    print("[Vision API] Starting pixel-perfect comparison...", flush=True)

    # Read and encode images
    figma_image_data = _encode_image(figma_screenshot_path)
    generated_image_data = _encode_image(generated_screenshot_path)

    if not figma_image_data or not generated_image_data:
        print("[Vision API] Failed to encode images", flush=True)
        return _fallback_result()

    # Collect component source code for context (if project_path available)
    source_code = ""
    if project_path:
        source_code = _collect_component_source(project_path)

    # Build comparison prompt
    prompt = _build_vision_comparison_prompt(design_data, focus_areas, source_code)

    # Call Claude Vision API
    try:
        client = anthropic.AsyncAnthropic(
            api_key=settings.litellm_api_key,
            base_url=settings.litellm_base_url if settings.litellm_base_url else None
        )

        print(f"[Vision API] Calling {settings.vision_comparison_model}...", flush=True)

        message = await client.messages.create(
            model=settings.vision_comparison_model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": figma_image_data,
                            },
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": generated_image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        # Parse response
        response_text = message.content[0].text
        print(f"[Vision API] Received response ({len(response_text)} chars)", flush=True)

        # Extract JSON from response
        result = _parse_vision_response(response_text)

        print(f"[Vision API] Confidence: {result['confidence']:.2f}, Matches: {result['matches']}", flush=True)
        print(f"[Vision API] Found {len(result['discrepancies'])} discrepancies", flush=True)

        return result

    except Exception as e:
        print(f"[Vision API] Error: {e}", flush=True)
        return _fallback_result()


def _encode_image(image_path: Path, max_raw_bytes: int = 3_700_000) -> Optional[str]:
    """Encode image to base64 for Vision API, resizing if needed.

    The Claude Vision API has a 5 MB (5,242,880 bytes) per-image limit on the
    **base64-encoded** payload.  Base64 expands data by ~33%, so a 3.7 MB raw
    file becomes ~4.9 MB base64 — safely under the limit.
    """
    try:
        raw = image_path.read_bytes()

        # If small enough, send as-is
        if len(raw) <= max_raw_bytes:
            return base64.standard_b64encode(raw).decode("utf-8")

        # Try resizing with Pillow
        try:
            from PIL import Image as _PILImage
            import io

            img = _PILImage.open(io.BytesIO(raw))
            # Shrink until under budget (halve each round)
            quality = 85
            for _ in range(5):
                w, h = img.size
                img = img.resize((w // 2, h // 2), _PILImage.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PNG", optimize=True)
                if buf.tell() <= max_raw_bytes:
                    print(f"[Vision API] Resized {image_path.name}: {len(raw)//1024}KB → {buf.tell()//1024}KB ({img.size[0]}x{img.size[1]})", flush=True)
                    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")
                # Try JPEG at lower quality if PNG is still too big
                buf2 = io.BytesIO()
                img.convert("RGB").save(buf2, format="JPEG", quality=quality)
                if buf2.tell() <= max_raw_bytes:
                    print(f"[Vision API] Resized {image_path.name} to JPEG: {len(raw)//1024}KB → {buf2.tell()//1024}KB", flush=True)
                    return base64.standard_b64encode(buf2.getvalue()).decode("utf-8")
                quality -= 10

            # Last resort: force small JPEG
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=50)
            print(f"[Vision API] Force-compressed {image_path.name}: {len(raw)//1024}KB → {buf.tell()//1024}KB", flush=True)
            return base64.standard_b64encode(buf.getvalue()).decode("utf-8")

        except ImportError:
            # No Pillow — just send raw and let it fail with a clear message
            print(f"[Vision API] Image {image_path.name} is {len(raw)//1024}KB (>{max_raw_bytes//1024}KB limit) and Pillow is not installed for resizing", flush=True)
            return base64.standard_b64encode(raw).decode("utf-8")

    except Exception as e:
        print(f"[Vision API] Failed to encode {image_path}: {e}", flush=True)
        return None


def _collect_component_source(project_path: Path, max_chars: int = 4000) -> str:
    """Collect generated component source code for vision comparison context.

    Reads entry points, component files, and CSS module files from common
    directory patterns (components/, pages/, views/, screens/).
    Truncated to stay within token budget.
    """
    files_to_read: List[Path] = []
    src = project_path / "src"

    # Entry points (prioritized)
    for entry in ("App.tsx", "App.jsx", "index.tsx", "index.jsx"):
        ep = src / entry
        if ep.exists():
            files_to_read.append(ep)
            break  # Only need one entry point

    # Component directories — check all common patterns
    component_dirs = ["components", "pages", "views", "screens", "sections"]
    for dir_name in component_dirs:
        comp_dir = src / dir_name
        if comp_dir.exists():
            for f in sorted(comp_dir.iterdir()):
                if f.is_file() and f.suffix in (".tsx", ".jsx", ".module.css"):
                    files_to_read.append(f)

    if not files_to_read:
        return ""

    # Budget chars per file
    per_file_limit = max(400, max_chars // len(files_to_read))
    parts: List[str] = []
    total = 0

    for fp in files_to_read:
        if total >= max_chars:
            break
        try:
            content = fp.read_text(encoding="utf-8")
            rel = fp.relative_to(project_path)
            truncated = content[:per_file_limit]
            if len(content) > per_file_limit:
                truncated += "\n// ... (truncated)"
            chunk = f"// {rel}\n{truncated}\n"
            parts.append(chunk)
            total += len(chunk)
        except Exception:
            continue

    return "\n".join(parts)


def _build_vision_comparison_prompt(design_data: dict, focus_areas: Optional[List[str]], source_code: str = "") -> str:
    """Build detailed prompt for Claude Vision API."""

    # Extract design context
    colors = [c.get("color", "") for c in design_data.get("colors", [])[:10]]
    fonts = [f.get("family", "") for f in design_data.get("fonts", [])]

    focus_section = ""
    if focus_areas:
        focus_section = f"\n**FOCUS AREAS:** Pay special attention to: {', '.join(focus_areas)}"

    source_code_section = ""
    if source_code:
        source_code_section = (
            "\n## Generated Source Code\n"
            "The following React/TSX source was generated for this design. "
            "Use it to provide PRECISE fix instructions - reference exact "
            "component names, CSS classes, and Tailwind utilities.\n"
            "```tsx\n" + source_code + "\n```\n"
        )

    prompt = f"""You are a pixel-perfect design verification expert. Compare these two images:

**IMAGE 1 (First image):** Figma Design - the source of truth
**IMAGE 2 (Second image):** Generated Website - the output to verify

Design Specification:
- Name: {design_data.get('name', 'Unnamed')}
- Colors: {', '.join(colors) if colors else 'N/A'}
- Fonts: {', '.join(fonts) if fonts else 'N/A'}{focus_section}
{source_code_section}
## CRITICAL ANALYSIS REQUIRED

Perform a pixel-perfect comparison focusing on:

### 1. Layout & Spacing (Most Important):
- Compare padding, margins, gaps between elements (measure in pixels)
- Check alignment (left, center, right, vertical centering)
- Verify container widths and heights
- Check if elements are properly positioned
- Measure spacing between sections

### 2. Visual Effects:
- Shadows: check offset, blur, spread, color
- Border radius: check corner rounding (in px)
- Gradients: check angle and color stops
- Opacity/transparency levels

### 3. Typography:
- Font sizes (exact px values)
- Font weights (100-900 or names like "bold", "semibold")
- Line heights and letter spacing
- Text alignment and color

### 4. Colors:
- Background colors (exact hex codes)
- Text colors
- Border colors
- Verify against design palette

### 5. Component Structure:
- Are all sections present?
- Is the nesting/hierarchy correct?
- Are elements in the right visual order?

## OUTPUT FORMAT

Respond with a JSON object (no markdown, just raw JSON):

{{
  "matches": false,
  "confidence": 0.85,
  "overall_assessment": "Close match but spacing issues in header",
  "discrepancies": [
    {{
      "type": "spacing|color|layout|shadow|typography|missing_element",
      "severity": "high|medium|low",
      "location": "Specific section/component name (e.g., 'Header section', 'Hero container')",
      "expected": "Exact value from Figma design (e.g., '24px padding', '#FF0000')",
      "actual": "What you see in generated version (e.g., '16px padding', '#FF1100')",
      "coordinates": {{"x": 100, "y": 50, "width": 200, "height": 80}},
      "fix_instructions": {{
        "target_file": "src/components/Header.tsx",
        "target_element": "header container",
        "current_value": "p-4",
        "new_value": "px-6 py-5",
        "explanation": "Change padding to match design exactly"
      }}
    }}
  ],
  "accuracy_scores": {{
    "layout": 0.85,
    "spacing": 0.75,
    "colors": 0.98,
    "typography": 0.92,
    "effects": 0.88
  }},
  "visual_explanation": "Brief explanation of overall match quality"
}}

**IMPORTANT INSTRUCTIONS:**
- Be extremely precise with measurements
- Provide exact Tailwind CSS classes for fixes (e.g., "p-6" not "more padding")
- For colors, use exact hex codes
- Severity: "high" = breaks layout/UX, "medium" = noticeable difference, "low" = minor detail
- Confidence: 1.0 = perfect match, 0.0 = completely different
- If images match perfectly, return {{"matches": true, "confidence": 1.0, "discrepancies": []}}

**OUTPUT JSON ONLY** - no explanatory text before or after the JSON."""

    return prompt


def _parse_vision_response(response_text: str) -> dict:
    """Parse Vision API response and extract JSON."""
    try:
        # Try to find JSON in response
        # Response might have explanatory text, find the JSON block
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1

        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON found in response")

        json_str = response_text[start_idx:end_idx]
        result = json.loads(json_str)

        # Validate required fields
        required_fields = ["matches", "confidence", "discrepancies", "accuracy_scores"]
        for field in required_fields:
            if field not in result:
                result[field] = _get_default_field(field)

        # Ensure discrepancies is a list
        if not isinstance(result["discrepancies"], list):
            result["discrepancies"] = []

        return result

    except Exception as e:
        print(f"[Vision API] Failed to parse response: {e}", flush=True)
        print(f"[Vision API] Response text: {response_text[:500]}", flush=True)
        return _fallback_result()


def _get_default_field(field: str) -> Any:
    """Get default value for a field."""
    defaults = {
        "matches": False,
        "confidence": 0.5,
        "discrepancies": [],
        "accuracy_scores": {
            "layout": 0.5,
            "spacing": 0.5,
            "colors": 0.5,
            "typography": 0.5,
            "effects": 0.5,
        },
        "visual_explanation": "Comparison completed with limited data",
    }
    return defaults.get(field, None)


def _fallback_result() -> dict:
    """Return fallback result when Vision API fails."""
    return {
        "matches": False,
        "confidence": 0.0,
        "discrepancies": [
            {
                "type": "error",
                "severity": "high",
                "location": "Vision API",
                "expected": "Successful comparison",
                "actual": "API call failed",
                "coordinates": {"x": 0, "y": 0, "width": 0, "height": 0},
                "fix_instructions": {
                    "target_file": "N/A",
                    "target_element": "N/A",
                    "current_value": "N/A",
                    "new_value": "N/A",
                    "explanation": "Vision API comparison failed, falling back to content-based comparison",
                },
            }
        ],
        "accuracy_scores": {
            "layout": 0.0,
            "spacing": 0.0,
            "colors": 0.0,
            "typography": 0.0,
            "effects": 0.0,
        },
        "visual_explanation": "Vision API comparison failed",
    }
