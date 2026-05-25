# FusionConstraints — ConstraintLens Add-in

## Current Status

**Working on:** Maintenance / community issues.
**Version:** 1.2.0 (manifest + commit must always match).
**Next step:** Monitor for new issues; next planned work TBD.
**Convention:** Every commit that bumps the version string must also update `ConstraintLens/ConstraintLens.manifest` `"version"` field so Fusion shows the correct version.
**Blocked by:** Nothing.

### Recent fixes (v1.0.1–v1.2.0)
- v1.2.0: Issue #3 follow-up — the binary dock toggle is replaced by a multi-position cycle (Float / Right / Left / Bottom / Top) so users can dock to a side that doesn't block Fusion's bottom-right selection-info overlay. A new selection-info footer inside the palette mirrors the same length / radius / area / volume readout, driven by `UserInterface.activeSelectionChanged` (push, not poll). `settings.json` migrated from `{"docked": bool}` to `{"dock_state": "<name>"}`; legacy key auto-migrates on first load. Unsupported dock-state enum members are pruned at runtime so the cycle button never offers a state Fusion would reject. Best-effort `setMaximumSize` cap applied when docking, in case the build honours it. Probe `tests/probe_palette/probe_palette.py` enumerates the API surface for verification.
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
- "Show underconstraint elements" button — calls `executeTextCommand("Sketch.ShowUnderconstrained")`; result as toast.
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
