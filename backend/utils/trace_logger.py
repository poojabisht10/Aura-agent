"""Conversion tracing / observability for Aura2.

Captures a per-conversion trace (prompts, messages, tool calls, tokens) and
persists it as JSON inside the generated project directory.  Optionally
forwards traces to Langfuse when configured — each conversion run becomes
a single Langfuse trace with nested spans for prompts, agent turns, and
tool calls.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from backend.config import settings

_logger = logging.getLogger("aura2")

# ── Langfuse singleton (lazy-init) ──────────────────────────────────

_langfuse_client = None
_langfuse_init_attempted = False


def get_langfuse_client():
    """Get Langfuse client if configured, otherwise return ``None``.

    Returns ``None`` when:
    - The ``langfuse`` package is not installed.
    - The required API keys are not set in settings / environment.
    """
    global _langfuse_client, _langfuse_init_attempted

    if _langfuse_init_attempted:
        return _langfuse_client

    _langfuse_init_attempted = True

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        _logger.debug("Langfuse keys not configured — skipping Langfuse integration")
        return None

    try:
        from langfuse import Langfuse  # type: ignore[import-untyped]

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        _logger.info("Langfuse client initialised")
        return _langfuse_client
    except ImportError:
        _logger.debug("langfuse package not installed — pip install langfuse")
        return None
    except Exception as exc:
        _logger.warning(f"Failed to initialise Langfuse client: {exc}")
        return None


# ── Conversion Trace ────────────────────────────────────────────────


class ConversionTrace:
    """Captures the full trace of a conversion for debugging and analysis.

    When Langfuse is configured, each ConversionTrace creates a Langfuse
    ``trace`` at init and nests spans/generations inside it:

    - ``system-prompt``  — generation span with the system prompt
    - ``conversion-prompt`` — generation span with the design-data prompt
    - ``agent-turn-N``   — generation span per assistant message
    - ``tool:ToolName``  — span per tool call
    """

    def __init__(self, project_id: int, project_name: str):
        self.project_id = project_id
        self.project_name = project_name
        self.started_at: str = datetime.utcnow().isoformat()
        self.finished_at: str | None = None
        self.events: list[dict] = []
        self.system_prompt: str = ""
        self.conversion_prompt: str = ""
        self.agent_messages: list[dict] = []
        self.tool_calls: list[dict] = []
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.model: str = ""
        self.ui_library: str = ""
        self.status: str = "running"
        self.error: str | None = None

        # ── Langfuse trace object (None if not configured) ──
        self._lf_trace = None
        self._lf_turn_count = 0
        lf = get_langfuse_client()
        if lf:
            try:
                self._lf_trace = lf.trace(
                    name=f"conversion:{project_name}",
                    metadata={
                        "project_id": project_id,
                        "project_name": project_name,
                    },
                    tags=["aura2", "figma-to-react", self.ui_library or "tailwind"],
                )
                _logger.info(f"Langfuse trace created for project {project_name}")
            except Exception as exc:
                _logger.warning(f"Failed to create Langfuse trace: {exc}")

    # ── event helpers ──────────────────────────────────────────────

    def log_event(self, event_type: str, data: dict) -> None:
        """Log a trace event with timestamp."""
        self.events.append({
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def log_system_prompt(self, prompt: str) -> None:
        """Record the system prompt used."""
        self.system_prompt = prompt
        self.log_event("system_prompt", {"length": len(prompt)})

        if self._lf_trace:
            try:
                self._lf_trace.generation(
                    name="system-prompt",
                    input=prompt[:50000],  # Langfuse has limits; truncate if huge
                    model=self.model,
                    metadata={"prompt_type": "system", "length": len(prompt)},
                )
            except Exception as exc:
                _logger.debug(f"Langfuse system-prompt span failed: {exc}")

    def log_conversion_prompt(self, prompt: str) -> None:
        """Record the conversion prompt (design data + instructions)."""
        self.conversion_prompt = prompt
        self.log_event("conversion_prompt", {"length": len(prompt)})

        if self._lf_trace:
            try:
                self._lf_trace.generation(
                    name="conversion-prompt",
                    input=prompt[:50000],
                    model=self.model,
                    metadata={"prompt_type": "conversion", "length": len(prompt)},
                )
            except Exception as exc:
                _logger.debug(f"Langfuse conversion-prompt span failed: {exc}")

    def log_agent_message(self, role: str, content: str, tokens: int = 0) -> None:
        """Log an agent message (assistant or user turn).

        Stores only the first 500 chars as a preview locally.
        Sends full content (truncated to 10k) to Langfuse.
        """
        self.agent_messages.append({
            "role": role,
            "content_preview": content[:500],
            "tokens": tokens,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.log_event("agent_message", {"role": role, "tokens": tokens})

        if self._lf_trace and role == "assistant":
            self._lf_turn_count += 1
            try:
                self._lf_trace.generation(
                    name=f"agent-turn-{self._lf_turn_count}",
                    output=content[:10000],
                    model=self.model,
                    usage={"output": tokens} if tokens else None,
                    metadata={"role": role, "turn": self._lf_turn_count},
                )
            except Exception as exc:
                _logger.debug(f"Langfuse agent-message span failed: {exc}")

    def log_tool_call(self, tool_name: str, args: dict, result: str = "") -> None:
        """Log a tool call made by the agent.

        Stores args preview (first 200 chars) and result preview locally.
        Creates a span in Langfuse.
        """
        args_str = json.dumps(args, default=str) if args else ""
        self.tool_calls.append({
            "tool": tool_name,
            "args_preview": args_str[:200],
            "result_preview": result[:200] if result else "",
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.log_event("tool_call", {"tool": tool_name})

        if self._lf_trace:
            try:
                self._lf_trace.span(
                    name=f"tool:{tool_name}",
                    input=args_str[:2000],
                    output=result[:2000] if result else None,
                    metadata={"tool_name": tool_name},
                )
            except Exception as exc:
                _logger.debug(f"Langfuse tool-call span failed: {exc}")

    def log_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Accumulate token usage."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    # ── lifecycle ──────────────────────────────────────────────────

    def finish(self, status: str = "success", error: str | None = None) -> None:
        """Mark the trace as complete. Updates Langfuse trace with final metadata."""
        self.status = status
        self.error = error
        self.finished_at = datetime.utcnow().isoformat()
        self.log_event("finish", {"status": status, "error": error})

        # Update Langfuse trace with final output, usage, and metadata
        if self._lf_trace:
            try:
                # Find total cost from events
                cost_events = [e for e in self.events if e.get("type") == "cost"]
                total_cost = cost_events[-1]["data"]["total_cost_usd"] if cost_events else None

                self._lf_trace.update(
                    output={
                        "status": status,
                        "error": error,
                        "total_turns": self._lf_turn_count,
                        "total_tool_calls": len(self.tool_calls),
                        "components_in_trace": len([
                            tc for tc in self.tool_calls
                            if "save_component" in tc.get("tool", "")
                        ]),
                        "total_cost_usd": total_cost,
                    },
                    metadata={
                        "project_id": self.project_id,
                        "project_name": self.project_name,
                        "model": self.model,
                        "ui_library": self.ui_library,
                        "total_input_tokens": self.total_input_tokens,
                        "total_output_tokens": self.total_output_tokens,
                        "total_cost_usd": total_cost,
                        "duration_seconds": self._duration_seconds(),
                    },
                    tags=["aura2", "figma-to-react", self.ui_library or "tailwind", status],
                )

                # Also create a final summary generation span with total usage
                if self.total_input_tokens > 0 or self.total_output_tokens > 0:
                    self._lf_trace.generation(
                        name="total-usage",
                        model=self.model,
                        usage={
                            "input": self.total_input_tokens,
                            "output": self.total_output_tokens,
                            "total": self.total_input_tokens + self.total_output_tokens,
                        },
                        metadata={
                            "total_cost_usd": total_cost,
                            "duration_seconds": self._duration_seconds(),
                        },
                    )
            except Exception as exc:
                _logger.debug(f"Langfuse trace update failed: {exc}")

        # Flush Langfuse to ensure data is sent
        self._flush_langfuse()

    def _duration_seconds(self) -> float | None:
        if self.started_at and self.finished_at:
            try:
                start = datetime.fromisoformat(self.started_at)
                end = datetime.fromisoformat(self.finished_at)
                return (end - start).total_seconds()
            except Exception:
                pass
        return None

    def _flush_langfuse(self) -> None:
        """Flush the Langfuse client to ensure all events are sent."""
        lf = get_langfuse_client()
        if lf:
            try:
                lf.flush()
            except Exception as exc:
                _logger.debug(f"Langfuse flush failed: {exc}")

    # ── serialisation / persistence ────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize the trace to a dict (includes full prompts for local storage)."""
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "error": self.error,
            "model": self.model,
            "ui_library": self.ui_library,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "system_prompt": self.system_prompt,
            "system_prompt_length": len(self.system_prompt),
            "conversion_prompt": self.conversion_prompt,
            "conversion_prompt_length": len(self.conversion_prompt),
            "agent_messages": self.agent_messages,
            "tool_calls": self.tool_calls,
            "events": self.events,
            "langfuse_trace_id": getattr(self._lf_trace, "id", None),
        }

    def save(self, project_path: Path) -> None:
        """Save trace to {project_path}/trace/conversion_trace.json."""
        trace_dir = project_path / "trace"
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_file = trace_dir / "conversion_trace.json"
        trace_file.write_text(
            json.dumps(self.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        _logger.info(f"Trace saved to {trace_file}")

    def summary(self) -> dict:
        """Return a compact summary suitable for inclusion in result dicts."""
        unique_tools = list({tc["tool"] for tc in self.tool_calls})
        return {
            "total_turns": len(
                [m for m in self.agent_messages if m["role"] == "assistant"]
            ),
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "tools_used": unique_tools,
            "langfuse_trace_id": getattr(self._lf_trace, "id", None),
        }
