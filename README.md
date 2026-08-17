# blueband-concept

Product-concept model of the BlueBand wristband module — form and
material only, not manufacturable CAD. Companion to `blueband-cad`
(the real CAD side).

## Files

- `build.py` — reproducible Blender build script. Constructs the
  module shell, USB-C mouth, squeeze dimples, seam groove, ribbon
  band, and named internal parts (`pcb`, `cell`, `usbc`) at true
  positions. Sets up per-camera lighting rigs and renders five
  canonical shots.
- `blueband_concept.blend` — the built scene (auto-saved by
  `build.py`). Editable interactively.
- `renders/` — the five canonical shots:
  1. `01_three_quarter_with_band.png` — module in band context
  2. `02_module_alone.png` — module three-quarter
  3. `03_side_profile.png` — straight-on side, thickness judgeable
  4. `04_port_face.png` — +Y end face showing USB-C port
  5. `05_minus_x_dimple.png` — squeeze-release dimple close-up

## Rebuilding

```
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --python build.py -- ./renders
```

Requires Blender 5.0+ (uses `MANIFOLD` boolean solver on shell,
`EXACT` on drafted-wall dimples).

Every dimension is in millimetres; Blender scene unit scale is
set to 0.001 (1 Blender unit = 1 mm) so numerical values in the
script are real millimetres.

## Design intent (not spec — see `../blueband-cad/DECISIONS.md` for the real spec)

- 26 × 40 × 13 mm module, elongated (breaks the near-square v1)
- 4 mm plan corner radius (not 9, which ate the whole form)
- 6° draft on ±X and −Y walls; +Y stays perpendicular for the port
- Top perimeter fillet 0.8 mm (crisp shoulder)
- Bottom perimeter fillet 3.5 mm (soft, lower third dissolves)
- Seam groove at Z = −2 mm — puts ~65 % of the visible mass above
  the seam so the read is "top shell dominant, bottom shell shallow"
  rather than "tub with a lid"
- Flat ribbon band (20 × 1.2 mm), exits at seam level on both ±Y
  faces, darker than shell, procedural noise for surface variation
- Cradle is not modelled — with mid-height band exit, the internal
  cradle is entirely inside the module silhouette and never visible

## What this is not

Not the CAD. Real geometry, tolerances, cell selection, wall-thickness
safety checks etc. live in `blueband-cad/`. This repo exists only for
marketing / concept renders. Any dimension mismatch between the two
is the CAD's fault — CAD is authoritative.
