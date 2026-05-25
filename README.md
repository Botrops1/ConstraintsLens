# ConstraintLens

A Fusion 360 add-in that docks a panel listing every sketch constraint and dimension — with click-to-select, delete, filter, and full diagnosis of over/under-constrained sketches.

Fills the long-standing UX gap of having to hunt tiny on-canvas glyphs to audit and repair a sketch.

---

## Requirements

- Fusion 360 January 2026 release or later (Python 3.14 runtime).
- Windows or macOS.

---

## Installation

1. Download the latest `ConstraintLens-vX.Y.Z.zip` from [**Releases**](../../releases).
2. Extract so that you have a `ConstraintLens/` folder (not a nested `ConstraintLens/ConstraintLens/`).
3. Copy the `ConstraintLens/` folder into your Fusion add-ins directory:
   - **Windows:** `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`
   - **macOS:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`
4. In Fusion: **Tools → Scripts and Add-Ins → Add-Ins** tab → select **ConstraintLens** → **Run**.
   - Tick **Run on Startup** to load it automatically on every Fusion launch.
5. The **Constraint Lens** button appears in the **Sketch → Constraints** panel (visible while editing a sketch).

---

## Quick start

1. Open a design and double-click a sketch in the browser tree to enter sketch-edit mode.
2. Click **Constraint Lens** in the Sketch toolbar. A floating palette appears immediately — no Refresh needed.
3. The palette lists every geometric constraint, dimension, and implicit endpoint join in the sketch.
4. Click any row to highlight the constraint's geometry in the viewport.

---

## The palette interface

```
┌──────────────────────────────────────────┐
│  Sketch3 (Body1) — under-constrained  ⊞ ☀│  ← name bar (dock / theme toggles)
├──────────────────────────────────────────┤
│  [Clear] [Delete 0] [Show u/c] [Find] [Refresh] │  ← toolbar
├──────────────────────────────────────────┤
│  🔍 Filter by label or type…             │  ← filter bar
├──────────────────────────────────────────┤
│  Selected: Line 3                        │  ← entity readout (canvas→palette)
├──────────────────────────────────────────┤
│  GEOMETRIC CONSTRAINTS (6)             ▾ │  ← collapsible section header
│  [⊥] Perpendicular — Line 1 ⊥ Line 2   □│
│  [∥] Parallel — Line 3 ∥ Line 4        □│
│  …                                       │
│  DIMENSIONS (3)                        ▾ │
│  [◇] Linear: 40 mm   Line 1 → Line 3  □│
│  …                                       │
│  ENDPOINT JOINS (4)                    ▾ │
│  [⊘] Endpoint join — Point 1 connects…  │
└──────────────────────────────────────────┘
```

### Sketch name bar (top row)

Shows the sketch name, parent component, and constrained state:
- **Green** — fully constrained.
- **Yellow/orange** — under-constrained (some geometry is still free).
- **Red** — over-constrained or has errors.
- Any `healthState` warning message is shown inline.

Two toggle buttons sit on the right end of the name bar:

| Button | What it does |
|---|---|
| **⊞ / ⊟** (dock toggle) | ⊞ docks the palette to the right column; ⊟ returns it to a free-floating, resizable window. Preference is saved to `settings.json` and restored on the next Fusion launch. Default is floating. |
| **☀ / 🌙** (theme toggle) | Switches between dark (default) and light theme. Preference is saved in `localStorage` and restored when the palette is reopened. |

### Toolbar (buttons row)

| Button | What it does |
|---|---|
| **Clear** | Deselects all checked rows (visible only when rows are checked). |
| **Delete N** | Deletes all checked rows at once after a confirmation prompt (visible only when rows are checked). |
| **Show underconstraint elements** | Calls Fusion's built-in Show Underconstrained command and displays the result as a toast. Requires an active sketch edit context. |
| **Find** | Reads the currently selected entity on the canvas and scrolls the palette to every row that references it, highlighted in blue. |
| **Refresh** | Manually re-scans the active sketch. Usually not needed — the palette refreshes automatically after every sketch edit. |

### Filter bar

Type any text to narrow the list. Matches against constraint labels, constraint type names, and entity chip labels (e.g. type `"Line 3"` to find every constraint that involves Line 3). The section headers update to show `(N of M)` when a filter is active. Clear the field to restore the full list.

### Entity readout strip

Appears below the filter bar when **Find** is used. Shows the canvas label of the selected entity ("Selected: Line 3") so you know which entity the palette is currently highlighting rows for.

---

## Interactions

### Click a row → select entities in viewport

Clicking anywhere on a row selects all geometry that the constraint references in the Fusion viewport. The canvas highlights the selected entities. Click again or use Fusion's **Escape** to deselect.

### Click the constraint icon → select the constraint object itself

Each row has a type icon on the left (e.g. the Parallel glyph, the Perpendicular glyph). **Clicking the icon** selects the constraint object itself — not just its referenced geometry. This lets you use Fusion's native **Delete** key as an alternative way to remove a constraint.

> This is different from clicking the row body: clicking the row selects geometry; clicking the icon selects the constraint.

### Hover for tooltips

Hover over any button or row element to see a tooltip explaining what it does. Icon glyphs show the constraint type name on hover.

### Double-click a row → open Fusion's edit dialog

Double-clicking a row opens the native Fusion edit dialog for that constraint or dimension:
- **Dimensions** (Linear, Angular, Radial, Diameter, etc.) — opens the standard dimension editor so you can change the value.
- **Offset curves dimension** — opens the Offset Curves edit dialog.
- **Circular / Rectangular pattern** — opens the corresponding pattern edit dialog.

Geometric constraints (Parallel, Perpendicular, etc.) do not have an edit dialog in Fusion — double-click does nothing for those rows.

### Inline edit a dimension expression (pencil icon)

Every dimension row shows its expression value in accent color (e.g. `40 mm`). **Hover** over the expression to reveal a pencil (✎) icon. **Click the pencil** to open an inline text field directly in the palette:
- Type a new expression (e.g. `50 mm` or a parameter name like `width`).
- Press **Enter** to commit. The sketch updates immediately and the list refreshes.
- Press **Escape** to cancel without changes.

Pattern constraints also expose inline editable fields:
- **Circular pattern** — edit quantity (count) and total angle.
- **Rectangular pattern** — edit count and spacing in each direction.

### Click an entity chip → filter and select

Each row shows small entity chips below the label (e.g. `Line 2`, `Circle 1`). Clicking a chip does two things at once:
1. Sets the filter bar to that entity's label, narrowing the list to every constraint involving it.
2. Selects that entity on the canvas (same as clicking it in the viewport).

This is the fastest way to answer "what constraints involve this line?".

### Bulk delete

Check the checkbox on the right side of any row to select it for bulk deletion. Multiple rows can be checked at once. When at least one row is checked:
- The **Delete N** button in the toolbar shows the count and becomes active.
- Click **Delete N** → a confirmation dialog appears listing the constraint types and warning that Fusion's `Ctrl+Z` can undo the whole operation.
- Confirm to delete all checked rows. The palette refreshes.

Click **Clear** to uncheck all rows without deleting.

> Implicit endpoint join rows (marked "implicit") have no checkbox — they cannot be deleted.

### Find: canvas → palette lookup

The **Find** button bridges the gap between selecting something on the canvas and finding it in the palette:
1. Select any sketch entity on the canvas (click a line, arc, point, or dimension).
2. Click **Find** in the palette toolbar.
3. Every row that references the selected entity is highlighted with a blue left border, and the palette auto-scrolls to the first match. The entity readout strip shows which entity was found.

This works for both geometry (lines, arcs, circles, points) and constraint objects.

### Collapsible sections

The list is divided into sections — **Geometric Constraints**, **Dimensions**, **Patterns and figures**, **Endpoint Joins**. Click any section header to collapse or expand it. The count in the header always stays visible. Collapsed state is preserved when the list refreshes.

---

## What gets listed

### Geometric constraints (21 types)

Horizontal, Vertical, Horizontal align, Vertical align, Parallel, Perpendicular, Collinear, Coincident, Coincident-to-surface, Tangent, Equal, Concentric, Midpoint, Symmetric, Offset, and surface-relation constraints (Line on surface, Line parallel to surface, Line perpendicular to surface).

Each row shows:
- A native Fusion constraint icon (copied from Fusion's own resource folders at startup).
- The constraint type name.
- A human-readable label with entity names ("Line 3", "Arc 2", "Point 5").
- Entity chips for each referenced object.

### Dimensions (12 types)

Linear, Angular, Radial, Diameter, Offset, Tangent distance, Distance-between-lines, Distance-to-surface, Concentric-circle, Ellipse major/minor radius, and Offset curves.

Each dimension row shows:
- The dimension expression in accent color (`40 mm`, `width/2`).
- Entity chips with friendly names ("Line 1 → Line 3", "Circle 2").
- A pencil icon for inline editing (see above).

### Patterns and figures

Circular pattern, Rectangular pattern, and Polygon constraint rows appear in a dedicated section. Pattern rows show editable count and spacing/angle fields.

### Endpoint joins (implicit)

Fusion stores endpoint-to-endpoint connections as shared `SketchPoint` instances, not as explicit constraints. ConstraintLens reconstructs these from the sketch geometry and shows them as "implicit" pseudo-rows so you can see which lines share an endpoint. These rows have:
- An "implicit" badge.
- A lock icon (⊘) instead of a delete button — implicit joins cannot be deleted here.
- No checkbox (excluded from bulk delete).

### Invisible entities

If a constraint references geometry that Fusion has made invisible (e.g. internal control geometry created by Offset or Spline operations), the corresponding entity chip is shown dimmed with a dashed border and a small "hidden" badge. The constraint row still appears and can still be selected or deleted.

---

## Auto-refresh

The palette automatically re-scans and updates after every Fusion sketch command (`commandTerminated` event). You do not need to click **Refresh** after adding or deleting a constraint. Use **Refresh** only if the palette seems stale (e.g. after minimizing and restoring the palette window, since there is no palette-restored event in the Fusion API).

---

## Known limitations

- **No granular undo for Delete** — Fusion's `Ctrl+Z` reverts the whole sketch-edit chunk, not the individual constraint deletion.
- **Implicit endpoint joins cannot be deleted** from the panel — they are shared `SketchPoint` instances, not real constraints.
- **`AssemblyConstraint`** (Constrain Components, January 2026 preview API) is not supported.
- **Palette data may be stale after minimizing/restoring** the palette window — click **Refresh** or perform any sketch edit to trigger a rescan.
- **No live highlight on canvas hover** — hovering a row does not draw a highlight overlay on the canvas (only a click triggers selection).

---

## Folder structure

```
FusionConstraints/
├── SPEC.md                         Architectural spec.
├── README.md                       This file.
├── ConstraintLens/                 The Fusion add-in (copy this folder into AddIns/).
│   ├── ConstraintLens.manifest
│   ├── ConstraintLens.py
│   ├── lib/                        Python backend modules.
│   └── palette/                    HTML/JS/CSS palette UI (vanilla JS, no build step).
└── tests/
    ├── fixture_sketch/             Deterministic test sketch (4 constraints, 2 dims, 4 implicit joins).
    ├── fixture_midpoint/           Triggers the M-1 midpoint-to-midpoint edge case.
    ├── fixture_dimensions/         Creates all dimension types for testing.
    └── spike_probe/                API-feasibility probe; re-run after each Fusion update.
```

To run a test script: **Tools → Scripts and Add-Ins → Scripts → +** → select the subfolder → **Run**.

---

## License

MIT — see [`LICENSE`](./LICENSE).
