# FusionConstraints — ConstraintLens Add-in

## Current Status

**Working on:** v1.6.1 — number formatting fixes, awaiting PC test. v1.6.0 is released and issues #8/#9/#10 are closed.
**Version:** 1.6.1 (manifest + commit must always match).
**Next step:** Monitor for regressions. Watch the double-click-to-edit-sketch report specifically — it was traced to the 500 ms poll tick colliding with Windows' double-click threshold, gated to sketch-edit mode only, and is no longer reproducible; timing instrumentation found no other per-click stall (slowest event in the add-in is a 47 ms sketch activation, palette pushes are sub-millisecond). **If it recurs, suspect `_start_sketch_poll` first.**
**Convention:** Every commit that bumps the version string must also update `ConstraintLens/ConstraintLens.manifest` `"version"` field so Fusion shows the correct version.
**Blocked by:** Nothing.

### Recent fixes (v1.0.1–v1.6.1)
- v1.6.1: **Number formatting — `formatValue`, never `formatInternalValue`.** Readouts showed full internal precision (`RADIUS 2.7873295 mm`, `= 5.1290366508 mm`). `UnitsManager.formatInternalValue` **is not in the API stubs** and formats at full precision; `formatValue(value, units, precision=-1, …)` takes the same internal-unit input (cm / radians) and `-1` means "use the user's preference". `_fmt_length` / `_fmt_angle` switched over. **Don't reintroduce `formatInternalValue`.**
  - Dimension rows: a dragged dimension stores its full-precision value *as the expression*, so rounding the display was not enough — `scanner.dimension_display()` formats plain numbers via `param.value` + `param.unit` (`unit` keeps angular dims in degrees) and passes real formulas like `d5*2` through verbatim. Rows carry both `parameterExpression` (raw, seeds the editor via `data-expr`) and `parameterDisplay` (shown). The JS editor reads `data-expr`, **not** `textContent`, or it would try to commit the formatted string.
  - `_selection_label` fell through to the raw type name for dimensions (`SketchDiameterDimension`); now `dispatch.dimension_kind()` + `param.name` → `Diameter d56`. Required adding `dispatch` to lifecycle's imports.
- v1.6.0: **Per-click cost measured, and the double scan on sketch entry removed.** A timing pass over every per-click path (log format in git history at `7ab6890`, since reverted) showed **nothing blocks**: `sendInfoToHTML` is 0.2–0.7 ms, `build_payload` 12–14 ms, worst single event 47 ms on `SketchActivate`. The "palette pushes block the main thread" theory was wrong — don't revisit it. It did reveal that entering a sketch scanned twice (`_sync_palette_visibility` republished, then `_on_change` republished again), ~30 ms of that 47 ms; `_sync_palette_visibility(app, republish=False)` from `_on_change` fixes it.
- v1.6.0: **Regression fix — the sketch poll broke double-click-to-edit-sketch.** Double-clicking a sketch in the browser or timeline stopped entering edit mode. The 500 ms `fireCustomEvent` tick is processed on the main thread and Windows' double-click threshold is also ~500 ms, so a tick landing between the clicks broke recognition. Fixed by `_poll_enabled`: the poll only fires while a sketch is being edited, which is the only time it has anything to find. `commandTerminated` flips it (`SketchActivate` / `SketchStop`, both seen in the probe log) and the tick re-checks so it can switch itself off. **If any double-click misbehaves again, suspect this thread first.**
- v1.6.0: **Palette visibility follows sketch-edit mode; pin toggle removed.** `_sync_palette_visibility()` hides on sketch exit unconditionally and restores on the next sketch when `_ever_opened` is set (i.e. the user opened it at least once this session). `_on_palette_closed` clears `_ever_opened` — closing with ✕ is the opt-out — guarded by `_suppress_closed_event` so our own programmatic hide can't clear it if a build raises `closed` on that too.
  - **Fusion's native palette collapse arrows are NOT in the API.** Verified against the stubs: the complete `Palette` surface is `isVisible`, `dockingState`, `dockingOption`, `width`/`height`, `left`/`top`, `setSize`, `setMinimumSize`, `setMaximumSize`, `setPosition`, `snapTo`. No collapse/expand/minimize member exists anywhere in `adsk.core`. Don't re-search for it. Collapsed state is preserved only because Fusion remembers it across hide/show.
- v1.6.0: **Dimension rows on one line (item #4).** The v1.6.0 density pass cut labels at `" — "` only, but `dispatch.py` builds dimension labels as `"Linear: Line 1 → Line 3 = 30 mm"` — so dimension rows still duplicated entities (label + chips) and value (label + expression line). `labelHeadOf()` now cuts at the first of `" — "`, `": "`, `" = "`. `exprHTML` moved inside `.row-head` with a `=` prefix and an `inline` class (`margin-top: 0`); `.btn-edit` is `opacity: 0.55` instead of hover-revealed. The `.dim-expr-wrap` / `.dim-expr` structure is load-bearing — the edit handler finds the value via `closest(".dim-expr-wrap")`.
- v1.6.0: **Two-entity measurements (#8) + dimension `Name` and point `Z` (#10).**
  - `_pair_measurements()` uses `app.measureManager.measureMinimumDistance()` / `measureAngle()` — whose docs state they accept "any sketch entity" — instead of hand-rolled geometry, so values match Fusion's own Measure tool. One mechanism covers all four cases in #8: 2 points, point+line, and 2 circles all resolve to minimum distance; 2 lines additionally get an angle (parallel lines give 0° so distance is the useful figure). Two circles: minimum distance is the circumference gap, which for concentric circles equals `|r1 - r2|` — the "offset" the issue asked for. `MeasureResults.value` is internal units (cm for distance, radians for angle), so the existing `_fmt_length` / `_fmt_angle` apply directly.
  - Returned as an ordinary `{label, props}` selection item and `insert(0, ...)`-ed, so **no JS change was needed** — `onSelectionInfo` already renders generic items. Placed first because the derived value is the point of a two-entity selection.
  - `_build_selection_info` now tracks raw `selected` entities separately from `items`, because a pair needs both entities even when one has no per-entity properties of its own.
  - #10a: dimension branch of `_selection_props` appends `param.name` before `param.expression`. Guarded by a `got_any` flag so the branch no longer returns early having appended nothing. #10b: `SketchPoint` gains `Z` from `entity.geometry` (sketch-space), shown unconditionally — in a 3D sketch a point can sit at Z=0 legitimately, so hiding the field there would read as "no Z information".
  - **Density note:** two selected entities now produce 3 footer rows against a 52 px cap, so it scrolls. Mitigated by putting the derived row first; raise `#footer-section` `max-height` to ~72 px if that proves annoying in use.
- v1.6.0: **Auto-hide on sketch exit (issue #9).** Opt-in `📌`/`📍` toggle in the toolbar, off by default (`localStorage` `cl-autohide`, mirrored to Python via `ACTION_SET_AUTO_HIDE` + `paletteReady`'s `autoHide`). `_apply_auto_hide()` runs from both `_on_change` and the poll tick.
  - `_auto_hidden` tracks *who* hid the palette. Without it, a user who closed the palette with the ✕ would have it forced open on their next sketch. Manual close leaves the flag False, so auto-show skips it; `_show_palette()` clears the flag because the toolbar button is an explicit "open this".
  - Auto-show must run **before** `_republish_if_sketch_changed()` in the tick — the latter bails out on a hidden palette, so ordering it after would make the palette unable to un-hide itself. It also republishes on show, since `messaging.send()` drops everything while invisible (M-8).
  - `_applying_height` guard added: `_apply_palette_height()` calls `adsk.doEvents()`, which can dispatch a queued poll tick mid-sequence, and that tick must not toggle `isVisible` while the height tiers are using `isVisible`/`dockingState`. The body moved to `_apply_palette_height_inner()` so the guard is a try/finally wrapper.
  - **Declined from the issue, deliberately:** there is no minimize/collapse state on `adsk.core.Palette` (only `isVisible`, `dockingState`, size — verified against the stubs), so "collapsed" is not implementable; and dock position is left alone because forcing it was tried in v1.2.0 and reverted in v1.2.1.
  - **Issue #8 decision on record:** two selected circles should report the **minimum gap** (`measureMinimumDistance`), which equals `|r1 - r2|` for concentric circles. Not yet implemented. `app.measureManager.measureMinimumDistance` / `measureAngle` accept any sketch entity and cover all four cases in that issue.
- v1.6.0: **Row density pass — ~72 px/row down to ~29 px, 5 visible rows to ~13.** The same information was rendered three times per row: `row.label` (`"Tangent — Line 3 ⌒ Arc 1"`), `row.kind` uppercased on its own `.row-meta` line (`TANGENTCONSTRAINT`), and the entity chips (`[Line 3] [Arc 1]`). `dispatch.py` builds every label as `"{type} — {entities}"`, so the label tail and the chips are the same thing, and `.kind` was a third copy of the type name.
  - `rowHTML()` now renders `label.split(" — ")[0]` only, with the full label + `row.kind` in the `title` tooltip. `.row-meta` and `.kind` are gone; badges moved into a new `.row-head` flex line shared with the label and chips (`.chips` lost its `margin-top`).
  - Safe because `matchesFilter()` ([app.js](ConstraintLens/palette/app.js)) reads `row.label` / `row.kind` / `row.entities` from the snapshot data, **not** the DOM — hiding them from display does not affect filtering.
  - Also: `.row` padding 8→5 px; `#entity-readout` cap 68→46 px and `#footer-section` cap 76→52 px (together they were 144 px of a 541 px column); toolbar button "Show underconstraint elements" → "Show u/c" so `.toolbar { flex-wrap: wrap }` stops wrapping to two lines at 420 px.
- v1.6.0: **Live row counts while a tool stays active.** `commandTerminated` was the only rescan trigger, and a resident sketch tool never fires it between applications. Measured 2026-07-25: three tangent constraints over 22 s produced **zero** events of any kind, then one `TERM cmd=ConstraintTangent` with the tally already at 9→12. Meanwhile plain canvas clicking fires `TERM cmd=SelectCommand` constantly — the silence is specific to being inside a tool.
  - `activeSelectionChanged` is **not** a usable trigger: during a command, entity picks go to that command's own selection input, not `ui.activeSelections`, so it stays silent exactly when needed. (Tried and reverted.)
  - A `setInterval` in the palette web view was tried and abandoned. Its failure reason was never established — the run logged no messages at all, equally consistent with the JS not having been deployed. Don't re-litigate it; the worker thread doesn't depend on the web view being loaded or focused.
  - **Counts DO move mid-command** — the same run caught `gc` stepping 9→10→11→12 as each constraint landed. Fusion does not hold a resident tool's edits transient; nothing was watching.
  - Implementation: `_start_sketch_poll()` runs a daemon thread that only calls `fireCustomEvent` every 500 ms (`events.register_custom_event` pins the handler per M-7; Fusion runs it on the main thread, and touching the API from the worker would crash). Each tick compares `geometricConstraints.count` + `sketchDimensions.count` against `_last_sketch_counts` and only calls `build_payload` when it moved. Single-in-flight via `_poll_in_flight`, because an unguarded fire queued 8 events into a 30 ms burst after a 3.9 s main-thread stall. Short-circuits on a hidden palette. Torn down in `stop()` *before* `events.unregister_all()`.
- v1.6.0: **Docked height control — the long-standing "palette height is fixed when docked" problem, finally characterised.** Probes `tests/probe_dock_height/` and `tests/probe_dock_height2/` (Fusion 2704.1.36) established the governing rule: **`docked height = min(maxHeight, columnHeight)`**. Three facts follow, and together they explain every failed attempt from v1.2.0 through v1.3.2:
  - `setMaximumSize` is the *only* size constraint the dock layout preserves, and it is honoured **only while the palette is floating**. On a docked palette it returns `False` and changes nothing (round 1 P2, round 2 M5).
  - `setSize` / the `height` property resize a *floating* palette, but the dock layout discards the value on re-dock (round 2 M3: 324 floating → 541 docked). Useful only to **grow** before re-docking, since `setMaximumSize` can never enlarge.
  - `dockingOption` is irrelevant — round 2 stage 0 (default `3`) and stage 1 (`1 ToVerticalOnly`, what every native side palette uses) were **both** undraggable. Hypothesis killed.

  Retro-explanation of the old history: `setMaximumSize(420, 700)` never "armed a Qt resize handle", it set a drag *ceiling* — hence resizable to exactly 700 and no further. `2048` looked like a no-op because `min(2048, column)` is just the column. `9999` crashes. Dropping the call in `48bd8ad` lost the affordance entirely.

  Implementation: `_apply_palette_height()` in `lifecycle.py` tries three tiers, each verified by reading `palette.height` back (return values are worthless — `setSize` is documented to report success even when docking blocked it): (1) in-place `setMaximumSize`, free and works when floating, and registers the drag ceiling even when it does not resize; (2) `isVisible` off/on to force a dock re-layout without undocking; (3) the proven float → `setMaximumSize` → `setSize` → re-dock round trip. UI: `⇕ 50/75/Full` cycle button on the name bar + a drag grip strip at the bottom of the body flex column, applied on pointer-release. `_dock_column_px` caches the tallest docked height ever seen (= the column); the Full preset asks for the 4000 px safe ceiling, which the dock layout clamps to the column and thereby re-measures it.

  **Landmines, unchanged:** `setMaximumSize(0, 0)` hard-locks the palette to 0×0 despite being documented as "no restriction"; values ≥ 9999 crash Fusion and deactivate the add-in. Never emit either.
- v1.3.2: ~~Remove docked-palette height cap.~~ **Explanation superseded by v1.6.0 — see above.** `setMaximumSize(420, 700)` from v1.2.2 was re-arming Fusion's Qt dock-widget resize handle as intended but also imposing a hard 420×700 size cap, so users could only enlarge the docked palette by 100 px vertically (it opens at 420×600). Switched to `setMaximumSize(420, 700)` (arm) then `setMaximumSize(0, 0)` (clear cap) — same arming side effect, no practical cap. `(0, 0)` is documented as "no restriction" and short-circuits before triggering the side effect, so it cannot be used alone to arm; but it correctly clears a cap that is already set. Large finite values (e.g. 9999) cause Fusion to crash/deactivate the add-in and must not be used.
- v1.3.1: Pack 4 — opt-in auto-zoom to selection. ⌕ toggle in the "Selected:" section header (persisted in localStorage). When on, each activeSelectionChanged event unions the bounding boxes of all selected entities and repositions the camera (cam.target + cam.viewExtents, with 1.5× padding and MIN 0.5 cm / MAX 50 cm guards). Skips silently on any API error. Python-side: _zoom_to_active_selection(); JS-side: autozoom-toggle button + setAutoZoom action; state synced to Python on paletteReady. Patch fix (palette/app.js): wrap `#selected-label` text in `<span id="selected-label-text">` so `textContent` writes don't destroy the ⌕ button sibling.
- v1.3.0: Selected / Find / Show-underconstrained refactor. (1) Layout: `#entity-readout` moved above the filter bar with a "Selected:" header; footer wrapped under a "Properties of selected:" header. (2) Find button removed — row highlighting + auto-scroll + chip readout are now driven automatically by `activeSelectionChanged` (same event that already powers the properties footer). (3) "Show underconstrained" no longer dumps plain text into the readout — it surfaces the underconstrained entities as clickable chips labelled "Underconstrained:", with a 750 ms selection-change suppression window so the labelled push isn't overwritten by the text command's selection side-effect.
- v1.2.2: Restore docked-palette resize affordance. `setMaximumSize(420, 700)` is called after palette creation to re-arm Fusion's Qt dock-widget resize handle; `isResizable=True` alone does not activate it when the palette is docked.
- v1.2.1: Issue #3 follow-up cleanup. PC testing confirmed Fusion's own drag-to-snap UX already covers all dock positions and the palette is resizable in every mode (docked or floating). The v1.2.0 dock-cycle button was therefore redundant and confusing — it has been removed, along with the `settings.json` `dock_state` key, the `setDockState` action, and the `setMaximumSize` cap. Fusion now controls dock state natively and remembers it across sessions. The selection-info footer from v1.2.0 stays — it's still the only way to see the bottom-right status when the palette covers that corner. Probe script kept in `tests/probe_palette/` for reference.
- v1.2.0: Issue #3 follow-up — added a multi-position dock cycle and a selection-info footer mirroring Fusion's bottom-right status overlay. (Dock cycle withdrawn in v1.2.1; footer retained.)
- v1.0.1: Issue #4 — "Show underconstrained" fully-constrained exception handled correctly.
- v1.0.2: Entity name chips in Find/underconstrained result strip; chip click sets filter + selects on canvas.
- v1.0.3: Issue #3 — dock/float toggle with `settings.json` persistence; default floating (resizable). Superseded by v1.2.0.
- v1.0.4: Issue #5 — light/dark theme toggle; CSS variables; `localStorage` persistence.
- v1.0.5: Two-slot icon copy (dark + light PNGs) for theme switching.
- v1.0.6: Toolbar layout — toggles moved to name bar; thin Fusion-style scrollbar.
- v1.0.7: Icon dark slot: only accept `-dark.png`; stale files removed so SVG fallback activates cleanly.
- v1.0.8: `_KIND_FALLBACK_CMDS` added for H/V constraint icon lookup (guessed IDs — not yet working).
- v1.0.9: `ConstraintHorizontalVertical` confirmed as correct command for H/V dark icons via probe script.

### What's verified working (all PC tests + session history)
- **v1.6.0, PC verified 2026-07-27:** denser rows + one-line dimension rows; two-entity pair measurements (#8); dimension `Name` + point `Z` (#10); palette follows sketch-edit mode with auto-reopen (#9); docked height cycle + drag grip (tier 3 float/re-dock, returns to the same slot); live row counts while a constraint tool stays active.
- **Still unconfirmed:** whether Fusion carries a manually-collapsed palette state through the auto hide/show. If it does, issue #9's "collapsed on reopen" request is satisfied without any API support — there is none to be had (see the v1.6.0 note below).
- Add-in loads, palette docks, populates without Refresh click.
- Geometric constraints list with click-to-select (row body) and select-constraint (icon glyph click).
- Dimensions list (Angular, Linear, Diameter, etc.) with parameter expression in accent color.
- Inline dimension expression edit via pencil icon; Enter commits, Esc cancels.
- Double-click row → opens native Fusion edit dialog (all dimension types via `SketchEditDimensionCmdDef`; Offset/Pattern via dedicated command IDs).
- Implicit endpoint joins as pseudo-rows with implicit badge AND ⊘ lock icon.
- Tangent spline+line row highlights both objects on click (token-based selection).
- OffsetConstraint row lists curve chips; label: `Offset (1→1 curves, 30 mm)`.
- SketchOffsetCurvesDimension row lists curve chips; double-click → offset edit dialog.
- Sketch status banner (name on own row, fully/under-constrained state with color).
- M-1 defensive guard (MidPoint accessor) — both rows render; no crash.
- Button in `SketchConstraintsPanel` (Sketch tab → Constraints panel).
- "Show u/c" button (shortened from "Show underconstraint elements" in v1.6.0 so the toolbar stops wrapping) — calls `executeTextCommand("Sketch.ShowUnderconstrained")`; result as toast.
- Filter bar — client-side by label/kind/entity chips; section headers show `(N of M)`.
- Find button — canvas selection → palette highlight (blue border + scroll); entity readout strip.
- Chip click → sets filter AND selects entity on canvas.
- Bulk delete — checkboxes, "Delete N" + "Clear" buttons, confirm dialog with Ctrl+Z note.
- Collapsible sections — chevron toggle; state preserved across refreshes.
- Invisible entity chips — dimmed + dashed border + "hidden" badge.
- Native Fusion icons (dark variants) — constraints, patterns, polygon, dimensions; 24×24 px.
- Circular/Rectangular pattern inline edit (count, spacing/angle via `ModelParameter.expression`).
- Polygon in "Patterns and figures" section; center chip + line chips; fallback label if center inaccessible.
- Filter matches entity chip labels (e.g. typing "Line 3" finds all constraints involving Line 3).
- Find works for dimension rows (indexes `row.token` not just chip tokens).
- GUI: sketch name on its own top row; buttons on separate second row with `flex-wrap`.
- PolygonConstraint `lines` iterated via `_iter_curves_into_chips()` (SketchLineVector has no `.count`).

### Known sub-issues to keep on radar
- Offset-of-spline creates internal control geometry that Fusion doesn't render. The row still appears in ConstraintLens with a dimmed "hidden" chip; clicking the row still selects the hidden entity — Fusion's native behaviour. (backlog #8 resolved)
- `OffsetConstraint.distance` returns None in the January 2026 build. Fully mitigated — label uses expression from the matched `SketchOffsetCurvesDimension` parameter. (backlog #9 resolved)
- `PolygonConstraint.centerSketchPoint` returns None in the January 2026 build. Mitigated — fallback chain tries `center`/`centerPoint`; if all fail, label is `"Polygon (N sides)"` with no error shown.
- `SketchLineVector` (returned by `PolygonConstraint.lines`) has no `.count` property. Must use direct iteration.

---

## Project Overview

A Fusion 360 Python add-in that docks a panel listing every constraint in the active sketch — with click-to-select, delete, and over/under-constrained status. Fills the UX gap of having to hunt tiny on-canvas glyphs to audit a sketch.

- **Language:** Python 3.14 (Fusion January 2026 build), vanilla JS palette (no framework).
- **Distribution:** GitHub Releases only (zipped `ConstraintLens/` folder). No App Store.
- **Workspace:** Solid workspace only (MVP). Button lives in `SketchConstraintsPanel` (Sketch tab → Constraints panel).
- **Spec:** `SPEC.md` — complete, all 5 open questions resolved.

---

## Architecture

```
ConstraintLens/
├── ConstraintLens.manifest       Fusion add-in manifest (id, version, runOnStartup)
├── ConstraintLens.py             Entry point — delegates to lib/lifecycle only
└── lib/
    ├── lifecycle.py              Command + palette creation, message routing
    ├── events.py                 GC-safe event handler registry (M-7 guard)
    ├── dispatch.py               21-row constraint type dispatch table + dimension dispatch
    ├── scanner.py                Sketch enumeration → JSON payload
    ├── labels.py                 EntityLabeler: token→"Line 3" map per scan
    ├── selection.py              ui.activeSelections helpers
    ├── actions.py                delete_constraint() with isDeletable check
    ├── tokens.py                 token_of() / resolve() wrappers
    └── messaging.py              palette.sendInfoToHTML / parse_incoming + M-8 guard
palette/
    ├── index.html                Shell; initial "Loading…" state
    ├── app.js                    Vanilla JS render loop + message handler
    └── styles.css                Dark theme matching Fusion
tests/
    ├── fixture_sketch/           Creates ConstraintLens_Fixture (4 constraints, 2 dims)
    ├── spike_probe/              API feasibility probe (all 5 Qs answered — run again after Fusion updates)
    └── fixture_midpoint/         M-1 trigger fixture (midpoint-to-midpoint)
```

### Key conventions
- **Collections:** `SketchCurveVector` (from `.parentCurves`, `.childCurves`, `.curves`) uses `len()` + iteration, not `.count`. `ObjectCollection` uses `.count` + `.item(i)`.
- **Event handlers:** Always appended to `events._handlers` list (M-7). Never instantiate a handler without pinning it.
- **Palette sends:** Always gated on `palette.isVisible` (M-8 guard in `messaging.send()`).
- **Entity selection:** JS sends `entityTokens` list; Python resolves each via `tokens.resolve()` (primary path). `_entities_for_row()` accessor re-scan is fallback only.
- **Test scripts:** Each must be in a same-named subfolder (e.g. `tests/fixture_sketch/fixture_sketch.py`) — Fusion requirement.

---

## Resolved Open Questions (SPEC.md §10)

| # | Question | Answer |
|---|---|---|
| Q1 | Panel id | `SolidScriptsAddinsPanel` confirmed. `SketchConstraintsPanel` exists for v1 relocation. |
| Q2 | ShowUnderconstrained precondition | Requires sketch edit context. Returns plain string `'Under constrained points: N, under constrained curves: N'`. |
| Q3 | Palette `shown` event | No `shown`/`opened` event exists. `commandTerminated` is the only refresh trigger after restore. |
| Q4 | entityToken stability | Stable across save-reload. `findEntityByToken` returns non-empty `BaseVector`. |
| Q5 | VerticalConstraint enumerated? | Yes — `adsk::fusion::VerticalConstraint` appears in `geometricConstraints` iteration. |

---

## Known Remaining Limitations (MVP scope, documented in README)

- No granular undo for delete — Fusion `Ctrl+Z` reverts the whole sketch-edit chunk.
- Implicit coincident joins cannot be deleted from the panel (shared `SketchPoint`, not a real constraint).
- `CircularPatternConstraint` / `RectangularPatternConstraint`: Delete only; no entity accessor.
- `AssemblyConstraint` not supported (preview API, January 2026).
- Palette has no `shown` event — stale data after minimize/restore until next `commandTerminated`.

---

## v1 Polish Backlog (post-MVP, not started)

1. ~~Move button to `SketchConstraintsPanel` for in-sketch discoverability.~~ **DONE ✓**
2. ~~"Show underconstrained" button~~ — **DONE ✓** "Show u/c" button in toolbar; calls `executeTextCommand("Sketch.ShowUnderconstrained")`; result surfaced as toast.
3. ~~Filter / search by constraint type~~ — **DONE ✓** Filter bar below toolbar; client-side filtering by label/kind; section headers show `(N of M)` when active.
4. ~~Constraint icons matching Fusion's own glyph set.~~ **DONE ✓** Native Fusion PNGs copied at startup to `palette/icons/`; SVG fallback on load failure.
5. ~~Bulk delete with confirmation.~~ **DONE ✓** Checkboxes on deletable rows; "Delete N" + "Clear" toolbar buttons; Ctrl+Z note in confirm dialog; single × button removed.
6. ~~Inline editable dimension expression.~~ **DONE ✓** Expression shown in accent color below label; pencil icon (hover-visible) → inline `<input>`; Enter commits, Esc cancels; Python sets `param.expression` and refreshes.
7. ~~**Sketch-→-palette reverse lookup**~~ — **DONE ✓** "Find" button reads `activeSelections` from Python; JS searches snapshot entity tokens; matching rows highlighted (blue left border) and scrolled to. Pull-model (on demand), not event-driven.
8. ~~**Mark invisible / unselectable entities**~~ — **DONE ✓** `chip_for()` checks `entity.isVisible`; invisible chips rendered dimmed + dashed border + "hidden" badge. Note: clicking a row still selects/reveals the hidden entity on canvas — this is Fusion's native behaviour.
9. ~~**Normalize OffsetConstraint label**~~ — **DONE ✓** Label is now `Offset (1→1 curves, 30 mm)` style, pulling expression from the matched SketchOffsetCurvesDimension.
10. ~~**Dimension entity chip labels — show "Line 2" not "SketchLine"**~~ — **DONE ✓** `_DIM_ACCESSORS` map added to `dispatch.py`; Angular/Diameter/Radial and others now use type-specific accessors with `entityOne`/`entityTwo` fallback.
11. ~~**Verify fully-constrained green status**~~ — **VERIFIED PC test (session 5+).** Banner turns green and reads "— fully constrained" correctly.
12. ~~**Canvas-to-palette entity name lookup**~~ — **DONE ✓** Same "Find" button as #7; entity label shown in accent-color readout strip below filter bar ("Selected: Line 3"). Shares infrastructure with #7.
13. ~~**Double-click to open edit dialog**~~ — **DONE ✓** (pending PC test). Command IDs confirmed by probe: `OffsetSketchEdit`, `SketchPatternCircularEdit`, `SketchRectangularPatternEdit`. Uses `commandDefinitions.itemById(id).execute()` (not executeTextCommand). Pre-selects the entity before executing; for offset, selects the underlying OffsetConstraint.
14. ~~**Collapsible sections**~~ — **DONE ✓** Chevron ▾/▸ on each section header; clicking toggles `state.collapsed` Set; header always shows count; rows hidden when collapsed; state persists across data refreshes.
15. ~~**Editable configurable elements**~~ — **DONE ✓** (pending PC test). Circular pattern: inline edit `quantity` (Count) and `totalAngle` (Angle). Rectangular pattern: inline edit `quantityOne/Two` (Count 1/2) and `distanceOne/Two` (Spacing 1/2). All via `ModelParameter.expression`. PolygonConstraint has no writable params (API exposes only `lines`/`points` geometry) — shows read-only Sides count instead.
16. ~~**Entity chip click → filter**~~ — **DONE ✓** Clicking any entity chip sets filter bar to that label and re-renders. Chips have hover accent border and pointer cursor. `data-label` attribute avoids textContent issues with nested "hidden" badge.
17. ~~**Double-click to edit other dimension types**~~ — **DONE ✓** (pending PC test). Probe confirmed `SketchEditDimensionCmdDef` handles all sketch dimension types. `scanner.py` adds `isDimension: True` flag to all dimension rows; JS uses `data-is-dimension` attr to trigger dblclick without enumerating all 12 kind strings; lifecycle.py routes `isDimension` payloads to `SketchEditDimensionCmdDef`. `fixture_dimensions` test script creates Linear, Angular, Diameter, Radial, Offset, Distance, Concentric, Ellipse major/minor, arc dimensions.
18. ~~**Fusion UI icons for patterns, polygons, and dimensions**~~ — **DONE ✓** `CircularPatternConstraint` → `sketch/pattern_circular`, `RectangularPatternConstraint` → `sketch/pattern_rectangular` added to `_ICON_MAP`. `PolygonConstraint` → `Constraint_Polygon` was already there. Dimension rows now use a `"dimension"` glyph stem resolved via `_copy_dimension_icon()` (scans known command IDs then sketch resource base). All copies prefer `*-dark.png` variants (white glyphs for dark palette); `rowHTML` falls back to glyph stem when `row.kind` has no TYPE_ICONS entry. Verified ✓ v0.2.8.
19. ~~**Larger constraint icons in rows**~~ — **DONE ✓** Icons increased to 24×24 px. SVG fallbacks updated (viewBox kept at 16×16, rendered size 24). PNG copy now prefers 32×32 source (scales down cleanly) with 16×16 fallback.
20. ~~**"Select constraint object" moved to icon**~~ — **DONE ✓** Clicking the constraint icon (left glyph) now triggers `selectConstraint` directly. The separate ⌖ button on the right has been removed. Pseudo/join rows keep the ⊘ lock indicator unchanged.
21. **Chip click → also select object on canvas** — **DONE ✓** Chip now carries `data-token`; click handler sends `selectEntities` in addition to setting the filter.

---

## v1.3.x GUI Backlog

22. ~~**Canvas-click → immediate filter**~~ — **DONE ✓** (pending PC test). `onSelectionResult` auto-sets `state.filter` + `els.filter.value` to `matched[0].label` when exactly one entity is matched. Multi-entity selection leaves filter unchanged.

23. ~~**Filter clear button — always-visible, left of filter bar**~~ — **DONE ✓** (pending PC test). `✕` button added left of filter input in index.html; always visible; clears `state.filter` and re-renders. Native webkit search-cancel button hidden via `::-webkit-search-cancel-button { display: none }`.

24. ~~**Thin scrollbar in "Properties of selected"**~~ — **DONE ✓ PC verified.** `scrollbar-width: thin; scrollbar-color: var(--border) transparent` + webkit rules on `#footer-section`. Scrollbar appears at ~4.5 rows.

25. ~~**"Selected" chip strip — max 3 rows, then scroll**~~ — **DONE ✓ PC verified.** `max-height: 96px; overflow-y: auto` + thin scrollbar on `#entity-readout`. Scrollbar appears at ~4.5 chip rows.

26. ~~**"Select all" checkbox in section headers**~~ — **DONE ✓ PC verified.** Checkbox left of chevron in Geometric Constraints, Dimensions, and Patterns headers. Checked = all filtered deletable rows selected; indeterminate = some; unchecked = none. Row checkbox changes update section checkbox live. Clicking checkbox does not collapse the section. Endpoint Joins excluded (non-deletable).

27. ~~**Profile handling in "Properties of selected"**~~ — **DONE ✓ PC verified.** `_selection_props()` returns Area for `adsk.fusion.Profile` via `entity.areaProperties().area`; label shows loop count (`"Profile (2 loops)"`). `_format_selection_entity()` suppresses items where props is empty and label is the raw type name.

28. ~~**"Properties of selected" — one entity per row, max 3 rows, then scroll**~~ — **DONE ✓ PC verified.** `.sel-item` is `display: flex` (one entity per row); `#footer-section` capped at `max-height: 110px; overflow-y: auto` with thin scrollbar. Scrollbar appears at ~4.5 rows.

29. ~~**Zoom button — visible label + clearer active state**~~ — **DONE ✓ PC verified.** Button shows `⌕ Zoom` label (visible only when "Selected:" section is shown). Active state uses `background: var(--accent); color: #ffffff` fill.
