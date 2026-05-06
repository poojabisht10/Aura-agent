"""System prompts and conversion prompt generation for Figma to React conversion."""
import functools
import logging

logger = logging.getLogger(__name__)


def design_data_to_prompt_text(design_data: dict, image_paths: dict) -> str:
    """Convert structured design data to text for the agent prompt.

    Args:
        design_data: Output from extract_complete_design_data()
        image_paths: Dict mapping image refs to local paths

    Returns:
        Formatted text describing the design
    """
    if "error" in design_data:
        return f"Error: {design_data['error']}"

    lines = []
    lines.append(f"# Design: {design_data['name']}")
    lines.append("")

    # Stats summary
    stats = design_data.get("stats", {})
    lines.append(f"## Overview")
    lines.append(f"- Pages: {stats.get('pageCount', 0)}")
    lines.append(f"- Frames: {stats.get('frameCount', 0)}")
    lines.append(f"- Unique Colors: {stats.get('colorCount', 0)}")
    lines.append(f"- Fonts: {stats.get('fontCount', 0)}")
    lines.append(f"- Images: {stats.get('imageCount', 0)}")
    lines.append("")

    # Fonts to import
    lines.append("## Fonts (import in index.html)")
    for font in design_data.get("fonts", []):
        weights = ",".join(map(str, font["weights"]))
        lines.append(f"- {font['family']}: weights {weights}")
    lines.append("")

    # Color palette
    lines.append("## Color Palette (use EXACT hex values)")
    all_colors = design_data.get("colors", [])
    if len(all_colors) > 30:
        logger.warning("Design has %d colors; only including top 30 in prompt", len(all_colors))
    for color_info in all_colors[:30]:
        contexts = ", ".join(color_info.get("contexts", [])[:2])
        lines.append(f"- {color_info['color']} (used {color_info['count']}x, e.g. {contexts})")
    lines.append("")

    # Images
    if image_paths:
        lines.append("## Downloaded Images (use these paths)")
        for ref, path in image_paths.items():
            lines.append(f"- {ref}: {path}")
        lines.append("")

    # Pages and frames with complete structure
    lines.append("## Complete Design Structure")
    lines.append("Use this EXACT structure to recreate the design:")
    lines.append("")

    for page in design_data.get("pages", []):
        lines.append(f"### Page: {page['name']}")

        for frame in page.get("frames", []):
            lines.append("")
            lines.append(format_frame_for_prompt(frame, 0))

    return "\n".join(lines)


def format_frame_for_prompt(node: dict, indent: int = 0) -> str:
    """Format a frame/node for the prompt with all necessary details."""
    prefix = "  " * indent
    lines = []

    node_type = node.get("type", "")
    name = node.get("name", "")
    node_id = node.get("id", "")
    semantic_type = node.get("semanticType", "")
    suggested_element = node.get("suggestedElement", "")
    children = node.get("children", [])

    # Frame header with position info
    layout = node.get("layout", {})
    bounds = layout.get("bounds", {})
    pos_info = ""
    if bounds.get("y") is not None and indent == 0:
        pos_info = f" [y={int(bounds['y'])}]"
    lines.append(f"{prefix}#### {name} ({node_type}) [id: {node_id}]{pos_info}")

    # Semantic type information (CRITICAL for proper HTML generation)
    if semantic_type and semantic_type != "unknown":
        aria_role = node.get("ariaRole", "")
        aria_attr = f' role="{aria_role}"' if aria_role else ""
        lines.append(f"{prefix}  **SEMANTIC: {semantic_type}** → Use <{suggested_element}{aria_attr}> element")

        # Add specific guidance based on semantic type
        if semantic_type == "button":
            lines.append(f"{prefix}  → Add: hover, active, focus states with transitions and cursor pointer")
            lines.append(f"{prefix}  → Accessibility: Add aria-label if icon-only, visible focus indicator")
        elif semantic_type == "header":
            lines.append(f"{prefix}  → Use: <header role='banner'> with <nav role='navigation'> inside, make sticky/fixed if at top")
        elif semantic_type == "footer":
            lines.append(f"{prefix}  → Use: <footer role='contentinfo'> with proper grid layout for link columns")
        elif semantic_type == "card":
            lines.append(f"{prefix}  → Add: hover shadow increase + subtle lift transition")
        elif semantic_type == "link":
            lines.append(f"{prefix}  → Use: <a href='#'> with hover color change and transition")
        elif semantic_type in ("heading", "h1", "h2", "h3"):
            lines.append(f"{prefix}  → Use proper heading element for SEO and accessibility")
        elif semantic_type == "hero":
            lines.append(f"{prefix}  → Make full-width with centered content container (max-width + auto margin)")
        elif semantic_type == "sidebar":
            lines.append(f"{prefix}  → Consider: hidden on mobile, visible on desktop, role='complementary'")
        elif semantic_type == "carousel":
            lines.append(f"{prefix}  → CRITICAL: Code as interactive carousel with React state, NOT static images!")
            lines.append(f"{prefix}  → Use: useState for current slide, useEffect for auto-play, keyboard navigation")
            lines.append(f"{prefix}  → Add: Previous/Next buttons with onClick handlers, arrow key support")
            lines.append(f"{prefix}  → Accessibility: role='region' aria-label='Image carousel', aria-live='polite'")
        elif semantic_type == "modal":
            lines.append(f"{prefix}  → Use: role='dialog' aria-modal='true', focus trap, ESC key to close")
        elif semantic_type == "dropdown":
            lines.append(f"{prefix}  → Use: <select> or custom dropdown with role='combobox', keyboard navigation")
        elif semantic_type == "accordion":
            lines.append(f"{prefix}  → Use: role='region', aria-expanded, keyboard navigation (Enter/Space)")
        elif semantic_type == "tabs":
            lines.append(f"{prefix}  → Use: role='tablist', role='tab', role='tabpanel', keyboard navigation (Arrow keys)")
        elif semantic_type == "navigation":
            lines.append(f"{prefix}  → Use: <nav role='navigation'>, keyboard navigation, skip links")

    # Layout info for frames
    layout = node.get("layout", {})
    if layout:
        if layout.get("mode"):
            direction = "flex-col" if layout["mode"] == "VERTICAL" else "flex-row"
            gap = layout.get("itemSpacing", 0)
            padding = layout.get("padding", {})
            p_str = f"p-t:{padding.get('top',0)} p-r:{padding.get('right',0)} p-b:{padding.get('bottom',0)} p-l:{padding.get('left',0)}"
            lines.append(f"{prefix}  Layout: {direction}, gap-[{gap}px], {p_str}")

            # Suggest grid if multiple children in a row
            if layout["mode"] == "HORIZONTAL" and len(children) >= 3:
                lines.append(f"{prefix}  → Consider: grid grid-cols-{len(children)} gap-[{gap}px] for better responsive control")

        bounds = layout.get("bounds", {})

        # Check for complex grid patterns
        if len(children) >= 4 and bounds:
            # Check if children form a grid pattern (multiple rows)
            child_bounds = [c.get("layout", {}).get("bounds", {}) for c in children if c.get("layout", {}).get("bounds")]
            if len(child_bounds) >= 4:
                # Estimate grid columns based on positioning
                widths = [b.get("width", 0) for b in child_bounds]
                if widths:
                    avg_width = sum(widths) / len(widths)
                    container_width = bounds.get("width", 0)
                    estimated_cols = max(2, int(container_width / avg_width) if container_width > 0 else 2)
                    lines.append(f"{prefix}  → Grid pattern detected: Consider grid grid-cols-1 md:grid-cols-{min(estimated_cols, 4)} lg:grid-cols-{estimated_cols}")

        if bounds:
            lines.append(f"{prefix}  Size: {bounds.get('width', 0):.0f}x{bounds.get('height', 0):.0f}px")

    # Background/fills
    fills = node.get("fills", [])
    for fill in fills:
        if fill.get("type") == "SOLID":
            lines.append(f"{prefix}  Background: {fill.get('color')}")
        elif fill.get("type") == "IMAGE":
            lines.append(f"{prefix}  Background Image: {fill.get('imageRef')}")

    # Corner radius
    radius = node.get("cornerRadius", {})
    if radius:
        if "all" in radius:
            lines.append(f"{prefix}  Border Radius: {radius['all']}px")
        else:
            lines.append(f"{prefix}  Border Radius: tl:{radius.get('topLeft',0)} tr:{radius.get('topRight',0)} bl:{radius.get('bottomLeft',0)} br:{radius.get('bottomRight',0)}")

    # Effects (shadows)
    effects = node.get("effects", [])
    for effect in effects:
        if effect.get("type") in ("DROP_SHADOW", "INNER_SHADOW"):
            shadow_type = "shadow" if effect["type"] == "DROP_SHADOW" else "shadow-inset"
            offset = effect.get("offset", {})
            lines.append(f"{prefix}  {shadow_type}: {offset.get('x',0)}px {offset.get('y',0)}px {effect.get('radius',0)}px {effect.get('color')}")

    # ARIA role information
    aria_role = node.get("ariaRole", "")
    if aria_role:
        lines.append(f"{prefix}  ARIA Role: {aria_role}")

    # Text content (CRITICAL - exact text!)
    if node_type == "TEXT":
        text = node.get("text", "")
        style = node.get("style", {})
        lines.append(f'{prefix}  TEXT: "{text}"')
        lines.append(f"{prefix}  Font: {style.get('fontFamily')} {style.get('fontSize')}px weight-{style.get('fontWeight')}")
        for fill in fills:
            if fill.get("type") == "SOLID":
                lines.append(f"{prefix}  Color: {fill.get('color')}")

    # Image alt text generation
    if semantic_type == "image" or (node_type == "RECTANGLE" and any(f.get("type") == "IMAGE" for f in fills)):
        from backend.utils.accessibility import generate_alt_text
        image_name = name
        surrounding_text = " ".join([c.get("text", "") for c in children if c.get("type") == "TEXT"][:3])
        alt_text = generate_alt_text(image_name, semantic_type, surrounding_text, is_decorative=False)
        lines.append(f"{prefix}  Alt Text: '{alt_text}' (MUST include in <img alt='{alt_text}'>)")

    # Children (already defined at top of function)
    if children:
        lines.append(f"{prefix}  Children ({len(children)}):")
        for child in children:
            lines.append(format_frame_for_prompt(child, indent + 2))

    return "\n".join(lines)


def get_ui_library_instructions(ui_library: str) -> str:
    """Get UI library specific instructions with responsive design patterns."""
    if ui_library == "mui":
        return """
### Material UI (MUI) Styling
- Import components from @mui/material
- Use sx prop for custom styling: sx={{ backgroundColor: '#hexcode' }}
- Use MUI's Box, Stack, Grid for layouts
- Use Typography for text with exact fontFamily, fontSize, fontWeight
- Use exact hex colors in sx prop
- Example: <Button sx={{ bgcolor: '#1E40AF', color: '#fff', borderRadius: '8px' }}>Text</Button>

### RESPONSIVE DESIGN (MUI)
- Use breakpoints in sx prop: sx={{ width: { xs: '100%', md: '50%', lg: '33%' } }}
- Use Grid with responsive columns: <Grid container spacing={{ xs: 2, md: 3 }}>
- Hide/show elements: sx={{ display: { xs: 'none', md: 'block' } }}
- Container maxWidth: <Container maxWidth="lg">

### INTERACTIVE STATES (MUI)
- Buttons: <Button variant="contained" sx={{ '&:hover': { bgcolor: 'darken(color)' } }}>
- Use proper MUI Button, IconButton, Link components
"""
    elif ui_library == "chakra":
        return """
### Chakra UI Styling
- Import components from @chakra-ui/react
- Use style props directly: bg="#hexcode" color="#hexcode"
- Use Box, Flex, Grid, Stack for layouts
- Use Text component with exact fontFamily, fontSize, fontWeight
- Use exact hex colors as props
- Example: <Button bg="#1E40AF" color="#fff" borderRadius="8px">Text</Button>

### RESPONSIVE DESIGN (Chakra)
- Use responsive arrays: width={{ base: "100%", md: "50%", lg: "33%" }}
- Use Show/Hide: <Show above="md"><Sidebar /></Show>
- SimpleGrid for responsive grids: <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }}>
- Container: <Container maxW="container.xl">

### INTERACTIVE STATES (Chakra)
- Buttons: <Button _hover={{ bg: "gray.700" }} _active={{ transform: "scale(0.98)" }}>
- Use proper Button, IconButton, Link components
"""
    elif ui_library == "css-modules":
        return """
### CSS Modules Styling — DETAILED RULES

**File Structure (MANDATORY for every component):**
- Create `ComponentName.module.css` alongside each `ComponentName.tsx`
- Import: `import styles from './ComponentName.module.css'`
- Apply: `className={styles.container}` or `className={`${styles.hero} ${styles.dark}`}`
- Class names: camelCase for multi-word (`.heroTitle`, `.navLink`, `.cardWrapper`)

**CSS PROPERTY MAPPING FROM FIGMA (CRITICAL — this is where accuracy matters):**

| Figma Property | CSS Property | Example |
|---|---|---|
| absoluteBoundingBox.width | width | `width: 400px;` (for fixed) or `max-width: 400px;` (for fluid) |
| absoluteBoundingBox.height | height / min-height | `min-height: 600px;` |
| layout.padding (top/right/bottom/left) | padding | `padding: 24px 32px 24px 32px;` |
| layout.itemSpacing | gap | `gap: 16px;` |
| layout.mode HORIZONTAL | flex-direction | `display: flex; flex-direction: row;` |
| layout.mode VERTICAL | flex-direction | `display: flex; flex-direction: column;` |
| fills[].color (SOLID) | background-color | `background-color: #1E40AF;` |
| fills[].color on TEXT nodes | color | `color: #333333;` |
| style.fontSize | font-size | `font-size: 48px;` |
| style.fontWeight | font-weight | `font-weight: 700;` |
| style.fontFamily | font-family | `font-family: 'Inter', sans-serif;` |
| style.lineHeight | line-height | `line-height: 1.5;` or `line-height: 56px;` |
| style.letterSpacing | letter-spacing | `letter-spacing: -0.5px;` |
| cornerRadius.all | border-radius | `border-radius: 8px;` |
| cornerRadius individual | border-radius | `border-radius: 8px 8px 0 0;` |
| effects[] DROP_SHADOW | box-shadow | `box-shadow: 0 4px 16px rgba(0,0,0,0.1);` |
| effects[] INNER_SHADOW | box-shadow | `box-shadow: inset 0 2px 4px rgba(0,0,0,0.06);` |
| effects[] LAYER_BLUR | filter | `filter: blur(8px);` |
| effects[] BACKGROUND_BLUR | backdrop-filter | `backdrop-filter: blur(8px);` |
| strokes[].color + strokeWeight | border | `border: 1px solid #E5E7EB;` |
| opacity | opacity | `opacity: 0.8;` |
| gradient fills | background | `background: linear-gradient(180deg, #000 0%, #fff 100%);` |

**PIXEL-PERFECT SPACING (USE absoluteBoundingBox DATA):**

Calculate EXACT gaps from coordinates:
- Element A: y=100, height=50; Element B: y=174 → gap = 174-(100+50) = 24px → `gap: 24px;`
- Element A: x=16, width=280; Element B: x=316 → gap = 316-296 = 20px → `gap: 20px;`

**CSS CUSTOM PROPERTIES (Design Tokens) — define in `src/index.css`:**
```css
:root {
  /* Extract from design data colors section */
  --color-primary: #1E40AF;
  --color-secondary: #374151;
  --color-background: #FFFFFF;
  --color-text: #111827;
  --color-text-muted: #6B7280;
  --color-border: #E5E7EB;

  /* Extract from design data fonts section */
  --font-heading: 'Inter', sans-serif;
  --font-body: 'Inter', sans-serif;

  /* Derive from common spacing values in the design */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;
  --spacing-2xl: 48px;
  --spacing-3xl: 64px;

  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 16px;
  --radius-full: 9999px;
}
```
Reference in .module.css: `color: var(--color-primary);` `padding: var(--spacing-lg);`

### RESPONSIVE DESIGN (CSS Modules — CRITICAL)

**Mobile-first approach:** Write base styles for mobile, add `@media` for larger screens.

**Breakpoints:**
- `@media (min-width: 640px)` — sm (tablets portrait)
- `@media (min-width: 768px)` — md (tablets landscape)
- `@media (min-width: 1024px)` — lg (laptops)
- `@media (min-width: 1280px)` — xl (desktops)
- `@media (min-width: 1536px)` — 2xl (large screens)

**Container Pattern (CRITICAL — NEVER use `width: 1440px`):**
```css
.container {
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 16px;
}
@media (min-width: 768px) { .container { padding: 0 24px; } }
@media (min-width: 1024px) { .container { padding: 0 32px; } }
```

**Layout Patterns:**
```css
/* Header */
.header { width: 100%; position: sticky; top: 0; z-index: 50; }
.headerInner { max-width: 1280px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; }

/* Hero — full width background, centered content */
.hero { width: 100%; }
.heroContent { max-width: 1280px; margin: 0 auto; padding: 48px 16px; display: flex; flex-direction: column; }
@media (min-width: 1024px) {
  .heroContent { flex-direction: row; padding: 80px 32px; gap: 48px; align-items: center; }
  .heroLeft { flex: 1; }
  .heroRight { flex: 1; }
}

/* Responsive Grid */
.grid { display: grid; grid-template-columns: 1fr; gap: 16px; }
@media (min-width: 768px) { .grid { grid-template-columns: repeat(2, 1fr); gap: 24px; } }
@media (min-width: 1024px) { .grid { grid-template-columns: repeat(3, 1fr); } }
@media (min-width: 1280px) { .grid { grid-template-columns: repeat(4, 1fr); gap: 32px; } }

/* Navigation — mobile hamburger, desktop horizontal */
.nav { display: none; }
.mobileMenuBtn { display: block; }
@media (min-width: 1024px) {
  .nav { display: flex; gap: 24px; align-items: center; }
  .mobileMenuBtn { display: none; }
}

/* Footer columns */
.footerGrid { display: grid; grid-template-columns: 1fr; gap: 32px; }
@media (min-width: 768px) { .footerGrid { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 1024px) { .footerGrid { grid-template-columns: repeat(4, 1fr); } }
```

**Responsive Typography:**
```css
.heading { font-size: 28px; line-height: 1.2; }
@media (min-width: 768px) { .heading { font-size: 36px; } }
@media (min-width: 1024px) { .heading { font-size: 48px; } }
@media (min-width: 1280px) { .heading { font-size: 56px; } }
```

### INTERACTIVE STATES (CSS Modules — MANDATORY for ALL interactive elements)

```css
/* Buttons */
.button {
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
}
.button:hover { opacity: 0.9; transform: translateY(-1px); }
.button:active { transform: scale(0.98); }
.button:focus { outline: none; box-shadow: 0 0 0 2px white, 0 0 0 4px var(--color-primary); }

/* Links */
.navLink { transition: color 0.2s ease; }
.navLink:hover { color: var(--color-primary); }

/* Cards */
.card { transition: box-shadow 0.3s ease, transform 0.3s ease; }
.card:hover { box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); transform: translateY(-2px); }

/* Images */
.image { width: 100%; height: auto; object-fit: cover; }
```

### SHADOW & EFFECT TRANSLATION (CSS Modules)

Figma DROP_SHADOW → CSS:
- offset {x:0, y:4}, radius:16, spread:0, color rgba(0,0,0,0.1) → `box-shadow: 0 4px 16px 0 rgba(0,0,0,0.1);`
- offset {x:0, y:2}, radius:4 → `box-shadow: 0 2px 4px rgba(0,0,0,0.05);`

Figma INNER_SHADOW → CSS: `box-shadow: inset 0 2px 4px rgba(0,0,0,0.06);`
Figma LAYER_BLUR → CSS: `filter: blur(8px);`
Figma BACKGROUND_BLUR → CSS: `backdrop-filter: blur(8px);`
Gradients: `background: linear-gradient(180deg, #000 0%, #fff 100%);`

### ANIMATION & TRANSITIONS (CSS Modules)

```css
/* Define keyframes in the module file */
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }

.fadeIn { animation: fadeIn 0.5s ease-in-out forwards; }
.slideUp { animation: slideUp 0.3s ease-out forwards; }
```
"""
    else:  # tailwind (default)
        return """
### Tailwind CSS v4 Styling
- Use arbitrary values for exact colors: bg-[#1E40AF] text-[#333333]
- Use arbitrary spacing for design accuracy: p-[16px] m-[8px] gap-[24px]
- Use arbitrary font sizes: text-[14px] leading-[1.5]
- Use exact border radius: rounded-[8px]
- Import is: @import "tailwindcss";
- NO tailwind.config.js needed
- PostCSS is pre-configured

### RESPONSIVE DESIGN RULES (CRITICAL)

**Container Widths - NEVER use fixed widths for main containers:**
- WRONG: w-[1440px] (breaks on smaller screens)
- RIGHT: w-full max-w-7xl mx-auto
- For full-width backgrounds: w-full, then inner container: max-w-7xl mx-auto px-4

**Responsive Breakpoints (mobile-first):**
- Base styles apply to mobile (no prefix)
- sm: (640px+) - tablets portrait
- md: (768px+) - tablets landscape
- lg: (1024px+) - laptops
- xl: (1280px+) - desktops
- 2xl: (1536px+) - large screens

**Layout Patterns:**
- Headers: w-full, inner content max-w-7xl mx-auto px-4 md:px-6 lg:px-8
- Hero sections: w-full py-12 md:py-20 lg:py-28
- Grids: grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 md:gap-6
- Sidebars: hidden lg:block lg:w-64 (show on desktop only)
- Navigation: Mobile hamburger menu with lg:hidden, desktop nav with hidden lg:flex

**Responsive Typography:**
- Headings: text-2xl md:text-3xl lg:text-4xl xl:text-5xl
- Body text: text-sm md:text-base
- Use clamp for fluid typography when appropriate

**Responsive Spacing:**
- Padding: px-4 md:px-6 lg:px-8 (increases with screen size)
- Gaps: gap-4 md:gap-6 lg:gap-8
- Margins: my-8 md:my-12 lg:my-16

### INTERACTIVE STATES (MANDATORY for buttons/links)

**Buttons:**
- hover:opacity-90 OR hover:bg-[darkerShade]
- active:scale-[0.98] (subtle press effect)
- focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[brandColor]
- transition-all duration-200
- cursor-pointer

**Links/Navigation:**
- hover:text-[accentColor] OR hover:underline
- transition-colors duration-200

**Cards:**
- hover:shadow-lg transition-shadow duration-300
- Optional: hover:scale-[1.02] hover:-translate-y-1

**Images:**
- Use object-cover object-center for background images
- Add loading="lazy" for below-fold images
"""


def _github_section() -> str:
    return """## GIT INTEGRATION (GitHub MCP enabled)

After completing code generation and verification:

1. **Create Repository**: Use `mcp__github__create_repository` (name, description, private: true)
2. **Push Files**: Use `mcp__github__push_files` (owner, repo, branch: "main", files, message)
3. **Create Feature Branch**: Use `mcp__github__create_branch` for updates
4. **Create Pull Request**: Use `mcp__github__create_pull_request` with component list in body

**Commit Message Convention:** feat(figma):, style(figma):, fix(figma):
"""


def _vercel_section() -> str:
    return """## VERCEL DEPLOYMENT (Vercel MCP enabled)

After pushing to GitHub (or directly):

1. **Create Project**: Use `mcp__vercel__create_project` (name, framework: "vite")
2. **Deploy**: Use `mcp__vercel__deploy` (projectId, target: "production")
3. **Verify**: Use `mcp__vercel__get_deployment` to confirm success
"""


@functools.lru_cache(maxsize=32)
def get_system_prompt(
    is_new_project: bool,
    ui_library: str = "tailwind",
    add_as: str = "new_project",
    project_name: str = "",
    has_github: bool = False,
    has_vercel: bool = False,
) -> str:
    """Generate system prompt for the conversion agent.

    Results are cached by parameter combination — same config reuses the same
    string without rebuilding it on every conversion call.
    """

    # MANDATORY: Save instructions for ALL projects (new or existing)
    save_instructions = """
## CRITICAL: SAVE ALL COMPONENTS TO LIBRARY (MANDATORY)

After creating EACH React component, you MUST call:
**mcp__component_library__save_component** with:
- name: Component name (e.g., "Header", "Footer", "ProductCard", "HeroSection")
- code: The FULL component code (entire file contents)
- description: Brief description of what the component does
- category: One of: "header", "footer", "card", "button", "form", "navigation", "hero", "section", "layout", "ui"

**IMPORTANT:** Do NOT include props_schema parameter unless the component accepts props. If you do include it, it must be a valid JSON object like {"title": "string"}, NOT a text description.

**DO NOT SKIP THIS STEP!** Every component MUST be saved for future reuse across projects.
This enables the platform's core value: component reuse across designs.

Example after creating Header.tsx:
```
mcp__component_library__save_component({
  name: "Header",
  code: "const Header = () => {...};\\n\\nexport default Header;",
  description: "Main navigation header with logo, nav links, and CTA button",
  category: "header"
})
```
"""

    # Reuse instructions - different behavior for new projects vs adding pages
    reuse_instructions = ""
    if not is_new_project:
        # Adding to existing project - prioritize search and reuse
        reuse_instructions = """
## ⚠️ COMPONENT REUSE STRATEGY (MANDATORY — DO NOT SKIP)

The component library already has reusable components from previous projects. You MUST search and reuse them.

### Required workflow for EACH component you need:

1. **SEARCH**: `mcp__component_library__search_components({ description: "header navigation bar", category: "header" })`
2. **If similarity > 80%**: Call `mcp__component_library__get_component({ component_id: "..." })` to get the full code. Use this code as your starting point — adapt colors/text to match the current design.
3. **If similarity < 60% or no match**: Create the component fresh, then SAVE it: `mcp__component_library__save_component({ name: "...", code: "...", ... })`

### You MUST call `search_components` before writing your FIRST component. This is NOT optional.

**Common reusable components (search for these first):**
- Header / Navbar (category: "header")
- Footer / SiteMap (category: "footer")
- HeroSection / HeroBanner (category: "hero")
- Product sections, news sections (category: "section")

**IMPORTANT**: When you find a match, you MUST call `get_component` to retrieve it — do NOT just look at the search preview and recreate it manually. Calling `get_component` is how reuse gets tracked.
"""
    else:
        # New project - save everything for future reuse
        reuse_instructions = """
## COMPONENT LIBRARY USAGE (New Project)

Since this is a NEW project:
1. You are creating components fresh (no existing library to search)
2. **SAVE EVERY COMPONENT** you create using mcp__component_library__save_component
3. Future pages/projects will be able to reuse your components

This builds the component library for enterprise-scale reuse across projects.
"""

    # New page mode instructions
    page_mode_instructions = ""
    if add_as == "new_page":
        page_component_name = "".join(word.capitalize() for word in project_name.split("-"))
        page_mode_instructions = f"""
## ⚠️ SPECIAL MODE: ADDING NEW PAGE TO EXISTING PROJECT

**IMPORTANT:** You are NOT creating a new project. You are adding a NEW PAGE to an existing React project.

### Your Task:
1. Create a NEW PAGE COMPONENT at: src/pages/{page_component_name}.tsx
2. REUSE existing components from src/components/ whenever possible
3. Only create NEW components if no similar component exists (>80% similarity)
4. Update src/App.tsx to add a new route: <Route path="/{project_name}" element={{<{page_component_name} />}} />
5. Import the new page component in App.tsx

### What You MUST DO:
- Check src/components/ directory first to see what components already exist
- Import and reuse: Header, Footer, Button, etc. if they exist
- Only write NEW components to src/components/ if needed
- Create the page component in src/pages/{page_component_name}.tsx
- Update src/App.tsx by adding the new route INSIDE the existing <Routes> component

### What You MUST NOT DO:
- DO NOT create a new project structure
- DO NOT overwrite existing App.tsx - only ADD the new route
- DO NOT duplicate components that already exist
- DO NOT remove existing routes

### Example App.tsx update:
```tsx
// Add import at top
import {page_component_name} from './pages/{page_component_name}';

// Add route inside <Routes>
<Route path="/{project_name}" element={{<{page_component_name} />}} />
```
"""

    # UI Library specific instructions
    ui_library_instructions = get_ui_library_instructions(ui_library)

    return f"""You are an expert Figma-to-React conversion specialist. Your SOLE mission is to produce a PIXEL-PERFECT replica of the Figma design — the generated website must be visually INDISTINGUISHABLE from the original design.

## MANDATORY TOOL USAGE (READ THIS FIRST)

**ALWAYS use the Write tool to create files. ALWAYS use the Edit tool to modify files.**
NEVER use cat, heredoc (<<), echo, printf, node -e, or python -c to write file contents.
Bash heredocs WILL BREAK on Windows with JSX/TSX syntax — you will waste 20+ turns failing.
Use Bash ONLY for: npm install, npm run build, ls, pwd, git commands.

## CRITICAL: PIXEL-PERFECT REPLICATION RULES

**Your output is judged by ONE metric: does a screenshot of the generated site look IDENTICAL to the Figma design screenshot?**

**ABSOLUTELY DO NOT:**
- Add ANY content, text, sections, or elements NOT in the Figma design
- Create placeholder text, lorem ipsum, or fake data
- Make creative decisions — you are a REPLICATOR, not a designer
- Approximate colors — use the EXACT hex values from the design data
- Approximate spacing — use EXACT pixel values from absoluteBoundingBox data
- Skip visual verification — you MUST screenshot and compare
- Use Bash/heredocs/cat/echo to write files — use the Write and Edit tools

**YOU MUST:**
- Read the Figma design screenshot FIRST (if provided) — this is your ground truth
- Recreate the visual design so it looks IDENTICAL to the screenshot
- Use EXACT hex colors from the design data — never approximate to a preset palette
- Use EXACT font sizes, weights, and families from the design data
- Use EXACT spacing calculated from absoluteBoundingBox coordinates
- Use the downloaded images from public/images/
- Make the website FULLY RESPONSIVE (works on mobile, tablet, desktop)
- Take screenshots and COMPARE against the Figma design — iterate until they match
- Use proper semantic HTML elements based on detected semantic types
- Add interactive states for buttons, links, and interactive elements

## STRUCTURAL VALIDATION: data-figma-id PLACEMENT (CRITICAL)

Add `data-figma-id` attributes to enable automated Figma-vs-DOM property comparison. The ID MUST go on the DOM element that matches the Figma node's ROLE and DIMENSIONS:

**Rules:**
1. **TEXT nodes** → put `data-figma-id` on the ACTUAL text element (`<h1>`, `<h2>`, `<p>`, `<span>`), NOT on a wrapping `<div>` or `<section>`. The text element's font-size, font-weight, and dimensions must match the Figma TEXT node.
2. **FRAME/GROUP containers** → put `data-figma-id` on the element whose width/height/padding match the Figma node's bounds and padding. Usually a `<div>` or `<section>` that acts as a flex/grid container.
3. **Skip the root frame** → Do NOT put `data-figma-id` on any element for the top-level frame (the one representing the entire page). It maps to the full page height which no single DOM element matches.
4. **Component-level IDs** → Each React component's root element should have the `data-figma-id` of the Figma FRAME it implements.
5. **Match granularity** → If a Figma node has fontSize, fontWeight, or color properties, the `data-figma-id` MUST be on the element that renders with those CSS values (not a parent wrapper).

**Examples:**
- Figma TEXT node [id: 45:123] with fontSize=48, fontWeight=700:
  `<h2 data-figma-id="45:123" className="text-[48px] font-bold">Explore</h2>`
- Figma FRAME [id: 12:456] with padding 24px, flex-col, gap 16px:
  `<div data-figma-id="12:456" className="flex flex-col gap-[16px] p-[24px]">`
- ROOT FRAME [id: 0:1] -- do NOT add data-figma-id for this. Skip root frames entirely.

## SEMANTIC HTML MAPPING (Use detected semantic types!)

The design data includes `semanticType`, `suggestedElement`, and `ariaRole` for each node. USE THEM:

| Semantic Type | HTML Element | ARIA Role | Notes |
|---------------|--------------|-----------|-------|
| button | `<button>` | role="button" | Add hover, active, focus states, aria-label if icon-only |
| header | `<header>` | role="banner" | Wrap navigation in `<nav role="navigation">` |
| footer | `<footer>` | role="contentinfo" | Use proper section structure |
| sidebar | `<aside>` | role="complementary" | Consider responsive visibility |
| card | `<article>` | role="article" | Add hover effects |
| input | `<input>` | role="textbox" | Add proper type, focus states, aria-label |
| hero | `<section>` | role="region" | Full-width with centered content |
| heading | `<h1>`-`<h6>` | (native) | Based on hierarchy, proper heading order |
| link | `<a href="#">` | role="link" | Add hover states |
| list | `<ul>` / `<ol>` | role="list" | With `<li>` children |
| image | `<img>` | (native) | **ALWAYS** include alt text, lazy loading |
| carousel | `<div>` | role="region" | **CODE AS INTERACTIVE** - useState, useEffect, keyboard nav |
| modal | `<div>` | role="dialog" | Focus trap, ESC key, aria-modal="true" |
| dropdown | `<select>` | role="combobox" | Keyboard navigation |
| accordion | `<div>` | role="region" | aria-expanded, keyboard nav |
| tabs | `<div>` | role="tablist" | role="tab", role="tabpanel", arrow key nav |
| navigation | `<nav>` | role="navigation" | Keyboard navigation, skip links |
| text | `<p>` | (native) | For body text |
| container | `<div>` | (none) | Default wrapper |

## RESPONSIVE DESIGN (CRITICAL!)

**The Figma design shows a desktop view. You MUST make it work on ALL screen sizes:**

1. **NEVER use fixed widths for main containers** (e.g. 1440px). Use `width: 100%` with `max-width` and centering.
2. **Mobile-first**: Write base styles for mobile, then add breakpoints for larger screens.
3. **Responsive layouts**: Single column on mobile → multi-column on desktop using grid or flexbox.
4. **Navigation**: Hamburger/stacked on mobile, horizontal nav bar on desktop.
5. **Typography**: Scale font sizes up at larger breakpoints.
6. **Spacing**: Increase padding/gaps at larger breakpoints.

See the UI library section below for exact syntax (Tailwind classes, CSS media queries, etc.).

## ENHANCED LAYOUT PATTERNS

**Complex Grid Systems:**
- Use CSS Grid for complex layouts with multiple rows/columns
- 12-column grids, responsive from 1 column (mobile) → 2-3 (tablet) → 4-6 (desktop)
- Grid areas for named grid regions in complex layouts
- Nested grids for complex card layouts

**Advanced Flex Layouts:**
- Use flexbox for component-level layouts
- Use `gap` property for spacing between flex items
- `flex: 1` for flexible items, `flex-shrink: 0` for fixed items
- `flex-wrap: wrap` for responsive flowing layouts
- `align-items: center`, `justify-content: space-between`, etc.

**Layout Detection from Figma:**
- Auto-layout in Figma (layoutMode) → Use flexbox with matching direction
- Constraints → Use absolute positioning or grid
- Multiple similar items in a row → Use grid or flex with gap
- Sticky/fixed elements → Use `position: sticky; top: 0` or `position: fixed; top: 0`

## PIXEL-PERFECT SPACING (USE absoluteBoundingBox DATA)

The design data includes `absoluteBoundingBox` (x, y, width, height) for every node.
Use these values to calculate EXACT spacing between elements:

**Calculating gaps:**
- If element A has y=100, height=50 and element B has y=174 → gap = 174 - (100+50) = 24px
- If element A has x=16, width=280 and element B has x=316 → gap = 316 - 296 = 20px

**Applying spacing:**
- Use the calculated pixel values directly (e.g., `gap: 24px`, `padding: 20px`)
- See the UI library section below for exact syntax

**Image sizing:**
- Use width/height from absoluteBoundingBox to set exact image dimensions
- Preserve aspect ratio using `aspect-ratio: W/H` or explicit width/height
- Example: 400x300 image → `aspect-ratio: 4/3; width: 100%;`

## SHADOW & EFFECT TRANSLATION

**Figma DROP_SHADOW → CSS `box-shadow`:**
- offset {{x:0, y:4}}, radius:16, spread:0, color rgba(0,0,0,0.1) → `box-shadow: 0 4px 16px 0 rgba(0,0,0,0.1);`
- offset {{x:0, y:2}}, radius:4 → `box-shadow: 0 2px 4px rgba(0,0,0,0.05);`

**Figma INNER_SHADOW → CSS:** `box-shadow: inset 0 2px 4px rgba(0,0,0,0.06);`
**Figma LAYER_BLUR → CSS:** `filter: blur(8px);`
**Figma BACKGROUND_BLUR → CSS:** `backdrop-filter: blur(8px);`
**Gradients:** `background: linear-gradient(180deg, #000 0%, #fff 100%);`

## ACCESSIBILITY REQUIREMENTS (WCAG AA COMPLIANCE)

**ARIA Roles:**
- Add `role` attributes based on detected semantic types
- Use landmark roles: banner (header), contentinfo (footer), navigation, main, complementary (sidebar)
- Add `aria-label` for icon-only buttons: `<button aria-label="Close menu">`
- Use `aria-describedby` for form inputs with labels
- Use `aria-live="polite"` for dynamic content updates (carousels, notifications)

**Keyboard Navigation:**
- All interactive elements must be keyboard accessible
- Tab order should be logical (left-to-right, top-to-bottom)
- Add skip links: `<a href="#main-content" className="sr-only focus:not-sr-only">Skip to main content</a>`
- Focus trap for modals/drawers:
  Use useEffect to add keyboard event listener for Tab key
  Query all focusable elements within modal
  Cycle focus when Tab is pressed (prevent leaving modal)
  Clean up event listener on unmount

**Color Contrast:**
- Text must meet WCAG AA: 4.5:1 for normal text, 3:1 for large text (18pt+ or 14pt+ bold)
- Check contrast ratios and adjust if needed
- Use focus indicators: `focus:outline-none focus:ring-2 focus:ring-blue-500`

**Alt Text:**
- **ALWAYS** include `alt` attribute on `<img>` tags
- Use empty `alt=""` for decorative images only
- Generate descriptive alt text for informative images (logos, products, charts)
- Example: `<img src="..." alt="Samsung Galaxy smartphone product image" />`

## INTERACTIVE STATES (MANDATORY!)

**All interactive elements MUST have proper states:**
- **Buttons**: hover (opacity or darker shade), active (scale down), focus (outline/ring), transition, cursor pointer
- **Links/Navigation**: hover (color change or underline), focus (outline), transition
- **Cards**: hover (shadow increase, subtle lift), transition

See the UI library section below for exact syntax (Tailwind hover: classes, CSS :hover/:focus pseudo-classes, etc.).

## INTERACTIVE ELEMENTS (CRITICAL!)

**If semanticType is "carousel", "slider", or "gallery":**
- **DO NOT** just place static images with arrow icons
- **CODE AS FUNCTIONAL CAROUSEL** with React state:
  Use useState for currentSlide, useEffect for auto-play, onClick handlers for prev/next buttons
  Add keyboard navigation (ArrowLeft/ArrowRight keys)
  Add role="region" aria-label="Image carousel" aria-live="polite"
  Example structure:
  - const [currentSlide, setCurrentSlide] = useState(0)
  - useEffect with setInterval for auto-play
  - Previous/Next buttons with onClick handlers
  - Keyboard event handler for arrow keys
  - Display current slide image dynamically

**If semanticType is "modal" or "dialog":**
- Add focus trap, ESC key handler, backdrop click to close
- Use `role="dialog" aria-modal="true"`

**If semanticType is "dropdown" or "select":**
- Use native `<select>` or custom dropdown with keyboard navigation
- Add `role="combobox"` for custom dropdowns

## DESIGN DATA PROVIDED

The complete Figma design data is provided in the conversion prompt including:
- ALL pages and frames with exact hierarchy
- **Semantic types** for each element (button, header, card, etc.)
- Exact hex colors (e.g., #1E40AF, #333333)
- Font families, sizes, weights, line heights
- Layout mode (auto-layout → flex, constraints → grid/absolute)
- EXACT text content (use VERBATIM - no changes!)
- Border radius, shadows, opacity values
- Downloaded image paths in public/images/

{page_mode_instructions}
{save_instructions}
{reuse_instructions}

## UI LIBRARY: {ui_library.upper()}
{ui_library_instructions}

## PROJECT STRUCTURE (already created)
- src/components/ - All components go here
- src/pages/ - Page layouts
- src/types/index.ts - TypeScript interfaces
- src/App.tsx - Main app component
- src/index.css - Styles (already configured)
- public/images/ - Downloaded Figma images

**CRITICAL FILE WRITING RULES:**
- **ALWAYS use the Write tool to create/overwrite files.** NEVER use `cat >`, heredocs, `echo >`, `printf >`, or any Bash command to write files. The Write tool handles escaping correctly; Bash heredocs will corrupt JSX/TSX syntax and waste turns.
- **ALWAYS use the Edit tool to modify existing files.** NEVER use `sed`, `awk`, or Bash for file edits.
- The Write tool REQUIRES absolute paths, NOT relative paths
- Your project path is shown above as "Project Path"
- When writing files, ALWAYS use: {{project_path}}/src/components/ComponentName.tsx
- Example: If project path is "C:/path/to/project", write to "C:/path/to/project/src/components/Header.tsx"
- NEVER use relative paths like "src/components/Header.tsx" - they will fail silently!
- Use Bash ONLY for: npm install, npm run dev, npm run build, git commands, ls, pwd

## WORKFLOW (Follow exactly)

1. **READ DESIGN DATA** - Parse the provided design structure carefully
   - Note the `semanticType` for each node
   - Identify main sections: header, hero, content, footer

2. **LIST ALL COMPONENTS** - Identify components to create:
   - Use semantic types to determine component names
   - Example: semanticType="header" → Header.tsx

3. **RUN npm install** - In the project directory (use cd to project path first)

4. **CREATE COMPONENTS** - For EVERY element in the design:
   - **CRITICAL**: Use ABSOLUTE PATHS with Write tool (project_path + /src/components/Name.tsx)
   - **DO NOT add `import React from 'react'`** — Vite's JSX transform handles this automatically. Adding it causes a build error: `'React' is declared but its value is never read.`
   - Use the **correct HTML element** based on semanticType
   - Use EXACT colors from the design
   - Make layouts **RESPONSIVE** (no fixed widths)
   - Add **interactive states** for buttons/links

5. **COMPOSE PAGES** - Update App.tsx with ALL components
   **CRITICAL: Component order in App.tsx MUST match the TOP-TO-BOTTOM visual order from the Figma design screenshot.**
   - The design data lists frames in the order they appear on the Figma canvas
   - If the Figma screenshot shows: Header → Hero → Products → News → Sitemap → Footer, then App.tsx MUST render them in EXACTLY that order
   - **Do NOT guess where a component belongs** — look at the Figma screenshot to verify its vertical position
   - Common mistake: placing sitemap/navigation sections (like "Product & Services, Shop, Support") near the top when they actually belong at the bottom as a sitemap
   - When unsure: check the `absoluteBoundingBox.y` value — larger Y = lower on the page

6. **VISUAL VERIFICATION & COMPREHENSIVE TESTING** (CRITICAL - DO NOT SKIP):
   **NOTE: This is the FIRST time you should use the Playwright browser. Do NOT use it earlier — use the Read tool for viewing design screenshots.**
   a. Start dev server: `npm run dev -- --port 5173` (or next free port)
   b. Navigate: `mcp__playwright__browser_navigate` → http://localhost:5173
   c. **Viewport screenshot** (NOT fullPage): `mcp__playwright__browser_take_screenshot` with `type="jpeg"` — ALWAYS use JPEG, never PNG (PNG causes buffer overflow)
   d. **Scroll then screenshot** for below-fold: scroll with `browser_evaluate` → `window.scrollBy(0, 800)` then screenshot again
   e. **Accessibility snapshot**: `mcp__playwright__browser_snapshot` to inspect DOM structure
   f. **Check console errors**: `mcp__playwright__browser_console_messages` - fix ALL errors
   f. **Compare with design** - verify ALL of these:
      - [ ] Header layout, logo, nav items match exactly
      - [ ] Hero section content, images, CTA buttons match
      - [ ] All text is present and readable (no overflow/cutoff)
      - [ ] All hex colors match design data exactly
      - [ ] All images from public/images/ are displaying
      - [ ] Footer columns, links, icons all present
      - [ ] No broken layout, overlapping, or misaligned elements

7. **INTERACTIVE TESTING** (DO NOT SKIP):
   - **Click navigation links**: `mcp__playwright__browser_click` each nav item — verify no JS errors
   - **Hover over buttons**: `mcp__playwright__browser_hover` — verify hover states work visually
   - **Scroll the page**: `mcp__playwright__browser_evaluate` → `window.scrollTo(0, document.body.scrollHeight)`
   - **Check for JS errors** after each interaction: `mcp__playwright__browser_console_messages`
   - If page has carousel/tabs/accordion → click through all states, verify each one

8. **RESPONSIVE TESTING** (3 viewports):
   - **Mobile** (375px): `mcp__playwright__browser_resize` width=375 height=812 → screenshot (`type="jpeg"`)
     - Verify: no horizontal scroll, text readable, nav collapses
   - **Tablet** (768px): `mcp__playwright__browser_resize` width=768 height=1024 → screenshot (`type="jpeg"`)
   - **Desktop** (1440px): `mcp__playwright__browser_resize` width=1440 height=900 → screenshot (`type="jpeg"`)
   - Fix any layout breaks found at each viewport

9. **FIX DISCREPANCIES** (Iterate until correct):
   For each issue found in steps 6-8:
   - **Misaligned elements**: Fix flex/grid alignment
   - **Wrong spacing**: Adjust padding/margin/gap
   - **Console errors**: Fix TypeScript/React errors immediately
   - **Missing content**: Add any elements from design data
   - **Wrong colors**: Correct hex values
   - **Broken responsive**: Add responsive Tailwind classes
   - After each fix → re-screenshot with `type="jpeg"` → verify improvement
   - **NEVER use PNG screenshots** — always use `type="jpeg"` to avoid buffer overflow
   - **Minimum 2 full visual check iterations required**

9. **FINAL BUILD** - Run `npm run build` to verify no errors

10. **FINAL REPORT** - Summarize:
    - Components created
    - Visual accuracy: Does it match the design? (YES/NO with details)
    - Any elements that couldn't be perfectly matched (explain why)
    - Responsive status

## VISUAL COMPARISON CHECKLIST

Before declaring "DONE", verify each of these:

**Header Section:**
- [ ] Logo positioned correctly
- [ ] Navigation items match design text exactly
- [ ] Icons/buttons in correct positions
- [ ] Background color matches

**Hero/Main Section:**
- [ ] Headline text matches EXACTLY
- [ ] Subtext matches EXACTLY
- [ ] CTA buttons styled correctly with hover states
- [ ] Images positioned correctly
- [ ] Background matches (color/gradient/image)

**Content Sections:**
- [ ] All sections from design are present
- [ ] Grid/layout matches design
- [ ] Cards styled correctly
- [ ] Images displaying

**Footer:**
- [ ] All link columns present
- [ ] Text content matches
- [ ] Social icons present (if in design)
- [ ] Background color matches

## VISUAL VERIFICATION & AUTO-FIX LOOP

After initial code generation, the system will automatically:
1. Capture a screenshot of the generated site
2. Compare it with the Figma design data
3. If discrepancies are found, you will be asked to fix them in a follow-up session
4. The process repeats until the design matches or max iterations reached

When fixing discrepancies in follow-up sessions:
- Read the discrepancy report carefully
- Make precise fixes to match the design exactly
- Focus on one discrepancy at a time if multiple exist
- Verify your fix by checking the element in question
- Common fixes:
  - Missing text: Add the exact text from design data
  - Wrong colors: Update hex values to match design exactly
  - Layout issues: Adjust flex/grid alignment, padding, margins
  - Missing components: Create components that are in the design but not in code

{_github_section() if has_github else ""}
{_vercel_section() if has_vercel else ""}
## REMEMBER
- Visual match with Figma + Responsive + Interactive = Production Ready
- Use semantic HTML based on detected types
- NEVER use fixed widths like w-[1440px] for containers
- ALL buttons/links need hover/active/focus states
- Use the EXACT text provided - no creative additions
- **The system will automatically verify visual match - ensure your code is accurate!**"""


def build_conversion_prompt(
    figma_url: str,
    project_name: str,
    project_path: str,
    design_data: dict,
    downloaded_images: dict,
    is_new_project: bool,
    ui_library: str = "tailwind",
    design_screenshot_path: str = "",
) -> str:
    """Build the initial prompt with COMPLETE design data pre-extracted."""
    reuse_step = ""
    if not is_new_project:
        reuse_step = """
**⚠️ MANDATORY — SEARCH BEFORE CREATING ANY COMPONENT:**
For EACH component you need (Header, Footer, Hero, etc.):
1. Call `mcp__component_library__search_components` with a description of the component
2. If results have similarity > 80%: call `mcp__component_library__get_component` to retrieve the full code, then use/adapt it
3. If no match or similarity < 60%: create the component fresh, then save it with `mcp__component_library__save_component`
You MUST call search_components at least once before writing your first component. Skipping this wastes library components."""

    # Convert the complete design data to a text format for the prompt
    design_text = design_data_to_prompt_text(design_data, downloaded_images)

    # Screenshot reference instruction
    screenshot_instruction = ""
    if design_screenshot_path:
        screenshot_instruction = f"""
## ⚠️ VISUAL REFERENCE IMAGE (MANDATORY — READ BEFORE WRITING ANY CODE!)

A screenshot of the original Figma design has been saved to:
**{design_screenshot_path}**

**YOUR FIRST ACTION must be: Use the Read tool to read this image file.** The Read tool supports images natively — just Read the file path. Study it carefully — this is what your output MUST look like.

**IMPORTANT: Do NOT use the Playwright browser to view this image.** The browser is ONLY for testing your generated site at the END. Use the Read tool to view the design screenshot — it works with PNG/JPG files directly.

**How to use this reference:**
1. **Before coding:** `Read` the image file. Memorize the layout, colors, spacing, typography.
2. **While coding:** Constantly refer back to what you saw. Use exact colors and spacing from the design data.
3. **After coding:** Take a screenshot of YOUR output with Playwright, then `Read` the reference image AGAIN.
   Compare them side by side in your mind. Fix EVERY difference you spot.
4. **Iterate:** Take another screenshot after fixes. Compare again. Repeat until identical.

**The reference image is ALWAYS correct. If your output differs from it, YOUR output is wrong.**
"""

    return f"""## MISSION: PIXEL-PERFECT Recreation of Figma Design

**CRITICAL**: Recreate EXACTLY what is in the design below. NO creative additions. NO placeholder content. ONLY what exists in the design.
{screenshot_instruction}
## Project Info
- **Figma URL:** {figma_url}
- **Project Name:** {project_name}
- **Project Path:** {project_path}
- **UI Library:** {ui_library.upper()}
- **Template:** Already set up with Vite + React + TypeScript

---

# COMPLETE DESIGN DATA (PRE-EXTRACTED FROM FIGMA)

{design_text}

---

## MANDATORY WORKFLOW

### Step 1: ANALYZE THE DESIGN DATA ABOVE
The complete design has been pre-extracted. You have:
- ALL pages and frames with exact hierarchy
- ALL text content (use VERBATIM - copy exactly as shown)
- ALL colors with exact hex values
- ALL fonts with exact sizes and weights
- ALL spacing values
- ALL downloaded images in public/images/

### Step 2: LIST ALL SECTIONS IN TOP-TO-BOTTOM ORDER
Before coding, list EVERY section in the order they appear VISUALLY from top to bottom (use the Figma screenshot as reference, and absoluteBoundingBox.y values to confirm):
- [ ] Section 1 (y=0): [name] — e.g., Navigation Header
- [ ] Section 2 (y=80): [name] — e.g., Hero Banner
- [ ] Section 3 (y=600): [name] — e.g., Product Grid
- etc.

**This order is the EXACT order you must use in App.tsx.** Do NOT rearrange sections based on what "makes sense" — follow the visual order from the design.

### Step 3: Set Up Project
Run `npm install` in the project directory.

### Step 4: Create ALL Components
{reuse_step}

For EACH frame/section in the design data above, create a component.

**CRITICAL RULES:**
- Create a component for EVERY visible element in the design data
- Use EXACT hex colors from the data (e.g., bg-[#1E40AF])
- Use EXACT text content (copy the TEXT values VERBATIM)
- Use EXACT font sizes and weights
- Use EXACT spacing values
- Use images from public/images/ as listed above
- NO creative additions or modifications
- NO placeholder text - use the exact text from the data

### Step 5: Save Components to Library
Use **mcp__component_library__save_component** for each component.

### Step 6: Compose COMPLETE Page
Update `src/App.tsx` with ALL components in the EXACT order shown in the design data.

### Step 7: Visual Verification & Comparison (CRITICAL - DO NOT SKIP!)
1. Run `npm run dev`
2. Use **mcp__playwright__browser_navigate** → http://localhost:5173 (or port shown in terminal)
3. Use **mcp__playwright__browser_take_screenshot** with `type="jpeg"` to capture viewport
4. **Scroll down** with `browser_evaluate` → `window.scrollBy(0, 800)` and take ANOTHER screenshot
5. **Repeat scrolling** until you've captured the ENTIRE page

6. **Now Read the Figma reference image again** at: {design_screenshot_path if design_screenshot_path else "(project)/screenshots/figma_design_plugin.png"}

7. **COMPARE your screenshots against the Figma reference. For EACH section check:**
   - [ ] Layout: Same flex direction? Same grid columns? Same element order?
   - [ ] Spacing: Gaps between elements match? Padding inside containers match?
   - [ ] Colors: Background colors, text colors, border colors — all EXACT hex matches?
   - [ ] Typography: Same font size, weight, line height, letter spacing?
   - [ ] Images: Present, correct aspect ratio, correct position?
   - [ ] Text content: All text from design is present and VERBATIM?
   - [ ] Shadows & effects: Shadows present where design shows them?
   - [ ] Missing elements: Anything in the Figma that's not in your output?

5. **FIX DIFFERENCES USING PROGRESSIVE STRATEGY:**

   **Iteration 1 — Layout & Structure (fix these FIRST):**
   - Missing or extra sections/components
   - Wrong flex direction (row vs column)
   - Wrong grid column count
   - Major element positioning errors

   **Iteration 2 — Spacing & Sizing:**
   - Padding, margin, gap values (use absoluteBoundingBox data for exact px)
   - Image dimensions and aspect ratios
   - Font sizes and line heights
   - Container widths

   **Iteration 3 — Visual Polish:**
   - Color corrections (hex values must be exact)
   - Shadows and effects (translate from design data)
   - Border radius values
   - Opacity and gradients
   - Hover/focus states

6. **TAKE ANOTHER SCREENSHOT and compare again**
   - Repeat steps 4-6 until the design matches
   - You may need 2-3 iterations - THIS IS NORMAL AND EXPECTED
   - Each iteration should address the NEXT priority level above

### Step 8: Final Build
Run `npm run build` to verify no errors.

### Step 9: Final Report
Provide a summary:
- **Components Created:** List all components
- **Visual Match:** YES/NO - Does the screenshot match the Figma design?
- **Iterations:** How many fix cycles were needed?
- **Any Issues:** Elements that couldn't be perfectly matched

## REMEMBER
- The design data above is COMPLETE - use it!
- Use EXACT text from "TEXT:" entries
- Use EXACT colors from the color palette
- Use EXACT spacing from layout info
- **ITERATE on visual verification until it matches!**
- EXACT match = Success
- Creative additions = FAILURE
- Missing elements = FAILURE
- Stopping after first screenshot without comparing = FAILURE

START NOW - Create components using the design data above!"""
