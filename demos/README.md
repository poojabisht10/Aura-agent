# Aura2 Demos

This directory contains demonstration materials showing how Aura2 converts Figma designs to React code. Each subdirectory is a self-contained example that can be walked through independently.

## Demos

### [example-conversion/](./example-conversion/)

A complete end-to-end conversion example using a synthetic "Acme Landing Page" design. Demonstrates:

- **Figma data ingestion**: Raw API response, processed design data, and extraction metadata
- **Code generation**: React components with Tailwind CSS generated from the design data
- **Property traceability**: Each component includes `data-figma-id` attributes linking back to source frames
- **Visual verification**: A detailed comparison report mapping Figma properties to generated CSS, showing exact matches, close matches, and items flagged for review

Start with `example-conversion/README.md` for a guided walkthrough.

### [cross-page-reuse/](./cross-page-reuse/)

Shows how Aura2 handles multi-page designs by building a component library and reusing components across pages. Demonstrates:

- **Page 1 (Homepage)**: Three components created from scratch and saved to the library
- **Page 2 (Contact Page)**: Two components reused from the library (Header at 0.92 similarity, Footer at 0.88), one new component created
- **Reuse statistics**: JSON report with per-page and aggregate metrics

Start with `cross-page-reuse/README.md` for the full scenario.

## Notes

- All Figma data in these demos is **synthetic** -- it was created to be realistic and representative, not extracted from an actual Figma file.
- The generated components follow the same patterns as real Aura2 output (Tailwind classes, `data-figma-id` attributes, Inter font references).
- For real conversion examples, see the `generated_projects/` directory in the repository root.
