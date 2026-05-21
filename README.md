# ConstraintLens

A Fusion 360 add-in that docks a panel listing every sketch constraint — with click-to-select, delete, and over/under-constrained status. Closes the long-standing UX gap of having to hunt tiny on-canvas glyphs to audit a sketch.

See [`SPEC.md`](./SPEC.md) for the full architectural specification.

## Features

- **All constraint types listed** — 21 geometric constraint subtypes (Parallel, Perpendicular, Coincident, Tangent, Equal, Concentric, Midpoint, Symmetric, Offset, Polygon, Circular/Rectangular Pattern, and more), plus all sketch dimension types (Linear, Angular, Radial, Diameter, Offset Curves, etc.).
- **Implicit endpoint joins** — reconstructed from shared `SketchPoint` instances and shown as pseudo-rows with an "implicit" badge and lock indicator.
- **Click row → select entities** — highlights the constraint's referenced geometry in the Fusion viewport.
- **⌖ Select constraint** button — selects the constraint object itself so you can use Fusion's native Delete key.
- **× Delete** button per row — calls `constraint.deleteMe()`, disabled when `isDeletable == False`.
- **Sketch status banner** — shows sketch name, component, fully/under-constrained state, and any `healthState` warning.
- **Auto-refresh** — updates on every `commandTerminated` event (after every sketch edit) without manual intervention; plus a manual **Refresh** button as backstop.
- **Graceful empty state** — shows "No active sketch" when no sketch is being edited.

## Requirements

- Fusion 360 January 2026 release or later (Python 3.14 runtime).
- Windows or macOS.

## Install

1. Download the latest `ConstraintLens-vX.Y.Z.zip` from [**Releases**](../../releases).
2. Extract the `ConstraintLens/` folder.
3. Copy it into your Fusion add-ins directory:
   - **Windows**: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`
   - **macOS**: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`
4. In Fusion: **Tools → Scripts and Add-Ins → Add-Ins** tab → select **ConstraintLens** → **Run**.
   - Tick **Run on Startup** to load it automatically on every Fusion launch.
5. The **Constraint Lens** button appears in **Solid → Tools → Scripts and Add-Ins** panel.

## Usage

1. Open a Fusion design and enter a sketch for editing (double-click a sketch in the browser).
2. Click **Constraint Lens** in the toolbar. A docked palette opens listing every constraint and dimension.
3. Click any row to select the referenced geometry in the viewport.
4. Use **×** to delete a constraint. The list refreshes automatically.
5. Click **⌖** to select the constraint object itself, then press `Delete` in Fusion for an alternative delete path.

## Folder structure

```
FusionConstraints/
├── SPEC.md                        Architectural spec.
├── ConstraintLens/                The Fusion add-in (copy this folder into AddIns/).
│   ├── ConstraintLens.manifest
│   ├── ConstraintLens.py
│   ├── lib/                       Python backend modules.
│   └── palette/                   HTML/JS/CSS palette UI (vanilla JS, no build step).
└── tests/
    ├── fixture_sketch/            Deterministic test sketch — 4 constraints, 2 dims, 4 implicit joins.
    ├── fixture_midpoint/          Triggers the M-1 midpoint-to-midpoint landmine for defensive testing.
    └── spike_probe/               API-feasibility probe; re-run after each Fusion update.
```

To run a test script: **Tools → Scripts and Add-Ins → Scripts → +** → point at the subfolder → **Run**.

## Known limitations (MVP scope)

- No granular CAD undo for **Delete** — Fusion's `Ctrl+Z` reverts the whole sketch-edit chunk.
- Implicit coincident endpoint joins cannot be deleted from the panel (they are shared `SketchPoint` instances, not true constraints).
- `CircularPatternConstraint` and `RectangularPatternConstraint` rows show only **Delete** — the API exposes no usable entity accessors for these types.
- `AssemblyConstraint` (Constrain Components, January 2026 preview API) is not supported; revisit when Autodesk drops the preview disclaimer.
- Palette data may be stale after minimizing/restoring the palette window — use **Refresh** or perform any sketch action to trigger a rescan.
- `OffsetConstraint` label shows `@ ?` for the distance because `OffsetConstraint.distance` returns `None` in the January 2026 build. The distance is correctly shown on the `SketchOffsetCurvesDimension` row.

## License

MIT — see [`LICENSE`](./LICENSE).
