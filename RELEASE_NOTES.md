# ConstraintLens — Release Notes

---

## v1.0.0 (current)

**Full v1 feature set — all 21 backlog items complete.**

This release completes the v1 Polish Backlog. Every feature that was deferred from the MVP is now shipped.

### New in v1.0

**Interaction improvements**
- **Double-click any dimension row** to open Fusion's native dimension editor directly from the palette. All 12 dimension types are supported via `SketchEditDimensionCmdDef`.
- **Double-click an Offset Curves dimension** to open the Offset Curves edit dialog.
- **Double-click a Circular or Rectangular Pattern** row to open the pattern edit dialog.
- **Click the constraint icon glyph** (left side of each row) to select the constraint object itself — the separate ⌖ "Select constraint" button has been removed.
- **Click any entity chip** to simultaneously filter the list to that entity AND select it on the canvas.
- **Inline dimension editing** via pencil icon (hover to reveal) — type a new expression, press Enter to commit or Escape to cancel.
- **Inline pattern editing** — Circular patterns expose Count and Total Angle fields; Rectangular patterns expose Count and Spacing for each direction.

**Canvas ↔ palette navigation**
- **Find button** — select any sketch entity on the canvas, click Find, and every palette row referencing that entity is highlighted (blue left border) and scrolled into view. Works for both geometry and dimension rows.
- **Entity readout strip** — shows the canvas label of the selected entity ("Selected: Line 3") below the filter bar when Find is active.

**List and filtering**
- **Filter bar** matches entity chip labels in addition to row labels and types — type "Line 3" to find every constraint that involves Line 3.
- **Collapsible sections** — click any section header to collapse or expand it. State is preserved across data refreshes.
- **"Patterns and figures" section** — Circular Pattern, Rectangular Pattern, and Polygon constraints are grouped here, separate from geometric constraints.

**Visual polish**
- **Native Fusion icons** for all constraint and dimension types, copied from Fusion's own resource folders at startup. Dark-theme variants (`*-dark.png`) are used so glyphs appear white on the dark palette, matching the Fusion UI.
- **24×24 px icons** — consistent size across all rows.
- **Sketch name on its own top row** — sketch name and constrained state displayed separately from the toolbar buttons.
- **Invisible entity chips** — geometry that Fusion has hidden (e.g. Offset spline control curves) is shown dimmed with a dashed border and a "hidden" badge. The constraint row still appears and can be deleted.

**Bulk operations**
- **Bulk delete** — check multiple rows, click "Delete N", confirm, and all selected constraints are deleted in one operation. Includes a Ctrl+Z note in the confirm dialog.

**Discoverability**
- Button relocated to **Sketch → Constraints** panel (visible during sketch editing), matching where users naturally look for constraint tools.
- "Show Underconstrained" button renamed to **"Show underconstraint elements"** for clarity.

---

## v0.1.7

- Bulk delete with confirmation dialog. Checkboxes on all deletable rows. "Delete N" and "Clear" toolbar buttons. Ctrl+Z note in the dialog. Single × button per row removed.
- Invisible entity chips: hidden geometry chips rendered dimmed + dashed border + "hidden" badge.

## v0.1.6

- Button relocated to `SketchConstraintsPanel` (Sketch tab → Constraints panel).
- "Show underconstrained" toolbar button.
- Filter bar — client-side filtering by label and type; section headers show `(N of M)`.
- OffsetConstraint label normalized: `Offset (1→1 curves, 30 mm)`.
- Dimension entity chip labels: friendly names ("Line 2 → Line 3") instead of API type strings.

## v0.1.5

- `SketchOffsetCurvesDimension` matching hardened with four-strategy fallback (parameter token → name → positional → single-constraint).
- OffsetConstraint `parentCurves` + `childCurves` used as dimension chips.

## v0.1.4

- OffsetConstraint row lists curve chips.

## v0.1.3

- Implicit endpoint joins rendered as pseudo-rows with "implicit" badge and ⊘ lock icon.
- Token-based entity selection (Tangent spline+line row correctly highlights both curves).
- M-1 defensive guard for `MidPointConstraint.point` accessor.

## v0.1.2

- Auto-load fixed: palette populates without requiring a manual Refresh click.
- OffsetConstraint accessor error fixed.

## v0.1.0 — MVP

- Docked palette listing all geometric constraint subtypes (21 types) and sketch dimensions (12 types).
- Click row → select referenced entities in the viewport.
- Delete button per row (`constraint.deleteMe()`), disabled when `isDeletable == False`.
- Sketch status banner (name, component, fully/under-constrained state, health warnings).
- Auto-refresh on `commandTerminated` and `documentActivated` events; manual Refresh button.
- Graceful "No active sketch" empty state.
