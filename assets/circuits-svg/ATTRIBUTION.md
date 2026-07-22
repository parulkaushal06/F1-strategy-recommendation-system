# Circuit SVGs — Attribution

Circuit layout SVGs in this folder are sourced unmodified from:

**F1 Circuits SVG** by ROY Jules
Repository: https://github.com/julesr0y/f1-circuits-svg
License: Creative Commons Attribution 4.0 International (CC BY 4.0) — full text in `LICENSE`

## What's here

- `circuits/minimal/` — track outline only, 4 styles (black, black-outline, white, white-outline)
- `circuits/detailed/` — track outline + start/finish line + direction arrow (2026-era layouts only)
- `circuits.json` — metadata: circuit id, name, country, lat/lng, and every historical layout
  (`layoutId` like `spa-francorchamps-3`) with the seasons it was used

Each circuit may have multiple layout files (`-1`, `-2`, ...) for different track configurations
used across F1 history — cross-reference `circuits.json` for which seasons each layout covers.

## Using these

For the dark UI theme in this project, `circuits/minimal/white-outline/` and
`circuits/detailed/white-outline/` read best against the `--surface-0` / `--surface-1`
backgrounds. Default stroke-width is 20px (outline) / 5px (inner) — restyle via the SVG's
inline `style` attribute to match design tokens (`--ink-secondary`, `--status-teal`, etc.).

No modifications have been made to the SVG files themselves as copied into this folder.
