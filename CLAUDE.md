# FusionConstraints — ConstraintLens Add-in

## Current Status

**Working on:** Awaiting PC test session 4 to verify 0.1.4 fixes.
**Version:** 0.1.4 on branch `claude/fusion-constraintlens-spec-94gPu`.
**Next step:** PC test 4 — pull 0.1.4, check: (1) `OffsetConstraint` row now lists curve names as chips, (2) `SketchOffsetCurvesDimension` row highlights its curves on click. If clean → package for GitHub Release.
**Blocked by:** PC test session 4 (user needs to be at the Fusion PC).

### What's verified working (PC tests 1, 2, 3)
- Add-in loads, palette docks, populates without Refresh click.
- Geometric constraints list with click-to-select, ⌖ select-constraint, × delete + auto-refresh.
- Dimensions list (Angular, Linear, Diameter, etc.) with parameter expression.
- Implicit endpoint joins as pseudo-rows with implicit badge AND ⊘ lock icon + tooltip (0.1.3).
- Tangent spline+line row highlights both objects on click (0.1.3 — token-based selection).
- Sketch status banner (name, component, fully/under-constrained).
- M-1 defensive guard (MidPoint accessor) — both rows render; no crash.
- OffsetConstraint ACCESSOR error fixed in 0.1.2.
- Auto-load fixed in 0.1.2 (palette populated without Refresh click).

### What changed in 0.1.4 (needs PC test 4 verification)
- **OffsetConstraint row chips** — `_b_offset` now iterates `parentCurves` + `childCurves` via shared `_iter_curves_into_chips` helper and emits a chip per curve (was `[]`).
- **SketchOffsetCurvesDimension selection** — `describe_dimension` now tries `.curves`/`.parentCurves`/`.childCurves` directly, then falls back to finding the matching OffsetConstraint via parameter `entityToken` equality and pulling its curves. `scanner._scan_dimensions` now passes `sketch` into `describe_dimension`.

### Known sub-issues to keep on radar
- Offset-of-spline creates internal control geometry that Fusion doesn't render. User reports a tangent constraint on a line that isn't visible on the canvas. The row still appears in ConstraintLens but the line can't be selected by the user. See backlog item below.

---

## Project Overview

A Fusion 360 Python add-in that docks a panel listing every constraint in the active sketch — with click-to-select, delete, and over/under-constrained status. Fills the UX gap of having to hunt tiny on-canvas glyphs to audit a sketch.

- **Language:** Python 3.14 (Fusion January 2026 build), vanilla JS palette (no framework).
- **Distribution:** GitHub Releases only (zipped `ConstraintLens/` folder). No App Store.
- **Workspace:** Solid workspace only (MVP). Button lives in `SolidScriptsAddinsPanel` ("Add-ins" tab).
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

1. Move button to `SketchConstraintsPanel` for in-sketch discoverability.
2. "Show underconstrained" button (Q2 confirmed it works; enable only in sketch edit).
3. Filter / search by constraint type.
4. Constraint icons matching Fusion's own glyph set.
5. Bulk delete with confirmation.
6. Inline editable dimension expression.
7. **Sketch-→-palette reverse lookup** — user picks an entity on the canvas, ConstraintLens scrolls to / highlights every row that references it. Lets the user start from the geometry rather than the list.
8. **Mark invisible / unselectable entities** — Fusion creates internal control geometry for some operations (e.g. spline offsets create a hidden line that participates in a tangent constraint but isn't drawn on the canvas). Detect via `entity.isVisible` (or class-based heuristic) and badge the row / chip so users know the row references geometry they can't click.
