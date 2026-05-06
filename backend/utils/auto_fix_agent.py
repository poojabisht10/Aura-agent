"""Auto-fix agent that generates fix instructions from visual comparison discrepancies."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


async def generate_fixes(
    discrepancies: List[Dict[str, Any]],
    project_path: Path,
    design_data: dict,
) -> List[Dict[str, Any]]:
    """
    Convert comparison discrepancies into actionable fix instructions.

    Handles discrepancy types produced by:
      - content-based comparison (text, color, structure, layout)
      - vision API comparison (spacing, color, typography, effects, missing_element)
      - structural comparison (structural)

    Args:
        discrepancies: List of discrepancy dicts from any comparison method.
        project_path: Path to generated project (used to scan files when needed).
        design_data: Original Figma design data.

    Returns:
        List of fix instruction dicts, sorted high → low priority.
    """
    fixes: List[Dict[str, Any]] = []

    for discrepancy in discrepancies:
        disc_type = discrepancy.get("type", "")
        issue = discrepancy.get("issue", "")
        severity = discrepancy.get("severity", "medium")

        # ------------------------------------------------------------------
        # Content-based discrepancies
        # ------------------------------------------------------------------
        if disc_type == "text" and issue == "missing_text":
            for text in discrepancy.get("missing_texts", []):
                fixes.append({
                    "type": "add_text",
                    "target": "App.tsx or relevant component",
                    "text": text,
                    "priority": "high",
                    "instruction": f"Add missing text content: '{text}' to the appropriate component",
                })

        elif disc_type == "color" and issue == "missing_colors":
            for color in discrepancy.get("missing_colors", []):
                fixes.append({
                    "type": "update_color",
                    "target": "components with matching design colors",
                    "color": color,
                    "priority": "medium",
                    "instruction": f"Update color values to use exact design color: {color}",
                })

        elif disc_type == "structure" and issue == "no_components":
            fixes.append({
                "type": "create_components",
                "target": "src/components/",
                "priority": "high",
                "instruction": "Create component files in src/components/ based on the design structure",
            })

        elif disc_type == "layout":
            element = discrepancy.get("element", "unknown")
            fixes.append({
                "type": "fix_layout",
                "target": element,
                "priority": "high",
                "instruction": f"Fix layout alignment and spacing for the '{element}' section",
            })

        # ------------------------------------------------------------------
        # Vision API discrepancies (have fix_instructions dict)
        # ------------------------------------------------------------------
        elif disc_type in ("spacing", "typography", "shadow", "missing_element"):
            fix_instr = discrepancy.get("fix_instructions", {})
            target_file = fix_instr.get("target_file", "")
            current_val = fix_instr.get("current_value", "")
            new_val = fix_instr.get("new_value", "")
            explanation = fix_instr.get("explanation", "")
            location = discrepancy.get("location", "unknown element")

            if disc_type == "spacing" and target_file and current_val and new_val:
                # Try to build a FixApplicator-compatible spacing fix
                fixes.append({
                    "type": "spacing",
                    "priority": severity,
                    "instruction": (
                        f"Fix spacing in {location}: {explanation or f'change {current_val!r} to {new_val!r}'}"
                    ),
                    "instructions": {
                        "file": target_file,
                        "from": current_val,
                        "to": new_val,
                    },
                })
            elif disc_type == "typography":
                _exp = discrepancy.get("expected", "")
                _act = discrepancy.get("actual", "")
                _typo_detail = explanation or f"{_exp} → {_act}"
                fixes.append({
                    "type": "update_typography",
                    "target": target_file or location,
                    "priority": severity,
                    "instruction": f"Fix typography in {location}: {_typo_detail}",
                    **({"instructions": {"file": target_file, "from": current_val, "to": new_val}}
                       if target_file and current_val and new_val else {}),
                })
            elif disc_type == "shadow":
                fixes.append({
                    "type": "shadow",
                    "priority": severity,
                    "instruction": f"Add/fix box-shadow in {location}: {explanation}",
                    **({"instructions": {"file": target_file, "shadow_class": new_val}}
                       if target_file and new_val else {}),
                })
            elif disc_type == "missing_element":
                fixes.append({
                    "type": "add_element",
                    "target": target_file or "relevant component",
                    "priority": "high",
                    "instruction": f"Add missing element in {location}: {explanation}",
                })

        elif disc_type == "color" and discrepancy.get("expected"):
            # Vision-detected color mismatch
            fix_instr = discrepancy.get("fix_instructions", {})
            target_file = fix_instr.get("target_file", "")
            old_val = fix_instr.get("current_value", "")
            new_val = fix_instr.get("new_value", discrepancy.get("expected", ""))
            location = discrepancy.get("location", "unknown")
            fixes.append({
                "type": "color",
                "priority": severity,
                "instruction": f"Fix color in {location}: expected {discrepancy.get('expected','')} but got {discrepancy.get('actual','')}",
                **({"instructions": {"file": target_file, "from": old_val, "to": new_val}}
                   if target_file and new_val else {}),
            })

        # ------------------------------------------------------------------
        # Structural comparison discrepancies
        # ------------------------------------------------------------------
        elif disc_type == "structural":
            location = discrepancy.get("location", "unknown element")
            expected = discrepancy.get("expected", "")
            actual = discrepancy.get("actual", "")

            # Parse the expected/actual strings like "padding-left: 16.0px"
            prop, figma_val, dom_val = _parse_structural_discrepancy(expected, actual)

            # Map CSS property to fix type
            if prop and _is_spacing_property(prop):
                # Try to build a FixApplicator-compatible spacing fix
                tailwind_fix = _css_to_tailwind(prop, figma_val)
                fixes.append({
                    "type": "spacing",
                    "priority": severity,
                    "instruction": (
                        f"Fix {prop} on '{location}': "
                        f"Figma expects {figma_val}, DOM has {dom_val}"
                        + (f" → use class {tailwind_fix}" if tailwind_fix else "")
                    ),
                    # No file path known — agent must find it
                    "target_element": location,
                    "property": prop,
                    "expected_value": figma_val,
                    "actual_value": dom_val,
                })
            elif prop and _is_color_property(prop):
                fixes.append({
                    "type": "color",
                    "priority": severity,
                    "instruction": (
                        f"Fix {prop} on '{location}': "
                        f"Figma expects {figma_val}, DOM has {dom_val}"
                    ),
                    "target_element": location,
                    "property": prop,
                    "expected_value": figma_val,
                    "actual_value": dom_val,
                })
            elif prop and _is_typography_property(prop):
                fixes.append({
                    "type": "update_typography",
                    "priority": severity,
                    "instruction": (
                        f"Fix {prop} on '{location}': "
                        f"Figma expects {figma_val}, DOM has {dom_val}"
                    ),
                    "target_element": location,
                    "property": prop,
                    "expected_value": figma_val,
                    "actual_value": dom_val,
                })
            else:
                # Generic structural fix
                fixes.append({
                    "type": "fix_structural",
                    "priority": severity,
                    "instruction": (
                        f"Fix structural mismatch on '{location}': "
                        f"expected {expected}, got {actual}"
                    ),
                    "target_element": location,
                })

    # Sort by priority: high → medium → low
    priority_order = {"high": 0, "medium": 1, "low": 2}
    fixes.sort(key=lambda f: priority_order.get(str(f.get("priority", "medium")), 1))

    return fixes


def format_fixes_for_prompt(fixes: List[Dict[str, Any]]) -> str:
    """
    Format fix instructions as a prompt for the agent to apply.

    Args:
        fixes: List of fix dicts from generate_fixes().

    Returns:
        Formatted markdown string.
    """
    if not fixes:
        return "No fixes needed — design matches perfectly!"

    lines = ["## FIXES REQUIRED", "",
             "The following discrepancies were found between the generated site and Figma design:", ""]

    for i, fix in enumerate(fixes, 1):
        fix_type = fix.get("type", "unknown").upper().replace("_", " ")
        instruction = fix.get("instruction", "")
        target = fix.get("target", fix.get("target_element", ""))
        priority = fix.get("priority", "medium")

        lines.append(f"{i}. **{fix_type}** [{priority}] — {instruction}")
        if target:
            lines.append(f"   - Target: {target}")
        if fix.get("property"):
            lines.append(f"   - Property: {fix['property']}")
            lines.append(f"   - Expected: {fix.get('expected_value', '')}")
            lines.append(f"   - Actual: {fix.get('actual_value', '')}")
        if fix.get("text"):
            lines.append(f"   - Text: '{fix['text']}'")
        if fix.get("color"):
            lines.append(f"   - Color: {fix['color']}")
        if fix.get("instructions"):
            instr = fix["instructions"]
            if instr.get("file"):
                lines.append(f"   - File: {instr['file']}")
            if instr.get("from") and instr.get("to"):
                lines.append(f"   - Change: '{instr['from']}' → '{instr['to']}'")
        lines.append("")

    lines.append("Please apply ALL fixes above to make the generated site match the Figma design exactly.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_structural_discrepancy(expected: str, actual: str):
    """
    Parse strings like "padding-left: 16.0px" into (property, figma_value, dom_value).
    Returns ("", "", "") if parsing fails.
    """
    prop = ""
    figma_val = ""
    dom_val = ""

    m = re.match(r"^([\w\-]+):\s*(.+)$", expected.strip())
    if m:
        prop = m.group(1)
        figma_val = m.group(2)

    m2 = re.match(r"^([\w\-]+):\s*(.+)$", actual.strip())
    if m2:
        dom_val = m2.group(2)

    return prop, figma_val, dom_val


_SPACING_PROPS = {
    "padding-top", "padding-right", "padding-bottom", "padding-left",
    "margin-top", "margin-right", "margin-bottom", "margin-left",
    "gap", "width", "height", "border-radius",
}

_COLOR_PROPS = {"background-color", "color", "border-color"}

_TYPO_PROPS = {
    "font-size", "font-weight", "font-family", "line-height", "letter-spacing",
}


def _is_spacing_property(prop: str) -> bool:
    return prop.lower() in _SPACING_PROPS


def _is_color_property(prop: str) -> bool:
    return prop.lower() in _COLOR_PROPS


def _is_typography_property(prop: str) -> bool:
    return prop.lower() in _TYPO_PROPS


# Rough mapping of px values to Tailwind arbitrary-value classes
def _css_to_tailwind(prop: str, value: str) -> Optional[str]:
    """Return a Tailwind arbitrary-value class hint for a CSS property/value pair."""
    px_match = re.search(r"([\d.]+)px", value)
    if not px_match:
        return None
    px = px_match.group(1)

    mapping = {
        "padding-top": f"pt-[{px}px]",
        "padding-right": f"pr-[{px}px]",
        "padding-bottom": f"pb-[{px}px]",
        "padding-left": f"pl-[{px}px]",
        "gap": f"gap-[{px}px]",
        "font-size": f"text-[{px}px]",
        "border-radius": f"rounded-[{px}px]",
    }
    return mapping.get(prop.lower())
