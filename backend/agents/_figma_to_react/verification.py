"""Enhanced visual verification with AI vision, structural comparison, and element-level screenshots."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    TextBlock,
)

from backend.config import settings
from backend.mcp_tools.component_library import create_component_library_server
from backend.utils.visual_comparison import (
    capture_page_screenshot,
    compare_with_figma_design,
    wait_for_server_ready,
)
from backend.utils.vision_comparison import compare_with_vision_api
from backend.utils.structural_comparison import compare_structural_properties, _get_design_viewport
from backend.utils.figma_screenshot import export_design_screenshot
from backend.utils.auto_fix_agent import generate_fixes, format_fixes_for_prompt
from backend.utils.fix_applicator import FixApplicator
from backend.dev_server_manager import start_dev_server, stop_dev_server
from backend.utils import get_npx_command


async def visual_verification_loop(
    project_path: Path,
    design_data: dict,
    figma_url: Optional[str] = None,
    plugin_data: Optional[dict] = None,
    figma_screenshot_path: Optional[Path] = None,
    max_iterations: Optional[int] = None,
    figma_token: str = "",
    file_key: str = "",
) -> dict:
    """
    Run enhanced visual verification loop with AI vision, structural comparison,
    element-level screenshots, and auto-fix iterations.

    Args:
        project_path: Path to generated project.
        design_data: Original Figma design data.
        figma_url: Figma file URL (for REST API export).
        plugin_data: Plugin data (may contain designScreenshot).
        figma_screenshot_path: Pre-saved Figma design screenshot (skips plugin/API extraction).
        max_iterations: Maximum fix iterations (defaults to config value).
        figma_token: Figma API token (enables element-level Figma node export).
        file_key: Figma file key (enables element-level Figma node export).

    Returns:
        {
            "status": "success" | "completed_with_warnings" | "needs_review" | "failed",
            "iterations": int,
            "confidence": float,
            "final_scores": {...},
            "element_comparison": {...},
            "history": [...]
        }
    """
    max_iterations = max_iterations or settings.max_verification_iterations
    confidence_threshold = settings.verification_confidence_threshold
    early_stop_threshold = settings.verification_early_stop_threshold

    print(f"[Verification] Starting enhanced verification (max {max_iterations} iterations)", flush=True)

    screenshots_dir = project_path / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    # Use negative ID range to avoid collision with real project IDs (positive ints)
    temp_project_id = -(abs(hash(str(project_path))) % 1000000 + 1)
    iteration_history = []
    element_comparison_result = {}

    try:
        # Start dev server
        print("[Verification] Starting dev server...", flush=True)
        port = start_dev_server(
            project_id=temp_project_id,
            project_path=project_path,
            project_name=project_path.name,
            install_deps=False,
        )

        if not port:
            return _error_result("Failed to start dev server")

        print(f"[Verification] Waiting for server on port {port}...", flush=True)
        if not await wait_for_server_ready(port, max_wait=30):
            return _error_result("Dev server did not become ready")

        print(f"[Verification] Server ready on port {port}", flush=True)

        # Resolve Figma design screenshot
        resolved_screenshot: Optional[Path] = figma_screenshot_path

        if resolved_screenshot is None and plugin_data:
            from backend.utils.figma_screenshot import save_plugin_screenshot
            resolved_screenshot = save_plugin_screenshot(plugin_data, screenshots_dir)
            if resolved_screenshot:
                print(f"[Verification] Using plugin screenshot: {resolved_screenshot}", flush=True)

        if resolved_screenshot is None:
            print(
                "[Verification] No Figma screenshot available — "
                "vision comparison will be skipped, falling back to structural + content",
                flush=True,
            )

        # Compute viewport from design data (handles mobile/tablet/desktop/custom)
        viewport = _get_design_viewport(design_data)
        print(f"[Verification] Design viewport: {viewport['width']}x{viewport['height']}", flush=True)

        # Run element-level screenshot comparison (once, before fix iterations)
        try:
            from backend.utils.element_screenshot_comparison import run_element_comparison
            print("[Verification] Running element-level screenshot comparison...", flush=True)
            element_comparison_result = await run_element_comparison(
                port=port,
                design_data=design_data,
                screenshots_dir=screenshots_dir / "elements",
                figma_token=figma_token,
                file_key=file_key,
                viewport=viewport,
            )
            if element_comparison_result.get("element_count", 0) > 0:
                dim_acc = element_comparison_result.get("overall_dimension_accuracy", 0)
                print(f"[Verification] Element comparison: {element_comparison_result['element_count']} elements, "
                      f"dim_accuracy={dim_acc:.2%}", flush=True)
        except Exception as exc:
            print(f"[Verification] Element comparison error: {exc}", flush=True)
            element_comparison_result = {}

        # Verification + fix loop
        for iteration in range(max_iterations):
            print(f"\n[Verification] === Iteration {iteration + 1}/{max_iterations} ===", flush=True)

            if iteration > 0:
                print("[Verification] Waiting for hot reload...", flush=True)
                await asyncio.sleep(3)

            # Capture generated page screenshot
            print("[Verification] Capturing page screenshot...", flush=True)
            generated_screenshot = await capture_page_screenshot(
                port, screenshots_dir,
                viewport_width=viewport["width"],
                viewport_height=viewport["height"],
            )

            if not generated_screenshot:
                print("[Verification] Failed to capture screenshot", flush=True)
                continue

            # Always keep a stable "generated_latest.png" for the dashboard
            import shutil
            latest_path = screenshots_dir / "generated_latest.png"
            try:
                shutil.copy2(str(generated_screenshot), str(latest_path))
            except Exception:
                pass

            # Vision comparison (requires Figma screenshot)
            vision_result = None
            if settings.enable_vision_comparison and resolved_screenshot:
                print("[Verification] Running vision comparison...", flush=True)
                vision_result = await compare_with_vision_api(
                    figma_screenshot_path=resolved_screenshot,
                    generated_screenshot_path=generated_screenshot,
                    design_data=design_data,
                    project_path=project_path,
                )

            # Structural comparison (requires data-figma-id attributes in DOM)
            structural_result = None
            if settings.enable_structural_comparison:
                print("[Verification] Running structural comparison...", flush=True)
                try:
                    structural_result = await compare_structural_properties(
                        port, design_data, project_path, viewport=viewport
                    )
                    if structural_result and structural_result["total_checks"] == 0:
                        structural_result = None
                except Exception as exc:
                    print(f"[Verification] Structural comparison error: {exc}", flush=True)
                    structural_result = None

            # Content-based comparison (always runs as baseline)
            print("[Verification] Running content-based comparison...", flush=True)
            content_result = await compare_with_figma_design(
                generated_screenshot,
                design_data,
                project_path,
            )

            # Adaptive weighting based on what comparisons are available
            has_vision = vision_result and vision_result.get("confidence", 0) > 0
            has_structural = structural_result and structural_result.get("confidence", 0) > 0

            if has_vision and has_structural:
                # Structural is measured data (CSS properties), vision is a single
                # LLM opinion — structural should dominate when available.
                combined_confidence = (
                    structural_result["confidence"] * 0.55
                    + vision_result["confidence"] * 0.25
                    + content_result["confidence"] * 0.20
                )
                # Use structural's MEASURED scores as the base, vision only adds
                # a qualitative "layout" score that structural can't measure
                accuracy_scores = {
                    "dimension": structural_result.get("dimension_accuracy", 0),
                    "color": structural_result.get("color_accuracy", 0),
                    "spacing": structural_result.get("spacing_accuracy", 0),
                    "typography": structural_result.get("typography_accuracy", 0),
                    "effects": structural_result.get("effects_accuracy", 0),
                    "layout": vision_result.get("accuracy_scores", {}).get("layout", 0),
                }
                # Merge discrepancies: structural failures are actionable,
                # vision discrepancies add qualitative context
                discrepancies = []
                for check in structural_result.get("property_checks", []):
                    if not check["match"] and check["severity"] in ("high", "medium"):
                        discrepancies.append({
                            "type": "structural",
                            "severity": check["severity"],
                            "location": check["element"],
                            "expected": f"{check['property']}: {check['figma_value']}",
                            "actual": f"{check['property']}: {check['dom_value']}",
                        })
                # Add vision discrepancies that don't duplicate structural findings
                for vd in vision_result.get("discrepancies", []):
                    discrepancies.append(vd)
                comparison_method = "vision+structural+content"

            elif has_vision:
                combined_confidence = (
                    vision_result["confidence"] * 0.7
                    + content_result["confidence"] * 0.3
                )
                discrepancies = vision_result["discrepancies"]
                accuracy_scores = vision_result.get("accuracy_scores", {})
                comparison_method = "vision+content"

            elif has_structural:
                combined_confidence = (
                    structural_result["confidence"] * 0.6
                    + content_result["confidence"] * 0.4
                )
                discrepancies = list(content_result["discrepancies"])
                for check in structural_result.get("property_checks", []):
                    if not check["match"]:
                        discrepancies.append({
                            "type": "structural",
                            "severity": check["severity"],
                            "location": check["element"],
                            "expected": f"{check['property']}: {check['figma_value']}",
                            "actual": f"{check['property']}: {check['dom_value']}",
                        })
                accuracy_scores = {
                    "structural": structural_result["confidence"],
                    "dimension": structural_result.get("dimension_accuracy", 0),
                    "color": structural_result.get("color_accuracy", 0),
                    "spacing": structural_result.get("spacing_accuracy", 0),
                    "typography": structural_result.get("typography_accuracy", 0),
                    "effects": structural_result.get("effects_accuracy", 0),
                }
                comparison_method = "structural+content"

            else:
                combined_confidence = content_result["confidence"]
                discrepancies = content_result["discrepancies"]
                accuracy_scores = {}
                comparison_method = "content_only"

            # Factor in element-level dimension accuracy (if available)
            if element_comparison_result.get("element_count", 0) > 0:
                elem_dim_acc = element_comparison_result.get("overall_dimension_accuracy", 1.0)
                # Blend: 90% existing + 10% element dimension accuracy
                combined_confidence = combined_confidence * 0.9 + elem_dim_acc * 0.1
                accuracy_scores["element_dimensions"] = elem_dim_acc

            iteration_result = {
                "iteration": iteration + 1,
                "confidence": round(combined_confidence, 4),
                "method": comparison_method,
                "accuracy_scores": accuracy_scores,
                "discrepancies": discrepancies,
                "fixes_applied": 0,
            }
            iteration_history.append(iteration_result)

            print(
                f"[Verification] Confidence: {combined_confidence:.2%} ({comparison_method})",
                flush=True,
            )
            if accuracy_scores:
                score_str = ", ".join(
                    f"{k}={v:.0%}" for k, v in list(accuracy_scores.items())[:5]
                )
                print(f"[Verification] Scores — {score_str}", flush=True)

            # Early stop — very high confidence
            if combined_confidence >= early_stop_threshold:
                print(
                    f"[Verification] ✓ Early stop — confidence {combined_confidence:.2%} "
                    f">= {early_stop_threshold:.2%}",
                    flush=True,
                )
                return _build_result("success", iteration + 1, combined_confidence,
                                     accuracy_scores, iteration_history, element_comparison_result,
                                     project_path=project_path, design_data=design_data)

            # Success threshold met
            if combined_confidence >= confidence_threshold:
                print(
                    f"[Verification] ✓ Success — confidence {combined_confidence:.2%} "
                    f">= {confidence_threshold:.2%}",
                    flush=True,
                )
                return _build_result("success", iteration + 1, combined_confidence,
                                     accuracy_scores, iteration_history, element_comparison_result,
                                     project_path=project_path, design_data=design_data)

            # Plateau detection
            if iteration > 0:
                prev_confidence = iteration_history[-2]["confidence"]
                improvement = combined_confidence - prev_confidence
                if improvement < 0.01:
                    print(
                        f"[Verification] ⚠ Plateau — improvement {improvement:.2%} < 1%, stopping",
                        flush=True,
                    )
                    status = "success" if combined_confidence >= confidence_threshold else "completed_with_warnings"
                    return _build_result(status, iteration + 1, combined_confidence,
                                         accuracy_scores, iteration_history, element_comparison_result,
                                     project_path=project_path, design_data=design_data)

            # Filter out unfixable discrepancies:
            # - errors and info-only items
            # - mapping issues (wrong DOM element)
            # - low severity (e.g. text width variance across renderers)
            actionable = [
                d for d in discrepancies
                if d.get("type") != "error"
                and d.get("severity") not in ("info", "low")
                and "wrong DOM element" not in str(d.get("note", ""))
            ]

            # Log breakdown by severity
            sev_counts = {}
            for d in discrepancies:
                s = d.get("severity", "?")
                sev_counts[s] = sev_counts.get(s, 0) + 1
            sev_str = ", ".join(f"{k}={v}" for k, v in sorted(sev_counts.items()))

            print(
                f"[Verification] Found {len(discrepancies)} discrepancies "
                f"({len(actionable)} actionable) [{sev_str}]",
                flush=True,
            )

            if not actionable:
                print("[Verification] No actionable discrepancies to fix", flush=True)
                break

            fixes = await generate_fixes(actionable, project_path, design_data)
            if not fixes:
                print("[Verification] No fixes generated", flush=True)
                break

            max_fixes = settings.max_fixes_per_iteration
            fixes_to_apply = fixes[:max_fixes]
            print(
                f"[Verification] Applying {len(fixes_to_apply)} fixes "
                f"(of {len(fixes)} generated)...",
                flush=True,
            )
            applied_count = await apply_fixes(fixes_to_apply, project_path, design_data)
            iteration_result["fixes_applied"] = applied_count
            print(f"[Verification] Applied {applied_count} fixes", flush=True)

            # If no files were actually modified, stop — another iteration won't help
            if applied_count == 0:
                print("[Verification] Fix agent made no changes — stopping iteration", flush=True)
                break

        # Loop exhausted — return final result
        final_confidence = iteration_history[-1]["confidence"] if iteration_history else 0.0
        final_scores = iteration_history[-1].get("accuracy_scores", {}) if iteration_history else {}

        if final_confidence >= confidence_threshold:
            status = "success"
        elif final_confidence >= 0.85:
            status = "completed_with_warnings"
        else:
            status = "needs_review"

        print(
            f"\n[Verification] Final status: {status} (confidence: {final_confidence:.2%})",
            flush=True,
        )
        return _build_result(status, len(iteration_history), final_confidence,
                             final_scores, iteration_history, element_comparison_result,
                             project_path=project_path, design_data=design_data)

    finally:
        print("[Verification] Stopping dev server...", flush=True)
        stop_dev_server(temp_project_id)


async def apply_fixes(
    fixes: list,
    project_path: Path,
    design_data: dict,
) -> int:
    """
    Apply fixes to the codebase.

    Strategy:
      1. Try FixApplicator for structured fixes (spacing / color / layout / shadow).
         These are deterministic, fast, and don't need an LLM call.
      2. For remaining (complex / unstructured) fixes, fall back to a focused
         Claude agent session.

    Args:
        fixes: List of fix dicts from generate_fixes().
        project_path: Path to project.
        design_data: Original design data.

    Returns:
        Number of fixes successfully applied.
    """
    if not fixes:
        return 0

    applicator = FixApplicator(project_path)
    applied_via_applicator = 0
    complex_fixes = []

    for fix in fixes:
        fix_type = fix.get("type", "")
        instructions = fix.get("instructions", {})

        # FixApplicator handles structured fixes that have explicit instructions
        if fix_type in ("spacing", "color", "layout", "shadow") and instructions:
            try:
                success = await applicator.apply_fix(fix)
                if success:
                    applied_via_applicator += 1
                    print(
                        f"[FixApplicator] Applied {fix_type} fix: {instructions.get('file', '?')}",
                        flush=True,
                    )
                else:
                    complex_fixes.append(fix)
            except Exception as exc:
                print(f"[FixApplicator] Error on {fix_type}: {exc}", flush=True)
                complex_fixes.append(fix)
        else:
            complex_fixes.append(fix)

    if applied_via_applicator:
        print(
            f"[FixApplicator] Applied {applied_via_applicator} structured fix(es) directly",
            flush=True,
        )

    # Fall back to agent for complex fixes
    if not complex_fixes:
        return applied_via_applicator

    agent_applied = await _apply_fixes_via_agent(complex_fixes, project_path)
    return applied_via_applicator + agent_applied


async def _apply_fixes_via_agent(
    fixes: list,
    project_path: Path,
) -> int:
    """Apply complex fixes using a focused Claude agent session.

    Tracks file modifications to verify the agent actually changed something.
    """
    fixes_prompt = format_fixes_for_prompt(fixes)

    # Snapshot file mtimes before the agent runs
    src_dir = project_path / "src"
    pre_mtimes: Dict[str, float] = {}
    if src_dir.exists():
        for f in src_dir.rglob("*"):
            if f.is_file() and f.suffix in (".tsx", ".jsx", ".css", ".ts"):
                pre_mtimes[str(f)] = f.stat().st_mtime

    # List component files for the agent to target
    component_files = []
    comp_dir = project_path / "src" / "components"
    if comp_dir.exists():
        for f in sorted(comp_dir.iterdir()):
            if f.is_file() and f.suffix in (".tsx", ".jsx", ".css"):
                component_files.append(f.name)
    file_list = ", ".join(component_files[:20]) if component_files else "src/components/*.tsx"

    component_library_server = create_component_library_server()
    mcp_servers = {
        "playwright": {
            "type": "stdio",
            "command": get_npx_command(),
            "args": ["@playwright/mcp@latest"],
        },
        "component_library": component_library_server,
    }

    options = ClaudeAgentOptions(
        model=settings.default_model,
        system_prompt=f"""You are a pixel-perfect code fixer for a React + CSS Modules project.

AVAILABLE FILES: {file_list}
PROJECT PATH: {project_path}

WORKFLOW:
1. Read ALL .tsx and .module.css files in src/components/
2. For each fix below, find the element and change the exact CSS property
3. Use the Edit tool to make surgical changes (NOT Write to rewrite entire files)
4. Run `npm run build` once at the end to verify

CRITICAL:
- Use the Edit tool for changes, NOT Write (avoid rewriting entire files)
- Use EXACT values from fix instructions (px, hex colors)
- For CSS Modules: edit the .module.css file
- For inline styles: edit the .tsx file
- Do NOT add, remove, or restructure components — only fix CSS values""",
        max_turns=settings.max_fix_turns,
        cwd=str(project_path),
        max_buffer_size=20 * 1024 * 1024,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        mcp_servers=mcp_servers,
        permission_mode="acceptEdits",
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(fixes_prompt)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(f"[Fix Agent] {block.text[:200]}...", flush=True)

        # Check which files were actually modified
        changed_files = []
        for fpath, old_mtime in pre_mtimes.items():
            try:
                new_mtime = Path(fpath).stat().st_mtime
                if new_mtime > old_mtime:
                    changed_files.append(Path(fpath).name)
            except FileNotFoundError:
                pass

        if changed_files:
            print(f"[Fix Agent] Modified {len(changed_files)} file(s): {', '.join(changed_files)}", flush=True)
            return len(changed_files)
        else:
            print("[Fix Agent] No files were modified — agent may have failed silently", flush=True)
            return 0

    except Exception as exc:
        print(f"[Fix Agent] Error: {exc}", flush=True)
        return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_result(
    status: str,
    iterations: int,
    confidence: float,
    final_scores: dict,
    history: list,
    element_comparison: dict,
    project_path: Optional[Path] = None,
    design_data: Optional[dict] = None,
) -> dict:
    """Assemble the final verification result dict and write JSON report."""
    result = {
        "status": status,
        "iterations": iterations,
        "confidence": confidence,
        "final_scores": final_scores,
        "element_comparison": element_comparison,
        "history": history,
    }

    # Write structured report to disk
    if project_path:
        try:
            report_path = _write_verification_report(
                project_path, result, design_data or {}
            )
            result["report_path"] = str(report_path)
        except Exception as exc:
            print(f"[Verification] Failed to write report: {exc}", flush=True)

    return result


def _error_result(message: str) -> dict:
    """Return an error result dict."""
    return {
        "status": "failed",
        "iterations": 0,
        "confidence": 0.0,
        "final_scores": {},
        "element_comparison": {},
        "history": [],
        "error": message,
    }


def _write_verification_report(
    project_path: Path,
    result: dict,
    design_data: dict,
) -> Path:
    """Write a structured JSON verification report to the project's screenshots dir.

    Args:
        project_path: Path to the generated project.
        result: The verification result dict from _build_result.
        design_data: Original Figma design data.

    Returns:
        Path to the written report file.
    """
    screenshots_dir = project_path / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    report_path = screenshots_dir / "verification-report.json"

    # Build per-element results from element_comparison
    per_element = []
    elem_comp = result.get("element_comparison", {})
    for elem in elem_comp.get("elements", []):
        # Convert absolute screenshot path to relative (from screenshots dir)
        # so the frontend can fetch via /api/projects/{id}/screenshots/{path}
        raw_path = elem.get("screenshot_path", "")
        rel_path = ""
        if raw_path:
            try:
                rel_path = str(Path(raw_path).relative_to(screenshots_dir)).replace("\\", "/")
            except (ValueError, TypeError):
                # Path not under screenshots_dir — try relative to project
                try:
                    full_rel = str(Path(raw_path).relative_to(project_path)).replace("\\", "/")
                    # Strip leading "screenshots/" if present
                    if full_rel.startswith("screenshots/"):
                        rel_path = full_rel[len("screenshots/"):]
                    else:
                        rel_path = full_rel
                except (ValueError, TypeError):
                    rel_path = Path(raw_path).name  # fallback to just filename

        per_element.append({
            "figma_id": elem.get("figma_id", ""),
            "name": elem.get("element_name", elem.get("figma_id", "")),
            "accuracy": elem.get("dimension_score", 0),
            "dom_screenshot": rel_path,
            "width_match": elem.get("width_match"),
            "height_match": elem.get("height_match"),
            "pixel_comparison": elem.get("pixel_comparison"),
        })

    # Collect discrepancies from the final history entry
    history = result.get("history", [])
    final_discrepancies = history[-1].get("discrepancies", []) if history else []

    report = {
        "timestamp": datetime.now().isoformat(),
        "project_name": project_path.name,
        "overall_confidence": result.get("confidence", 0.0),
        "status": result.get("status", "unknown"),
        "method": history[-1].get("method", "unknown") if history else "unknown",
        "iterations": result.get("iterations", 0),
        "scores": result.get("final_scores", {}),
        "element_comparison": {
            "element_count": elem_comp.get("element_count", 0),
            "overall_dimension_accuracy": elem_comp.get("overall_dimension_accuracy", 0),
            "overall_pixel_accuracy": elem_comp.get("overall_pixel_accuracy"),
        },
        "per_element_results": per_element,
        "discrepancies": final_discrepancies,
        "iteration_history": history,
    }

    report_path.write_text(
        json.dumps(report, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"[Verification] Report written to {report_path}", flush=True)
    return report_path
