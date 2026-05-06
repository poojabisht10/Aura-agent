# Cross-Page Component Reuse Demo

This directory demonstrates how Aura2 reuses components across multiple pages of a multi-page Figma design. When converting page-by-page, the system builds a component library and checks each new frame against existing components before generating new code.

## The Scenario

A two-page website: a **Homepage** and a **Contact Page**. Both pages share a Header and Footer, but the Contact Page also has a unique form.

## What Happened

### Page 1: Homepage

The first page was converted with no existing library. All three components were generated from scratch and saved to the component library.

| Component | Action | Library After |
|-----------|--------|---------------|
| Header | Created new | 1 |
| Footer | Created new | 2 |
| Button | Created new | 3 |

See: `page1/Header.tsx`, `page1/Footer.tsx`, `page1/Button.tsx`

### Page 2: Contact Page

When the second page was converted, each frame was compared against the library:

| Component | Action | Similarity | Notes |
|-----------|--------|-----------|-------|
| Header | Reused | 0.92 | Nav link text differs slightly |
| Footer | Reused | 0.88 | Has one additional link |
| ContactForm | Created new | -- | No similar component in library |

See: `page2/Header.tsx`, `page2/Footer.tsx`, `page2/ContactForm.tsx`

## How Reuse Works

1. **Embedding comparison**: Each Figma frame is converted to a structural embedding. This is compared against all existing library components using cosine similarity.
2. **Threshold**: Components with similarity above 0.85 are considered reusable. The existing code is used as a base, with only the differing properties updated.
3. **Library growth**: New components (below the threshold) are generated from scratch and added to the library for future pages.

## Results

- **Reuse rate**: 33.3% (2 out of 6 total component slots were reused)
- **Code savings**: The reused Header and Footer did not need full regeneration, reducing LLM calls and ensuring visual consistency across pages
- **Library size**: 4 unique components after both pages

See `reuse_report.json` for the full statistics.

## Directory Structure

```
cross-page-reuse/
  page1/
    Header.tsx       -- Created new, saved to library
    Footer.tsx       -- Created new, saved to library
    Button.tsx       -- Created new, saved to library
  page2/
    Header.tsx       -- Reused from library (similarity: 0.92)
    Footer.tsx       -- Reused from library (similarity: 0.88)
    ContactForm.tsx  -- Created new, added to library
  reuse_report.json  -- Statistics for both pages
```
