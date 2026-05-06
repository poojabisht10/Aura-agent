"""Dev server manager for running Vite dev servers for generated projects."""
import os
import platform
import signal
import subprocess
import threading
from pathlib import Path
from typing import Dict, Optional
import time
import socket

from backend.utils import get_npm_command

# Global dictionary to track running dev servers
# Format: {project_id: {"process": subprocess.Popen, "port": int, "project_name": str}}
_running_servers: Dict[int, Dict] = {}
_lock = threading.Lock()

# Port range for dev servers (starting from 5173, Vite's default)
_START_PORT = 5173
_MAX_PORT = 6000

_IS_WINDOWS = platform.system() == "Windows"


def find_free_port(start_port: int = _START_PORT, max_port: int = _MAX_PORT) -> Optional[int]:
    """Find a free port in the given range, always scanning from _START_PORT."""
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('localhost', port))
                return port
            except OSError:
                continue
    # Wrap around: try ports below start_port in case old servers were stopped
    if start_port > _START_PORT:
        for port in range(_START_PORT, start_port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('localhost', port))
                    return port
                except OSError:
                    continue
    return None


def _kill_process_tree(process: subprocess.Popen) -> None:
    """Kill a process and all its children. Handles Windows npm/node process trees."""
    pid = process.pid
    try:
        if _IS_WINDOWS:
            # On Windows, taskkill /T kills the entire process tree
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=10,
            )
        else:
            # On Unix, send SIGTERM to process group
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        # Last resort
        try:
            process.kill()
        except Exception:
            pass


def start_dev_server(project_id: int, project_path: Path, project_name: str, install_deps: bool = True) -> Optional[int]:
    """Start a Vite dev server for a project. Returns the port number or None if failed."""
    with _lock:
        # Check if server is already running
        if project_id in _running_servers:
            return _running_servers[project_id]["port"]

    # Run npm install OUTSIDE the lock to avoid blocking all server operations
    project_dir = Path(project_path)
    if not project_dir.exists():
        return None

    package_json = project_dir / "package.json"
    if not package_json.exists():
        return None

    node_modules = project_dir / "node_modules"
    if install_deps and not node_modules.exists():
        try:
            print(f"Installing dependencies for {project_name}...")
            install_result = subprocess.run(
                [get_npm_command(), "install"],
                cwd=str(project_dir),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            if install_result.returncode != 0:
                print(f"Failed to install dependencies for {project_name}: {install_result.stderr}")
                return None
        except Exception as e:
            print(f"Error installing dependencies for {project_name}: {e}")
            return None

    with _lock:
        # Re-check after npm install (another thread may have started it)
        if project_id in _running_servers:
            return _running_servers[project_id]["port"]

        # Find a free port
        port = find_free_port(_START_PORT)
        if not port:
            return None

        try:
            # Build Popen kwargs — on Windows, use CREATE_NEW_PROCESS_GROUP
            # so we can kill the entire npm/node tree later
            popen_kwargs = dict(
                cwd=str(project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if _IS_WINDOWS:
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

            # Start Vite dev server with custom port
            process = subprocess.Popen(
                [get_npm_command(), "run", "dev", "--", "--port", str(port), "--host"],
                **popen_kwargs,
            )

            # Wait a moment to see if it starts successfully
            time.sleep(3)

            # Check if process is still running
            if process.poll() is None:
                _running_servers[project_id] = {
                    "process": process,
                    "port": port,
                    "project_name": project_name,
                }
                return port
            else:
                # Process died, read error
                stdout, stderr = process.communicate()
                print(f"Failed to start dev server for {project_name}: {stderr}")
                return None
        except Exception as e:
            print(f"Error starting dev server for {project_name}: {e}")
            return None


def stop_dev_server(project_id: int) -> bool:
    """Stop a running dev server for a project."""
    with _lock:
        if project_id not in _running_servers:
            return False

        server_info = _running_servers.pop(project_id)

    # Kill outside the lock to avoid blocking
    process = server_info["process"]
    _kill_process_tree(process)
    return True


def get_dev_server_port(project_id: int) -> Optional[int]:
    """Get the port number for a running dev server."""
    with _lock:
        if project_id in _running_servers:
            return _running_servers[project_id]["port"]
        return None


def is_server_running(project_id: int) -> bool:
    """Check if a dev server is running for a project."""
    with _lock:
        if project_id not in _running_servers:
            return False

        process = _running_servers[project_id]["process"]
        return process.poll() is None


def list_running_servers() -> Dict[int, Dict]:
    """List all running dev servers."""
    with _lock:
        # Clean up dead processes
        dead_servers = []
        for project_id, server_info in _running_servers.items():
            if server_info["process"].poll() is not None:
                dead_servers.append(project_id)

        for project_id in dead_servers:
            del _running_servers[project_id]

        return _running_servers.copy()
