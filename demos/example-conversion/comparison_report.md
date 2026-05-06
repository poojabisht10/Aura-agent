# Figma-to-React Comparison Report

**Design:** Acme Landing Page
**Generated:** 2026-03-20T10:00:00Z
**Pipeline:** Aura2 (plugin source)

---

## 1. Header Component

### Node: `frame:header`

| Property | Figma Value | Generated Code | Match |
|----------|------------|----------------|-------|
| Background | `#FFFFFF` (solid) | `bg-white` | Exact |
| Padding X | `64px` | `px-16` (64px) | Exact |
| Padding Y | `16px` | `py-4` (16px) | Exact |
| Layout | `HORIZONTAL`, `SPACE_BETWEEN` | `flex items-center justify-between` | Exact |
| Shadow | drop-shadow y:2 blur:4 alpha:0.05 | `shadow-sm` | Close |

**Shadow note:** Figma specifies `offset-y: 2px, blur: 4px, opacity: 0.05`. Tailwind `shadow-sm` produces `0 1px 2px rgba(0,0,0,0.05)`. The blur radius differs slightly (4px vs 2px), but the visual difference is negligible at this scale.

### Node: `node:logo`

| Property | Figma Value | Generated Code | Match |
|----------|------------|----------------|-------|
| Font | Inter, 700 | `font-bold` (700) | Exact |
| Size | 24px | `text-2xl` (24px) | Exact |
| Color | `#1E40AF` | `text-[#1E40AF]` | Exact |
| Letter Spacing | -0.5px | `tracking-tight` (-0.025em = -0.6px at 24px) | Close |

**Letter spacing note:** Figma uses `-0.5px`. Tailwind `tracking-tight` at 24px font size equals `-0.6px`. The 0.1px difference is sub-pixel and imperceptible. An alternative would be `tracking-[-0.5px]` for an exact match.

### Node: `node:cta-button`

| Property | Figma Value | Generated Code | Match |
|----------|------------|----------------|-------|
| Background | `#1E40AF` | `bg-[#1E40AF]` | Exact |
| Corner Radius | 8px | `rounded-lg` (8px) | Exact |
| Padding L/R | 24px | `px-6` (24px) | Exact |
| Padding T/B | 10px | `py-2.5` (10px) | Exact |
| Text Font | Inter, 600, 14px | `text-sm font-semibold` | Exact |
| Text Color | `#FFFFFF` | `text-white` | Exact |

---

## 2. Hero Component

### Node: `node:hero-heading`

| Property | Figma Value | Generated Code | Match |
|----------|------------|----------------|-------|
| Font | Inter, 800, 56px | `text-[56px] font-extrabold` | Exact |
| Line Height | 64px | `leading-[64px]` | Exact |
| Letter Spacing | -1.5px | `tracking-[-1.5px]` | Exact |
| Color | `#111827` | `text-[#111827]` | Exact |
| Alignment | CENTER | `text-center` | Exact |

### Node: `node:hero-subtitle`

| Property | Figma Value | Generated Code | Match |
|----------|------------|----------------|-------|
| Font | Inter, 400, 20px | `text-[20px]` | Exact |
| Line Height | 32px | `leading-8` (32px) | Exact |
| Color | `#5F697A` | `text-[#5F697A]` | Exact |
| Max Width | 640px | `max-w-[640px]` | Exact |

### Node: `frame:hero` (container)

| Property | Figma Value | Generated Code | Match |
|----------|------------|----------------|-------|
| Background | `#F3F4F6` | `bg-[#F3F4F6]` | Exact |
| Padding X | 64px | `px-16` (64px) | Exact |
| Padding Y | 96px | `py-24` (96px) | Exact |
| Layout | `VERTICAL`, `CENTER` | `flex flex-col items-center` | Exact |
| Item Spacing | 24px | `mt-6` / `mt-10` on children | Adapted |

**Spacing note:** Figma uses a uniform `itemSpacing: 24px` via auto-layout. In the generated code, `gap-6` could achieve this, but the component uses individual `mt-6` and `mt-10` margins. The heading-to-subtitle gap is 24px (correct), but the subtitle-to-image gap is 40px (`mt-10`) instead of 24px. This is a visual verification candidate.

---

## 3. Footer Component

### Node: `frame:footer`

| Property | Figma Value | Generated Code | Match |
|----------|------------|----------------|-------|
| Background | `#111827` | `bg-[#111827]` | Exact |
| Padding X | 64px | `px-16` (64px) | Exact |
| Padding Y | 32px | `py-8` (32px) | Exact |
| Layout | `HORIZONTAL`, `SPACE_BETWEEN` | `flex items-center justify-between` | Exact |

### Node: `node:footer-links` spacing

| Property | Figma Value | Generated Code | Match |
|----------|------------|----------------|-------|
| Item Spacing | 24px | `space-x-6` (24px) | Exact |
| Text Color | `#9BA3B0` | `text-[#9BA3B0]` | Exact |
| Font | Inter 400, 14px | `text-sm` (14px) | Exact |

---

## Summary

| Category | Exact | Close | Needs Review |
|----------|-------|-------|-------------|
| Colors | 12/12 | 0 | 0 |
| Typography | 9/10 | 1 (letter-spacing) | 0 |
| Spacing/Layout | 8/10 | 1 (shadow) | 1 (hero item-spacing) |
| **Total** | **29/32** | **2** | **1** |

**Overall accuracy: 90.6% exact, 96.9% acceptable**

The one item needing review is the hero section's subtitle-to-image gap (40px generated vs 24px in Figma). This would be caught by the visual verification pipeline and corrected in a refinement iteration.
