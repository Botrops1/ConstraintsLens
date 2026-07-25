# ConstraintLens — Release Notes

---

## v1.6.0 (current)

**Adjustable palette height while docked, live row counts while a tool is active, and a denser row layout.**

### Auto-hide when leaving a sketch (#9)

New **📌** toggle in the toolbar. Pinned is the default and keeps today's
behaviour; switch it to **📍** and the palette hides when you leave a sketch and
comes back on the next one you edit.

Closing the palette yourself with the ✕ is respected — auto-hide only reopens a
palette that auto-hide itself hid, so a deliberate close is not undone on the
next sketch.

Two parts of the request could not be done as asked. Fusion's `Palette` exposes
only `isVisible`, `dockingState` and size — there is **no minimize or collapse
state** — so this hides and shows rather than collapsing to a title bar. And the
dock position is deliberately left alone: forcing it was tried in v1.2.0 and
reverted in v1.2.1 as redundant and confusing, because Fusion already remembers
the user's choice across sessions.

### Denser rows — roughly 2.5× more visible at the same height

A constraint row cost about 72 px because the same information appeared three
times: the label read `Tangent — Line 3 ⌒ Arc 1`, the line under it read
`TANGENTCONSTRAINT`, and the chips under that read `[Line 3] [Arc 1]`.

Rows now show the type followed by the entity chips on one wrapping line, at
about 29 px. In a 541 px dock column that is roughly 13 visible rows instead of
5. Nothing is lost: hovering the type shows the full description and the API
type, and the filter still matches label, type, and chip text because
`matchesFilter()` reads them from the data rather than the DOM.

Also in this pass: row padding 8 px → 5 px; the toolbar's "Show underconstrained
elements" shortened to **Show u/c** so the toolbar stops wrapping to two lines at
420 px wide; and the "Selected:" strip and properties footer caps lowered from
68/76 px to 46/52 px, since together they were taking 144 px of the column
whenever anything was selected.

### Live refresh while a constraint tool stays active

Applying the same constraint to one pair of entities after another used to leave
the row list and the section counts frozen until you switched tools or pressed
Esc. They now update within half a second of each constraint landing.

Fusion fires no event at all while a resident tool edits the sketch — a measured
run applied three tangent constraints over 22 seconds and produced no
`commandTerminated` and no `activeSelectionChanged`, just one terminating event
at the end with the tally already advanced. `activeSelectionChanged` cannot help
either, because during a command entity picks go to that command's own selection
input rather than `ui.activeSelections`.

So there is now a 500 ms poll, on a worker thread that only calls
`fireCustomEvent`; Fusion runs the handler on the main thread, where the API is
safe to touch. Each tick reads `geometricConstraints.count` and
`sketchDimensions.count` — two property reads, no enumeration — and only runs a
full `build_payload` scan when that tally has actually moved. Ticks are
single-in-flight, so a busy main thread makes the poll skip rather than queue
events up for a burst later, and the whole thing short-circuits when the palette
is hidden.

### Adjustable palette height while docked

A docked ConstraintLens used to be stuck at the full height of the dock
column. It now has a **⇕ 50% / 75% / Full** cycle button on the name bar and
a drag grip along the bottom edge for any height in between. The preset is
remembered in `localStorage` and re-applied the next time the palette docks.

### Why it took until now

Probe scripts (`tests/probe_dock_height/`, `tests/probe_dock_height2/`) run
against Fusion 2704.1.36 established one rule that explains every earlier
failed attempt:

```
docked height = min(maxHeight, columnHeight)
```

`setMaximumSize` is the only size constraint the dock layout preserves, and
it is honoured **only while the palette is floating** — called on a docked
palette it returns `False` and changes nothing. `setSize` and the `height`
property resize a floating palette but the dock layout discards the value on
re-dock. So applying a height requires floating the palette, capping it, and
re-docking, which is what `_apply_palette_height` does (after first trying two
cheaper approaches and verifying each by reading `palette.height` back).

This also corrects the v1.3.2 note below. `setMaximumSize(420, 700)` did not
"arm a Qt resize handle" — it set a drag ceiling, which is why the palette
appeared resizable up to exactly that height and no further. `2048` looked
like a no-op because `min(2048, columnHeight)` is just the column, and
removing the call entirely in v1.4 lost the affordance altogether.
`dockingOption` turned out to be irrelevant: with both the default
`ToVerticalAndHorizontal` and the native-palette `ToVerticalOnly`, a docked
palette had no drag handle at all.

---

## v1.5.0

**GUI improvements: auto-filter, section select-all, scrollable strips, ✕ clear button, profile area, auto-zoom toggle.**

### Canvas click → auto-filter (#22)
Selecting a single entity on the canvas now immediately sets the filter bar to that entity's label, narrowing the constraint list to every row that involves it. Multi-entity selections leave the filter unchanged. Click ✕ or clear the field to restore the full list.

### Always-visible ✕ clear button (#23)
A small **✕** button sits permanently to the left of the filter input. It clears the filter instantly without having to select the text field first. The redundant native browser cancel button (hidden by `-webkit-appearance`) is suppressed.

### Scrollable "Selected:" strip, capped at 3 rows (#25)
The entity chip strip above the filter bar now scrolls after 3 chip rows (`max-height: 68 px`) instead of expanding the palette arbitrarily. The scroll track uses the same thin Fusion-style scrollbar as the main list.

### Scrollable "Properties of selected" footer, capped at 3 rows (#24)
The selection-info footer at the bottom scrolls after 3 entity rows (`max-height: 76 px`) and also uses the thin scrollbar style.

### Section select-all checkboxes (#26)
Each of the **Geometric Constraints**, **Dimensions**, and **Patterns and figures** section headers now has a checkbox on the left. Clicking it selects all deletable rows in that section; clicking again deselects them. The checkbox shows an indeterminate state (−) when only some rows in the section are checked.

### Profile area in footer (#27)
Selecting a sketch **Profile** (closed loop) in the footer section now shows its computed **Area** (in the active document units). Previously the footer showed a bare "Profile" label with no properties.

### Auto-zoom toggle labeled (#29)
The ⌕ auto-zoom toggle button in the "Selected:" header now reads **⌕ Zoom** for clarity. Active state uses a filled accent background so the on/off state is unambiguous at a glance.

---

## v1.3.2

**Bug fix: docked palette could not be resized beyond 700 px tall.**

> **Superseded by v1.6.0 — the explanation below is wrong.** `setMaximumSize`
> was setting a drag *ceiling*, not arming a Qt resize handle, and the
> `setMaximumSize(0, 0)` follow-up described here was later found to hard-lock
> the palette to 0×0 rather than clear the cap. The shipped code was reverted
> to a no-max state before v1.5.0; see the v1.6.0 entry for what actually
> governs docked height. Kept for history.

The v1.2.2 resize-affordance fix called `setMaximumSize(420, 700)`, which
re-armed Fusion's Qt dock-widget resize handle as intended but also
imposed a hard 420×700 size cap. The palette opens at 420×600, so users
could only grow it by 100 px before the drag became a no-op. The fix
calls `setMaximumSize(420, 700)` to arm the handle, then immediately
calls `setMaximumSize(0, 0)` to clear the cap — `(0, 0)` is documented
as "no restriction" and removes the limit once the handle is already armed.

---

## v1.3.1

**Auto-zoom to selection — opt-in ⌕ toggle.**

- Added an **auto-zoom toggle (⌕)** in the "Selected:" section header. When on, every canvas selection repositions the camera to frame the selected entity (bounding-box fit, 1.5× padding, 0.5 cm min / 50 cm max). Works for single and multi-entity selections; skips silently on any API error.
- Toggle state is persisted in `localStorage` and restored on palette reopen.
- Default off — the camera is never moved unless the user explicitly enables this feature.

---

## v1.3.0

**Automatic canvas → palette lookup; "Show underconstrained" chips.**

- **Find button removed.** Canvas-to-palette lookup is now automatic: selecting anything on the canvas instantly highlights matching rows (blue left border), auto-scrolls to the first match, and shows entity chips in the new "Selected:" header strip above the filter bar. Powered by `activeSelectionChanged` (push-based, no polling, no button click).
- **"Selected:" section** appears above the filter bar when entities are selected; hides itself when nothing is selected. Entity chips in this strip are clickable — clicking sets the filter and selects the entity on the canvas.
- **"Show underconstraint elements"** now surfaces results as clickable entity chips labelled "Underconstrained:" in the same strip, instead of a plain text toast. A 750 ms suppression window prevents the text command's own selection side-effect from overwriting the labelled push.
- **Layout** restructured: entity readout above the filter bar; a "Properties of selected:" section header added above the existing selection-info footer.

---

## v1.2.2

**Restore docked-palette resize affordance.**

- `setMaximumSize(420, 700)` is called after palette creation to re-arm Fusion's Qt dock-widget resize handle. `isResizable=True` alone does not activate the resize affordance when the palette is docked; the explicit size call is required.

---

## v1.0.0

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
