"""Figma to React conversion modules."""

from .design_styles import (
    rgba_to_hex,
    extract_text_style,
    extract_layout_info,
    extract_effects,
    extract_fills,
    extract_strokes,
    extract_corner_radius,
)
from .figma_extraction import (
    extract_figma_file_key,
    extract_node_data,
    collect_image_refs,
    collect_colors_and_fonts,
    extract_complete_design_data,
)
from .figma_api import (
    fetch_figma_data,
    fetch_figma_image_fills,
    download_figma_images,
    export_figma_node_images,
)
from .plugin_conversion import (
    convert_plugin_data_to_design_data,
    transform_plugin_node,
    save_plugin_images,
)
from .prompt_generation import (
    get_system_prompt,
    get_ui_library_instructions,
    build_conversion_prompt,
    design_data_to_prompt_text,
    format_frame_for_prompt,
)
from .semantic_analysis import (
    infer_semantic_type,
    get_aria_role,
)
from .verification import (
    visual_verification_loop,
    apply_fixes,
)
from .project_setup import (
    configure_litellm,
    setup_project_from_template,
)

__all__ = [
    # design_styles
    "rgba_to_hex",
    "extract_text_style",
    "extract_layout_info",
    "extract_effects",
    "extract_fills",
    "extract_strokes",
    "extract_corner_radius",
    # figma_extraction
    "extract_figma_file_key",
    "extract_node_data",
    "collect_image_refs",
    "collect_colors_and_fonts",
    "extract_complete_design_data",
    # figma_api
    "fetch_figma_data",
    "fetch_figma_image_fills",
    "download_figma_images",
    "export_figma_node_images",
    # plugin_conversion
    "convert_plugin_data_to_design_data",
    "transform_plugin_node",
    "save_plugin_images",
    # prompt_generation
    "get_system_prompt",
    "get_ui_library_instructions",
    "build_conversion_prompt",
    "design_data_to_prompt_text",
    "format_frame_for_prompt",
    # semantic_analysis
    "infer_semantic_type",
    "get_aria_role",
    # verification
    "visual_verification_loop",
    "apply_fixes",
    # project_setup
    "configure_litellm",
    "setup_project_from_template",
]
