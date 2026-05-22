# FusionConstraints — ConstraintLens Add-in

## Current Status

**Working on:** v1 polish backlog.
**Version:** 0.2.3 (manifest + commit must always match) — polygon fixes, offset dblclick fix, chip→select+filter.
**Next step:** Pick next backlog item (see v1 Polish Backlog below).
**Convention:** Every commit that bumps the version string must also update `ConstraintLens/ConstraintLens.manifest` `"version"` field so Fusion shows the correct version.
**Blocked by:** Nothing.

### What's verified working (PC tests 1–5 + v0.1.6 session)
- Add-in loads, palette docks, populates without Refresh click.
- Geometric constraints list with click-to-select, ⌖ select-constraint, × delete + auto-refresh.
- Dimensions list (Angular, Linear, Diameter, etc.) with parameter expression.
- Implicit endpoint joins as pseudo-rows with implicit badge AND ⊘ lock icon + tooltip (0.1.3).
- Tangent spline+line row highlights both objects on click (0.1.3 — token-based selection).
- OffsetConstraint row lists curve chips (0.1.4).
- SketchOffsetCurvesDimension row lists curve chips AND highlights on click (0.1.5). ✓ PC test 5
- Sketch status banner (name, component, fully/under-constrained).
- M-1 defensive guard (MidPoint accessor) — both rows render; no crash.
- OffsetConstraint ACCESSOR error fixed in 0.1.2.
- Auto-load fixed in 0.1.2 (palette populated without Refresh click).
- Button relocated to `SketchConstraintsPanel` (Sketch tab → Constraints panel). ✓ backlog #1
- "Show u/c" button highlights underconstrained entities on canvas via `executeTextCommand("Sketch.ShowUnderconstrained")`; shows result string as toast. ✓ backlog #2
- Filter bar narrows rows by label or constraint type (case-insensitive, client-side); section headers show filtered count. ✓ backlog #3
- OffsetConstraint label normalised: `Offset (1→1 curves, 30 mm)` style. ✓ backlog #9
- Dimension entity chips show friendly names ("Line 2 → Line 3") for Angular, Diameter, Radial and other type-specific-accessor subtypes. ✓ backlog #10
- Bulk delete: checkboxes on deletable rows, "Delete N" + "Clear" buttons in toolbar, confirm dialog, Python loops deletions. Single × button removed. ✓ backlog #5
- Invisible entity chips (e.g. hidden spline-offset control geometry) rendered dimmed with dashed border and "hidden" badge. ✓ backlog #8

### What was fixed in 0.1.5 (verified PC test 5)
- **SketchOffsetCurvesDimension matching, hardened** — `_find_offset_constraint_for_dim` stacks four strategies because `OffsetConstraint.distance` returns None on the January 2026 build: (1) parameter entityToken, (2) parameter name, (3) positional pairing, (4) single-constraint fallback. Once matched, constraint's `parentCurves` + `childCurves` become the dimension's chips.

### Known sub-issues to keep on radar
- Offset-of-spline creates internal control geometry that Fusion doesn't render. User reports a tangent constraint on a line that isn't visible on the canvas. The row still appears in ConstraintLens but the line can't be selected by the user. See backlog #8.
- `OffsetConstraint.distance` returns None in the January 2026 build. The label-only consequence is now fully resolved via the matched dimension's parameter expression (backlog #9 fix).

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
17. **Double-click to edit other dimension types** — Angular, Linear, Diameter, Radial, etc. currently have no double-click dialog. Need to discover correct command IDs (probe required: scan all `SketchDimension*` command defs). Create a test script that builds one of every dimension type for systematic testing.
18. **Fusion UI icons for patterns and polygons** — `CircularPatternConstraint`, `RectangularPatternConstraint`, `PolygonConstraint` currently use a generic `pattern.svg` SVG fallback. Find the native Fusion icon folder names (probe via `commandDefinitions` resourceFolder inspection) and add them to `_ICON_MAP` in lifecycle.py.
19. **Larger constraint icons in rows** — Current icon size is 16×16 px. Increase to 20×20 or 24×24; adjust `.row-glyph` dimensions in styles.css accordingly.
20. ~~**"Select constraint object" moved to icon**~~ — **DONE ✓** Clicking the constraint icon (left glyph) now triggers `selectConstraint` directly. The separate ⌖ button on the right has been removed. Pseudo/join rows keep the ⊘ lock indicator unchanged.
21. **Chip click → also select object on canvas** — **DONE ✓** Chip now carries `data-token`; click handler sends `selectEntities` in addition to setting the filter.
