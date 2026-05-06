"""Structured logger with in-memory progress store for real-time frontend updates."""
import logging
import time
import threading
from typing import Dict, List, Optional

logger = logging.getLogger("aura2")

# ── In-memory progress store (thread-safe) ──────────────────────────
_progress_lock = threading.Lock()
_progress_store: Dict[int, dict] = {}  # project_id → progress dict
MAX_LOG_LINES = 60


def get_progress(project_id: int) -> Optional[dict]:
    """Get current progress for a project. Returns None if not found."""
    with _progress_lock:
        entry = _progress_store.get(project_id)
        if entry is None:
            return None
        return {**entry, "lines": list(entry["lines"])}


def clear_progress(project_id: int):
    """Remove progress entry (call after conversion completes)."""
    with _progress_lock:
        _progress_store.pop(project_id, None)


# ── ConversionLogger ────────────────────────────────────────────────
class ConversionLogger:
    def __init__(self, project_id: int, project_name: str):
        self.project_id = project_id
        self.project_name = project_name
        self._phase = "SETUP"
        self._phase_start = time.time()
        self._total_start = time.time()
        self._components = 0
        self._tools_used = 0

        # Initialise progress store entry
        with _progress_lock:
            _progress_store[project_id] = {
                "project_id": project_id,
                "project_name": project_name,
                "phase": self._phase,
                "status": "running",
                "elapsed_s": 0,
                "components": 0,
                "tools_used": 0,
                "lines": [],
            }

    # ── internal helpers ──
    def _prefix(self) -> str:
        return f"[#{self.project_id} | {self._phase:<10}]"

    def _push(self, level: str, msg: str):
        """Push a log line to the in-memory store and Python logger."""
        ts = time.strftime("%H:%M:%S")
        line = {"ts": ts, "level": level, "phase": self._phase, "msg": msg}
        with _progress_lock:
            entry = _progress_store.get(self.project_id)
            if entry:
                entry["phase"] = self._phase
                entry["elapsed_s"] = round(time.time() - self._total_start, 1)
                entry["components"] = self._components
                entry["tools_used"] = self._tools_used
                lines: list = entry["lines"]
                lines.append(line)
                if len(lines) > MAX_LOG_LINES:
                    del lines[: len(lines) - MAX_LOG_LINES]

    def _sync_store(self, **extra):
        with _progress_lock:
            entry = _progress_store.get(self.project_id)
            if entry:
                entry.update(extra)

    # ── public API ──
    def phase(self, name: str):
        elapsed = time.time() - self._phase_start
        self._push("info", f"Phase complete in {elapsed:.1f}s")
        logger.info(f"{self._prefix()} Phase complete in {elapsed:.1f}s")
        self._phase = name
        self._phase_start = time.time()
        self._push("info", f"── Starting ──")
        logger.info(f"{self._prefix()} ── Starting ──")

    def info(self, msg: str):
        self._push("info", msg)
        logger.info(f"{self._prefix()} {msg}")

    def warn(self, msg: str):
        self._push("warn", msg)
        logger.warning(f"{self._prefix()} {msg}")

    def error(self, msg: str):
        self._push("error", msg)
        logger.error(f"{self._prefix()} {msg}")

    def tool(self, tool_name: str, detail: str = ""):
        self._tools_used += 1
        extra = f" → {detail}" if detail else ""
        self._push("tool", f"{tool_name}{extra}")
        logger.info(f"{self._prefix()} Tool: {tool_name}{extra}")

    def component_saved(self, name: str, category: str = ""):
        self._components += 1
        cat = f" ({category})" if category else ""
        self._push("component", f"Saved: {name}{cat}")
        logger.info(f"{self._prefix()} Component saved: {name}{cat}")

    def done(self, components: int, build_ok: bool):
        self._components = components
        elapsed = time.time() - self._total_start
        mins, secs = divmod(int(elapsed), 60)
        status = "✓" if build_ok else "✗"
        msg = f"Completed in {mins}m {secs}s — {components} components, build: {status}"
        self._push("done", msg)
        logger.info(f"[#{self.project_id} | {'DONE':<10}] {msg}")
        self._sync_store(status="done", components=components)
