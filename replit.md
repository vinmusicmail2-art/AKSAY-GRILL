# Аксай Гриль — Static Site

Single-page static HTML site for "Аксай Гриль" using Tailwind CSS via CDN. Implements the "Terracotta Hearth" design system (see `DESIGN.md`).

## Project Layout
- `index.html` — main page (renamed from `code.html`)
- `DESIGN.md` — design system reference
- `screen.png` — design reference screenshot

## Running locally
A workflow named "Start application" serves the site on port 5000 via `python -m http.server 5000 --bind 0.0.0.0`.

## Deployment
Configured as a `static` deployment with `publicDir = "."`.
