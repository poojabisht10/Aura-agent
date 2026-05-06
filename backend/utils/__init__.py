import platform

from .component_matcher import ComponentMatcher


def get_npm_command() -> str:
    """Get the correct npm command for the current platform."""
    if platform.system() == "Windows":
        return "npm.cmd"
    return "npm"


def get_npx_command() -> str:
    """Get the correct npx command for the current platform."""
    if platform.system() == "Windows":
        return "npx.cmd"
    return "npx"


__all__ = ["ComponentMatcher", "get_npm_command", "get_npx_command"]
