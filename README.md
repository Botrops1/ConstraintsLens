# ConstraintLens

A Fusion 360 add-in that docks a panel listing every constraint in the active sketch — with click-to-select, delete, and over/under-constrained status. Closes the long-standing UX gap of having to hunt tiny on-canvas glyphs to audit a sketch.

See [`SPEC.md`](./SPEC.md) for the architectural specification.

## Status

Pre-MVP scaffold. The full module structure, dispatch table, and palette UI are in place; runtime verification of the five open questions in `SPEC.md` section 10 is still pending.

## Install (development)

ConstraintLens requires Fusion 360 (January 2026 release or later, Python 3.14).

1. Clone this repository.
2. Copy or symlink the `ConstraintLens/` folder into your Fusion add-ins directory:
   - **Windows**: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`
   - **macOS**: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`
3. In Fusion: **Tools → Scripts and Add-Ins → Add-Ins** tab. Select **ConstraintLens** and click **Run**. Tick *Run on Startup* if you want it loaded automatically.
4. The **Constraint Lens** button appears in **Solid → Tools → Scripts and Add-Ins** (panel id is verified at runtime via the spike probe; see below).

## Verifying the install

Before relying on ConstraintLens, run the test scripts under `tests/`:

1. **Fixture** — Tools → Scripts and Add-Ins → **Scripts** tab → **+** → point at `tests/fixture_sketch/` → **Run**. Creates a deterministic sketch named `ConstraintLens_Fixture` with 4 explicit constraints, 2 dimensions, and 4 implicit endpoint joins.
2. **Spike probe** — same workflow, point at `tests/spike_probe/`. Open the fixture sketch for edit first. The probe writes a full report to your OS temp directory (`constraintlens_probe.txt`) and previews it in a message box; paste that file contents back to the developer to validate the five open questions in `SPEC.md` section 10.

## Folder structure

```
FusionConstraints/
├── SPEC.md                        Architectural spec — read first.
├── ConstraintLens/                The Fusion add-in (drop this into AddIns/).
│   ├── ConstraintLens.manifest
│   ├── ConstraintLens.py
│   ├── lib/                       Python modules (see SPEC.md section 4).
│   └── palette/                   HTML/JS/CSS palette UI.
└── tests/
    ├── fixture_sketch/            Deterministic test sketch (point Fusion Scripts at this folder).
    ├── fixture_midpoint/          M-1 landmine trigger fixture.
    └── spike_probe/               API-feasibility probe (run once per Fusion update).
```

## Known limitations

- No granular CAD undo for `Delete` actions in MVP — Fusion's `Ctrl+Z` reverts the whole sketch-edit chunk.
- Implicit coincident endpoint joins cannot be deleted from the panel (they are shared `SketchPoint` instances, not true constraints).
- `CircularPatternConstraint` and `RectangularPatternConstraint` rows expose only `Delete` (the API exposes no usable accessors).
- Assembly-level `AssemblyConstraint` (Constrain Components, January 2026 preview API) is intentionally not supported; revisit when Autodesk drops the preview disclaimer.

## License

MIT — see [`LICENSE`](./LICENSE).
