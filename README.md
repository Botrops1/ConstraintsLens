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
│  Sketch3 (Body1) — under-constrained  ☀  │  ← name bar (theme toggle)
├──────────────────────────────────────────┤
│  [Clear] [Delete 0] [Show u/c] [Refresh] │  ← toolbar
├──────────────────────────────────────────┤
│  SELECTED:                            ⌕  │  ← canvas selection (auto, hidden when empty)
│   Line 3                                 │  ← entity chips
├──────────────────────────────────────────┤
│  🔍 Filter by label or type…             │  ← filter bar
├──────────────────────────────────────────┤
│  GEOMETRIC CONSTRAINTS (6)            ▾  │  ← collapsible section
│  [⊥] Perpendicular — Line 1 ⊥ Line 2  □ │
│  [∥] Parallel — Line 3 ∥ Line 4       □ │
│  …                                       │
│  DIMENSIONS (3)                       ▾  │
│  [◇] Linear: 40 mm   Line 1 → Line 3  □ │
│  …                                       │
│  ENDPOINT JOINS (4)                   ▾  │
│  [⊘] Endpoint join — Point 1 connects…  │
├──────────────────────────────────────────┤
│  PROPERTIES OF SELECTED:                 │  ← properties footer (hidden when empty)
│  Line 3   Length 42.5 mm                 │
└──────────────────────────────────────────┘
```

### Sketch name bar (top row)

Shows the sketch name, parent component, and constrained state:
- **Green** — fully constrained.
- **Yellow/orange** — under-constrained (some geometry is still free).
- **Red** — over-constrained or has errors.
- Any `healthState` warning message is shown inline.

One toggle button sits on the right end of the name bar:

| Button | What it does |
|---|---|
| **☀ / 🌙** (theme toggle) | Switches between dark (default) and light theme. Preference is saved in `localStorage` and restored when the palette is reopened. |

> **Docking and resizing** are handled by Fusion itself. Drag the palette title bar to any edge of the Fusion window to snap-dock it (right / left / bottom / top), or drop it anywhere to float. Drag any palette edge to resize — works in both docked and floating modes. Fusion remembers the position and size across sessions.

### Toolbar (buttons row)

| Button | What it does |
|---|---|
| **Clear** | Deselects all checked rows (visible only when rows are checked). |
| **Delete N** | Deletes all checked rows at once after a confirmation prompt (visible only when rows are checked). |
| **Show underconstraint elements** | Calls Fusion's built-in Show Underconstrained command. Under-constrained entities are surfaced as clickable chips in the "Selected:" strip. Requires an active sketch edit context. |
| **Refresh** | Manually re-scans the active sketch. Usually not needed — the palette refreshes automatically after every sketch edit. |

### Selected section (canvas → palette, automatic)

Appears automatically above the filter bar whenever you select anything on the canvas. No button click required — the palette listens to Fusion's `activeSelectionChanged` event.

- Shows the selected entity or entities as clickable chips (e.g. `Line 3`, `Circle 1`).
- Every row in the list that references any selected entity is highlighted with a blue left border and scrolled into view.
- Clicking a chip sets the filter bar to that entity's label and selects it on the canvas.
- The section hides itself when nothing is selected.

The **⌕** button at the right end of the "Selected:" header controls **auto-zoom**:
- **Off (default):** camera stays where it is.
- **On:** each selection repositions the camera so the selected geometry fills the viewport (bounding-box fit with 1.5× padding). Useful for locating tiny construction lines.
- Preference is persisted in `localStorage` and restored on palette reopen.

When "Show underconstraint elements" is triggered, the section header changes to "Underconstrained:" and shows chips for all under-constrained entities instead of the generic canvas selection.

### Filter bar

Type any text to narrow the list. Matches against constraint labels, constraint type names, and entity chip labels (e.g. type `"Line 3"` to find every constraint that involves Line 3). The section headers update to show `(N of M)` when a filter is active. Clear the field to restore the full list.

### Properties of selected footer

A footer at the bottom of the palette shows the name and key measured properties of the currently selected entity — useful when the palette is docked over Fusion's own bottom-right status corner. Updates immediately on every selection change; hides itself when nothing is selected.

| Entity type | Properties shown |
|---|---|
| Sketch line / B-Rep edge | `Length` |
| Sketch circle | `Radius`, `Diameter` |
| Sketch arc | `Radius`, `Sweep` angle |
| Sketch ellipse | `Major`, `Minor` axis radii |
| Sketch point | `X`, `Y` coordinates (sketch plane) |
| Sketch dimension | current `Value` (expression) |
| B-Rep face | `Area` |
| B-Rep body | `Volume`, `Area` |

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
