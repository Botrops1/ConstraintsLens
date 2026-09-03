# ConstraintLens — Release Notes

---

## v1.6.5 (current)

**Faster on every click, and the filter box no longer holds on after you let go.**

### The auto-filter lets go when the selection does

Clicking one entity on the canvas fills the filter box with its name, which is
a convenience with no way to undo itself. Deselect, click empty space, or
select two things instead, and the list stayed narrowed to an entity that was
no longer selected, with nothing on screen saying why — the only way out was
the ✕ beside the box. It also fought the feature next to it: rows matching the
new selection were highlighted and then filtered straight out of the view.

The filter box now tells a filter it chose apart from one you typed. The first
kind is retired as soon as it stops describing the selection — nothing
selected, nothing matched, several matched, or a move to another sketch. The
second kind is never cleared for you, and neither is disturbed by a rescan of
the sketch you are already in.

### Less work per click

Nothing here changes what you see; it changes how much happens to show it.

- **The sketch was described twice on every scan.** Geometric constraints and
  patterns were gathered in two separate passes, each of which built every row
  in the sketch and then discarded the ones it did not want. One pass now.
- **The entity-name index was rebuilt on every canvas click.** Naming entities
  reads an identifier for each one in the sketch, and that was happening again
  for each selection change on top of each scan. It is cached and rebuilt only
  when the sketch's geometry actually changes.
- **Selection work ran behind a hidden palette.** Outside sketch-edit mode the
  palette is hidden by design, but every click in the browser tree still
  triggered a full read of the selection whose result was then thrown away.

### Corrections

- Dimension rows put their full internal precision back into the hover tooltip
  and the filter index — the row showed `5.13 mm` while hovering it showed
  `5.1290366508 mm`, and typing the number you could see matched nothing.
- Areas and volumes were converted for millimetre, metre and inch documents
  only; centimetre and foot documents both fell back to reporting cm² and cm³.
- The in-palette help sheet still said Fusion remembers where you put the
  palette. It does not — that was established in v1.6.4 and corrected in the
  README at the time, but not in the sheet.
- Stopping and restarting the add-in without restarting Fusion carried the old
  run's state over, so a palette closed with ✕ reappeared on the next sketch.

### For contributors

`tests/headless/` is new: the Python runs against hand-written `adsk` stubs and
the palette runs in a real browser over `file://`, both without Fusion
installed, and both in CI on every push. See `tests/headless/README.md`.

---

## v1.6.4

**The palette opens docked to the right (#11), and the install path in the
README was wrong for everyone.**

A new custom palette is created at (0, 0) floating. When the Fusion window is
not on the primary monitor, that corner belongs to a different screen, so the
palette opened off the Fusion window entirely and nothing appeared to happen.
It now docks to the right edge on creation — the same place Fusion's own Sketch
Palette lives — which sidesteps screen coordinates altogether.

This happens on every launch, not just the first: Fusion does not restore a
custom palette's docking state between sessions, so there is no remembered
choice to override. Within a session only creation docks — move the palette by
hand and it stays where you put it, including across leaving and re-entering a
sketch.

`setPosition` was deliberately not used. The coordinate frame those numbers are
counted from is still unverified, and guessing wrong would push the palette
further off-screen rather than back on.

Also: **Installation step 4 said Tools → Add-Ins.** Fusion renamed that tab to
**Utilities** on every platform, so the instruction was stale for everyone at
the exact step where a new user concludes the add-in is broken. `Shift+S` is
documented as the version-proof route.

---

## v1.6.3

**Discoverability: the drag strips are visible now, and a `?` explains the rest.**

Both resize grips drew their handle bar in the hairline border colour — about
`#404040` on a `#333` strip — so neither could be found without hovering over
it. They have their own colour tokens now, per theme, and the bars are wider.

The `?` button on the name bar opens a sheet listing every unlabelled click
target in the palette: row body versus row icon, entity chip, pencil, grip
strip. Dismiss it with `?` again, Esc, ✕, or a click on the backdrop.

---

## v1.6.2

**The "Properties of selected" pane is draggable (#12).**

The v1.6.0 density pass capped it at about two rows, which is too short to read
the properties of several selected entities at once. Both it and the
"Selected:" chip strip get a drag strip; double-click either to reset it. The
default cap is taller than it was, and the size is remembered between sessions.

Because the divider resizes a pane inside the palette rather than the palette
itself, it applies live as you drag — none of the docked-height machinery is
involved. Neither pane can take more than 60% of the view, so the constraint
list cannot be crowded out.

---

## v1.6.1

**Readable numbers.**

Values were shown at full internal precision — `5.1290366508 mm` on a dimension
row, `RADIUS 2.7873295 mm` in the footer. They now follow the precision set in
your document preferences, matching what Fusion shows everywhere else.

The cause was `UnitsManager.formatInternalValue`, which formats at full
precision and is not part of the documented API. Everything now uses
`formatValue`, whose default `precision = -1` means "use the user's preference".

Dimension rows get a further refinement. A dimension created by dragging stores
its full-precision value *as its expression*, so there was nothing to round —
the long number was the honest answer. Those now show the formatted value, while
genuine formulas like `d5*2` are still shown verbatim, because knowing a
dimension is driven matters more than its current number. Editing is unaffected:
the inline editor is always seeded with the real underlying expression.

Also: selecting a dimension showed `SketchDiameterDimension` in the footer, the
raw API type name. It now reads `Diameter d56` — friendly kind plus the
parameter identifier.

---

## v1.6.0

**Adjustable palette height while docked, live row counts while a tool is active, and a denser row layout.**

### Measurements for a two-entity selection (#8)

Select exactly two entities and the footer gains a first row labelled
`Line 3 ↔ Arc 1` showing the derived measurement:

- **Any two entities** — `Distance`, the minimum distance between them.
- **Two lines** — `Angle` as well, since for parallel lines the angle is 0° and
  the distance is the number that matters.
- **Two circles** — the distance is the gap between circumferences, which for
  concentric circles is exactly the radial offset.
- **A point and a line** — distance to the line, correct for a finite segment.

These use Fusion's own `MeasureManager` rather than separately computed geometry,
so the figures agree with the built-in **Measure** tool. The derived row is
placed first because it is what you selected two things to see.

### Dimension identifier and point Z in the footer (#10)

Selecting a dimension now shows its parameter **`Name`** (e.g. `d526`) next to the
value — that is the identifier you reference from other expressions, and the only
way to tell apart two dimensions that read the same. Selecting a sketch point now
shows **`Z`** alongside X and Y; the coordinates are sketch-space, so Z carries
real information in a 3D sketch.

### Double-click to edit a sketch

During development of this release, double-clicking a sketch in the browser or
timeline could stop entering sketch-edit mode. The cause was the new
live-row-count poll: it fired a custom event every 500 ms, processed on Fusion's
main thread, and Windows' double-click threshold is also around 500 ms — so a
tick landing between the two clicks broke double-click recognition.

The poll only exists to catch edits made by a resident sketch tool, so outside
sketch-edit mode it has nothing to look for. It is now completely silent there.

Timing instrumentation across every per-click code path afterwards found nothing
that blocks: the slowest single event in the add-in is a 47 ms sketch activation,
and pushing data to the palette costs well under a millisecond. The problem is
not reproducible on the released build. If you do hit it, please open an issue —
the poll thread is the first thing to suspect.

Also fixed while measuring: entering a sketch scanned it twice, because the
auto-show path and the refresh path each published independently. That was about
30 ms of the 47 ms.

### Palette follows sketch-edit mode (#9)

The palette now hides whenever you leave a sketch, and reappears on the next
sketch you edit — so it only needs opening once per Fusion session. The **📌**
pin toggle from the first cut of this feature has been removed; there was no
reason to keep the palette visible outside a sketch.

Closing it with the **✕** is the opt-out: it then stays away until you click
**Constraint Lens** in the Sketch toolbar again.

Note on collapsing: Fusion's native collapse arrows on a docked palette are
**not exposed to the API** — the entire `Palette` surface is `isVisible`,
`dockingState`, `dockingOption`, size and position. ConstraintLens therefore
never changes your collapsed state, dock position or size; whatever Fusion
remembers is carried straight through the hide and show.

### Dimension rows on one line

A dimension row now reads `[◇] Linear (Line 1) (Line 3) = 40 mm ✎`, with the
value inline and the pencil always visible rather than appearing on hover.

The earlier density pass missed dimensions entirely. It cut labels at `" — "`,
but `dispatch.py` builds dimension labels with different separators —
`"Linear: Line 1 → Line 3 = 30 mm"` — so those rows were still printing the
entity names in the label *and* as chips, and the value in the label *and* in
the expression line below. Label trimming now cuts at whichever of `" — "`,
`": "` or `" = "` comes first.

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
