"""Configuration management for Aura2."""
from enum import Enum
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class UILibrary(str, Enum):
    """Supported UI component libraries."""
    TAILWIND = "tailwind"
    MUI = "mui"
    CHAKRA = "chakra"
    CSS_MODULES = "css-modules"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra env vars not defined in the model
    )

    # API Keys
    figma_token: str = ""
    litellm_api_key: str = ""  # LiteLLM API key
    github_personal_access_token: str = ""  # GitHub personal access token (alternative name)

    # LiteLLM Configuration
    litellm_base_url: str = ""  # Set via LITELLM_BASE_URL environment variable
    litellm_provider: str = ""  # Set via LITELLM_PROVIDER environment variable

    # Database
    database_url: str = "sqlite+aiosqlite:///./aura2.db"

    # Directories
    generated_projects_dir: Path = Path("./generated_projects")
    component_library_dir: Path = Path("./component_library")

    # Agent Settings
    default_model: str = "claude-sonnet-4-6"
    fast_model: str = "claude-haiku-4-5-20251001"
    max_agent_turns: int = 500
    max_fix_turns: int = 15

    # UI Library Settings
    default_ui_library: UILibrary = UILibrary.TAILWIND
    supported_ui_libraries: list = ["tailwind", "mui", "chakra", "css-modules"]

    # Figma MCP Server Settings
    use_figma_mcp: bool = False  # Enable Figma MCP Server (requires setup)
    figma_mcp_server_type: str = "remote"  # "remote" or "local"
    figma_mcp_server_url: str = "https://mcp.figma.com/mcp"  # Remote server URL

    # GitHub Integration Settings
    github_token: str = ""  # GitHub personal access token (env: GITHUB_TOKEN)
    github_owner: str = ""  # GitHub org or username
    github_default_branch: str = "main"  # Default branch name
    auto_create_repo: bool = False  # Auto-create repo on project creation
    auto_create_pr: bool = False  # Auto-create PR after generation

    # Code Quality Settings
    auto_run_lint: bool = True  # Run ESLint after generation
    auto_run_format: bool = True  # Run Prettier after generation
    auto_fix_lint: bool = True  # Auto-fix ESLint issues
    verify_build: bool = True  # Verify build after generation

    # Vercel Deployment Settings
    vercel_token: str = ""  # Vercel API token (env: VERCEL_TOKEN)
    vercel_org_id: str = ""  # Vercel organization/team ID (optional)
    vercel_project_id: str = ""  # Default Vercel project ID (optional)
    auto_deploy_vercel: bool = False  # Auto-deploy to Vercel after generation

    # Visual Verification Settings (AI Vision-based)
    enable_vision_comparison: bool = True  # Use Claude Vision API for pixel-perfect comparison
    vision_comparison_model: str = "claude-sonnet-4-6"  # Model with vision capabilities
    max_verification_iterations: int = 10  # Max iterations for verification loop
    verification_confidence_threshold: float = 0.95  # Min confidence to pass (95%)
    verification_early_stop_threshold: float = 0.98  # Confidence for early stop (98%)

    # Screenshot Settings
    screenshot_scale: int = 1  # 1x scale to reduce base64 token cost
    screenshot_viewport_width: int = 1440  # Desktop viewport width
    screenshot_viewport_height: int = 900  # Desktop viewport height

    # Structural Comparison Settings
    enable_structural_comparison: bool = True
    structural_comparison_tolerance_px: int = 2
    color_comparison_tolerance: int = 5  # Per-channel RGB tolerance (0-255)

    # Fix Application Settings
    max_fixes_per_iteration: int = 5  # Max fixes to apply per iteration
    auto_apply_high_priority_fixes: bool = True  # Auto-apply high severity fixes
    require_manual_review_for_low_confidence: bool = True  # Manual review if confidence < threshold

    # Tracing / Observability
    enable_trace_logging: bool = True  # Save trace JSON per conversion
    langfuse_public_key: str = ""  # Optional Langfuse public key
    langfuse_secret_key: str = ""  # Optional Langfuse secret key
    langfuse_host: str = "https://cloud.langfuse.com"  # Langfuse host URL

    @property
    def effective_github_token(self) -> str:
        """Get GitHub token from either github_token or github_personal_access_token."""
        return self.github_token or self.github_personal_access_token

    @property
    def is_vercel_enabled(self) -> bool:
        """Check if Vercel deployment is enabled."""
        return bool(self.vercel_token and self.auto_deploy_vercel)


settings = Settings()
