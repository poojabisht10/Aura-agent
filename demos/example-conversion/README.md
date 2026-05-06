# Example Conversion Demo

This directory contains a synthetic but realistic example of what Aura2 produces when converting a Figma design to React code. It demonstrates the full pipeline output from Figma JSON ingestion through to generated components.

## Directory Structure

```
example-conversion/
  figma_data/
    raw_figma_response.json   -- Simulated Figma API response (abbreviated)
    design_data.json          -- Processed design data used by the generation pipeline
    design_metadata.json      -- Stats and metadata about the extraction
  src/
    components/
      Header.tsx              -- Generated header component
      Hero.tsx                -- Generated hero section component
      Footer.tsx              -- Generated footer component
  screenshots/
    README.md                 -- Placeholder for visual comparison screenshots
  comparison_report.md        -- Detailed property-by-property comparison
```

## What Each File Represents

### Figma Data (`figma_data/`)

- **`raw_figma_response.json`** is the kind of data the Figma REST API or plugin sends. It contains the document tree with frame bounding boxes, layout modes, and style references. In a real conversion, this is the starting point.

- **`design_data.json`** is the processed and enriched version. The Aura2 pipeline flattens the Figma tree into a page-and-frames structure with resolved colors (hex values), typography details, image references, and layout properties. This is what the code generation agent actually reads.

- **`design_metadata.json`** records when the extraction happened, how it was sourced (plugin vs API), and summary statistics (page count, frame count, colors, fonts, images).

### Generated Components (`src/components/`)

Each `.tsx` file corresponds to a top-level frame in the Figma design. Notice:

- Every component has a `data-figma-id` attribute linking it back to its source frame
- Tailwind classes map directly to Figma properties (colors, spacing, typography)
- Comments in the code reference the original Figma values for traceability

### Comparison Report (`comparison_report.md`)

The comparison report walks through specific Figma nodes and shows exactly how each property was translated. It highlights:

- **Exact matches** (e.g., `#1E40AF` to `bg-[#1E40AF]`)
- **Close matches** (e.g., letter-spacing -0.5px to `tracking-tight` which is -0.6px)
- **Items needing review** (e.g., hero item spacing discrepancy)

This is the kind of analysis the visual verification pipeline performs automatically.

## How to Use This Demo

1. Open `figma_data/design_data.json` and pick any node (e.g., `node:cta-button`)
2. Find the corresponding component in `src/components/Header.tsx`
3. Cross-reference with `comparison_report.md` to see the property mapping
4. This flow demonstrates how Aura2 maintains traceability from design to code
