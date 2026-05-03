# Terracotta Hearth Design System

### 1. Overview & Creative North Star
**Creative North Star: The Rustic Sophisticate**
Terracotta Hearth is a design system that balances the warmth of artisanal craftsmanship with the clarity of modern editorial layouts. It moves away from the clinical "app-like" feel in favor of a sensory, grounded experience. By utilizing asymmetrical bento-grid layouts and high-contrast typography, the system creates a digital environment that feels as tactile as a hand-thrown ceramic plate or a sun-drenched stone courtyard.

### 2. Colors
The palette is rooted in Earth tones—deep clay reds, ochre accents, and creamy parchment neutrals.
- **Primary Roles:** The `primary` (#9B3F1C) is a rich terracotta used for branding and key CTAs. `Tertiary` (#FDC39A) provides a sun-kissed highlight for accents.
- **The "No-Line" Rule:** Sectioning is achieved through color blocks. For example, the sidebar uses `surface` while the main feed uses `surface_container_low`. Do not use 1px borders to separate major sections.
- **Surface Hierarchy & Nesting:** Use `surface_container_lowest` (#FFFFFF) for cards to make them pop against `surface_container_low` (#F8F3E9) backgrounds.
- **The "Glass & Gradient" Rule:** The header and mobile navigation use a backdrop-blur of 80% opacity on `surface` to maintain a sense of airiness over the dense, earthy content.

### 3. Typography
The system uses a serif-italic display style paired with a clean, high-legibility sans-serif for body copy.
- **Typography Scale:**
    - **Display/Hero:** 3.75rem (60px) up to 8rem. Uses *Newsreader Italic* with a thin weight (300).
    - **Headlines:** 1.5rem to 2.25rem. Uses *Newsreader Italic* to convey personality.
    - **Body Text:** 1.125rem (18px) for lead paragraphs and 0.875rem (14px) for descriptions. Uses *Montserrat* (or *Manrope*) for a neutral, functional balance.
    - **Labels/Utility:** 0.75rem (12px) to 10px. Uses *Plus Jakarta Sans* or *Be Vietnam Pro* for technical clarity.
- **Typographic Rhythm:** The contrast between the large, italicized Newsreader titles and the geometric stability of the body text creates an "Editorial Magazine" feel.

### 4. Elevation & Depth
Depth is created through tonal stacking and soft, atmospheric shadows rather than structural lines.
- **The Layering Principle:** A three-tier stack is preferred: `surface` (base) -> `surface_container_low` (content area) -> `surface_container_lowest` (interactive card).
- **Ambient Shadows:** The system uses `shadow-lg` (approximately `0 10px 15px -3px rgba(155, 63, 28, 0.1)`)—a soft, primary-tinted shadow that suggests the object is floating just above the surface.
- **Glassmorphism:** Navigation bars use `backdrop-blur-xl` with an 80% opacity fill of the background color to suggest a "frosted clay" effect.

### 5. Components
- **Buttons:** Primary buttons are large, rounded-lg (8px), and utilize a `primary` background with `on_primary` text. They should have a subtle `shadow-lg` to indicate interactivity.
- **Cards:** Cards are `rounded-xl` (12px) and use `surface_container_low`. On hover, they should scale slightly (1.02x) and increase shadow depth.
- **Bento Grid:** Use asymmetric offsets (e.g., `translate-y-12`) for alternating items in a grid to break the rigid structure and create visual rhythm.
- **Icons:** Use *Material Symbols Outlined*. For active states, switch to a `FILL 1` setting and use the `primary` color.

### 6. Do's and Don'ts
**Do:**
- Use italics for all brand-driven headlines to maintain the "Hearth" personality.
- Apply wide spacing (`spacing: 3`) to allow elements room to breathe.
- Use primary-tinted shadows for white elements.

**Don't:**
- Do not use pure black (#000000) for text; use `on_surface` (#1D1C16) to keep the look organic.
- Avoid sharp corners (radius 0); always use at least `rounded-lg` for components.
- Do not use traditional divider lines; let white space and background shifts define the boundaries.