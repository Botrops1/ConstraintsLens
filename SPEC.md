# ConstraintLens — SPEC.md

> Architectural specification for the ConstraintLens Fusion 360 add-in. This document is finalized before any production code is written; the implementer should be able to execute it without revisiting design decisions.

---

## 1. Problem statement

Fusion 360's desktop sketch environment surfaces constraints only as tiny on-canvas glyphs with no list view, making non-trivial sketches painful to audit, repair, and de-clutter. The Fusion Python API fully exposes geometric constraints, dimensions, and entity references — everything needed to build the missing list — but no third-party add-in does this today. ConstraintLens fills the gap with a docked HTML palette that lists every constraint in the active sketch and lets the user click-select, delete, filter, and diagnose them.

---

## 2. Scope: MVP vs deferred

### MVP (target: ~30 hours of build, single developer + Claude Code)
- Dockable HTML palette registered under **Solid → Sketch → Inspect** panel, shown via a single command button "Constraint Lens".
- Live list of every `GeometricConstraint` in the **active sketch** (the one currently in edit mode). One row per constraint with: type icon, type name, human-readable label, involved entity chips.
- Live list of every `SketchDimension` in the active sketch (separate tab/section), with parameter expression shown read-only for MVP.
- Reconstructed list of **implicit coincident endpoint joins** via `SketchPoint.connectedEntities`, rendered as pseudo-rows with a distinct "implicit" badge.
- **Click row → select referenced entities** in the viewport via `ui.activeSelections`.
- **Click row's "Select constraint" affordance → select the constraint object itself** (so the user can use Fusion's native Delete key as an alternative path).
- **Delete button per row** invoking `constraint.deleteMe()`; disabled when `isDeletable == False`.
- Sketch status banner: `isFullyConstrained` + `healthState` + `errorOrWarningMessage`.
- Auto-refresh on `ui.commandTerminated` and `app.documentActivated`; manual "Refresh" button as backstop.
- Graceful "No active sketch" state.
- Distributed as a zipped add-in folder + README install snippet for `~/Autodesk/Autodesk Fusion 360/API/AddIns/`.

### Deferred (v1 polish, v2 premium — not in MVP)
- Filter / group / search controls (type, entity, redundant heuristic).
- Bulk delete with confirmation prompt.
- Hover-preview highlight via `CustomGraphics` overlay.
- Plugin-level undo stack (snapshot constraint set before destructive ops).
- Joint / AsBuiltJoint list panel.
- Editable dimension expression inline.
- Toggle for `sketch.areConstraintsShown` (hide native glyphs).
- "Show underconstrained" button wrapping `executeTextCommand("Sketch.ShowUnderconstrained")`.
- `AssemblyConstraint` (Constrain Components, January 2026 preview API) — **explicitly deferred until Autodesk drops the preview disclaimer.**
- App Store submission with installer (.msi / .pkg), screenshots, help URL.
- Multi-sketch / document-wide constraint browser.
- Redundant-constraint detector and auto-fix assistant.

---

## 3. Folder & file structure

```
FusionConstraints/
├── SPEC.md
├── README.md
├── ConstraintLens/
│   ├── ConstraintLens.manifest
│   ├── ConstraintLens.py
│   ├── resources/
│   │   ├── ConstraintLens/
│   │   │   ├── 16x16.png
│   │   │   ├── 32x32.png
│   │   │   └── 64x64.png
│   │   └── glyphs/
│   │       ├── parallel.svg
│   │       ├── perpendicular.svg
│   │       ├── horizontal.svg
│   │       ├── vertical.svg
│   │       ├── coincident.svg
│   │       ├── tangent.svg
│   │       ├── equal.svg
│   │       ├── collinear.svg
│   │       ├── concentric.svg
│   │       ├── midpoint.svg
│   │       ├── symmetric.svg
│   │       ├── offset.svg
│   │       ├── polygon.svg
│   │       ├── pattern.svg
│   │       └── surface.svg
│   └── lib/
│       ├── __init__.py
│       ├── lifecycle.py
│       ├── events.py
│       ├── dispatch.py
│       ├── scanner.py
│       ├── labels.py
│       ├── selection.py
│       ├── actions.py
│       ├── tokens.py
│       └── messaging.py
├── palette/
│   ├── index.html
│   ├── app.js
│   └── styles.css
└── tests/
    └── fixture_sketch.py
```

Path notes:
- The add-in root is `ConstraintLens/` (single directory, name-matches the `.py` and `.manifest` per Autodesk add-in convention).
- The palette HTML is served from inside the add-in folder via the local `palette/` directory copy at deploy time; during development the manifest entry resolves to the sibling `palette/` directory using a relative path. Keep it inside `ConstraintLens/palette/` for the shipped artifact — the top-level `palette/` is the source of truth.
- The shipped layout collapses the top-level `palette/` into `ConstraintLens/palette/`; the build step is a recursive copy (no bundler, no minifier — vanilla JS, single page).

---

## 4. Module responsibilities

**`ConstraintLens/ConstraintLens.manifest`** — Autodesk add-in manifest JSON. Declares add-in id, name, version, runs-on-startup flag, and the supported platforms. Owns nothing else; do not put logic here.

**`ConstraintLens/ConstraintLens.py`** — Add-in entry point. Implements only `run(context)` and `stop(context)`. Delegates immediately to `lib.lifecycle.start()` and `lib.lifecycle.stop()`. Does NOT contain command definitions, event handler classes, or palette logic.

**`lib/lifecycle.py`** — Owns command creation, palette creation, and panel-button registration. Calls `events.register_all()` on start, `events.unregister_all()` on stop, and registers a single `Commands.add("ConstraintLensShow")` toolbar button under `SolidScriptsAddinsPanel` (Sketch workspace) and `SolidCreatePanel` (Model workspace) — exact panel id confirmed at runtime spike. Does NOT iterate constraints or build UI content.

**`lib/events.py`** — Owns all event handler classes (subclassing `adsk.core.*EventHandler`) AND the module-level `_handlers: list[adsk.core.EventHandler]` list that keeps Python refs alive against GC. Exports `register_all(app, ui)` / `unregister_all(app, ui)`. Each handler's `notify()` delegates to a free function elsewhere (typically `scanner.publish_active_sketch(palette)`). Does NOT scan sketches or talk to the palette directly.

**`lib/dispatch.py`** — Owns the single source of truth for the **constraint type dispatch table** (section 5). Exports `DISPATCH: dict[str, ConstraintDescriptor]` keyed by `objectType` string (e.g. `"adsk::fusion::ParallelConstraint"`). Each descriptor declares accessor names, label-builder callable, glyph filename, and known-bug guard. Does NOT execute the lookups — `scanner.py` does.

**`lib/scanner.py`** — Owns enumeration. Walks `sketch.geometricConstraints`, `sketch.sketchDimensions`, and `sketch.sketchPoints` (for implicit joins), applies the `dispatch.DISPATCH` table, and emits a JSON-serializable payload via `messaging.build_data_payload()`. Returns plain dicts; never touches the palette. Does NOT cache between calls in MVP — a re-scan on every event is acceptable for the sketch sizes encountered.

**`lib/labels.py`** — Owns entity-display naming. Exports `EntityLabeler(sketch)` which on construction builds (token → "Line 3") maps by walking `sketchCurves.sketchLines`, `sketchPoints`, `sketchCurves.sketchCircles`, `sketchCurves.sketchArcs`, `sketchCurves.sketchEllipses`, `sketchCurves.sketchFittedSplines`, `sketchCurves.sketchControlPointSplines`. Pure data; one instance per scan.

**`lib/selection.py`** — Owns viewport selection. Exports `select_entities(ui, entities: list)` and `select_constraint(ui, constraint)`. Always clears `ui.activeSelections` first; wraps `.add()` calls in a single batch to minimize repaint flicker. Does NOT delete or modify entities.

**`lib/actions.py`** — Owns destructive operations. Exports `delete_constraint(constraint_token: str) -> ActionResult` and (deferred) `bulk_delete(tokens)`. Resolves the token via `tokens.resolve()`, checks `isDeletable`, invokes `deleteMe()`, returns success/failure with a message. Does NOT broadcast back to the palette — the caller triggers a refresh.

**`lib/tokens.py`** — Owns `entityToken` resolution. Exports `token_of(entity) -> str` (returns `entity.entityToken`) and `resolve(design, token: str) -> object | None` (uses `Design.findEntityByToken`, returns first element or `None`). Centralized so the rest of the code never touches the underlying API directly.

**`lib/messaging.py`** — Owns the palette ↔ Python wire format (section 7). Exports `send_to_palette(palette, action: str, payload: dict)`, `parse_from_palette(action: str, raw_json: str) -> dict`, and the JSON schemas as constants. JSON-serializes via `json.dumps(payload, default=str)`. Does NOT contain business logic.

**`palette/index.html`** — Single-page palette shell. Loads `app.js` and `styles.css`. Provides root `<div id="root">` and the `adsk.fusionSendData` plumbing. No logic beyond bootstrap.

**`palette/app.js`** — Vanilla JS (no framework, no build step). Owns: render loop, message handler for `Python → JS` actions, click delegation to the appropriate `JS → Python` action via `adsk.fusionSendData(action, JSON.stringify(payload))`. Single global `state` object holding the latest snapshot from Python. No virtual DOM library — direct innerHTML diffing is fine at MVP scale.

**`palette/styles.css`** — Owns visual styling. Matches Fusion's dark palette by default; CSS variables for theming. No logic.

**`tests/fixture_sketch.py`** — Owns the dev smoke fixture (section 8). Stand-alone Fusion script (not part of the add-in) that builds a deterministic sketch. Run via Scripts & Add-Ins → Scripts → Run.

---

## 5. Constraint type dispatch table

Every `GeometricConstraint` subtype listed below is exhaustively covered. The dispatch table key is the `objectType` string returned by the API (e.g. `"adsk::fusion::ParallelConstraint"`); the human-readable label is built by `labels.EntityLabeler` plus the per-row template shown in the "Label template" column.

**Important: the two research docs conflict on accessor naming.** Doc 1 implies a universal `entityOne` / `entityTwo` pair on `GeometricConstraint`. Doc 2 — which is correct against the Autodesk API reference — shows that each subtype has its own accessors (`lineOne`/`lineTwo`, `curveOne`/`curveTwo`, `point`/`entity`, etc.). **The dispatch table follows doc 2.** Any code that tries `hasattr(c, 'entityOne')` is a bug per this spec.

| # | `objectType` | API class | Entity accessors (return type) | Label template | Known bugs / edge cases |
|---|---|---|---|---|---|
| 1 | `adsk::fusion::HorizontalConstraint` | `HorizontalConstraint` | `.line` (SketchLine) | `Horizontal — {line}` | none |
| 2 | `adsk::fusion::VerticalConstraint` | `VerticalConstraint` | `.line` (SketchLine) | `Vertical — {line}` | **Not enumerated in either research doc but documented in the Fusion API; treat as a peer of `HorizontalConstraint`.** Flag for runtime verification (open question 5). |
| 3 | `adsk::fusion::HorizontalPointsConstraint` | `HorizontalPointsConstraint` | `.pointOne`, `.pointTwo` (SketchPoint) | `Horizontal align — {p1} ↔ {p2}` | none |
| 4 | `adsk::fusion::VerticalPointsConstraint` | `VerticalPointsConstraint` | `.pointOne`, `.pointTwo` (SketchPoint) | `Vertical align — {p1} ↔ {p2}` | none |
| 5 | `adsk::fusion::ParallelConstraint` | `ParallelConstraint` | `.lineOne`, `.lineTwo` (SketchLine) | `Parallel — {l1} ∥ {l2}` | none |
| 6 | `adsk::fusion::PerpendicularConstraint` | `PerpendicularConstraint` | `.lineOne`, `.lineTwo` (SketchLine) | `Perpendicular — {l1} ⊥ {l2}` | none |
| 7 | `adsk::fusion::CollinearConstraint` | `CollinearConstraint` | `.lineOne`, `.lineTwo` (SketchLine) | `Collinear — {l1} ⋯ {l2}` | none |
| 8 | `adsk::fusion::CoincidentConstraint` | `CoincidentConstraint` | `.point` (SketchPoint), `.entity` (SketchEntity — line, circle, arc, ellipse, spline, point) | `Coincident — {point} on {entity}` | This is **the explicit coincident constraint only**; endpoint "joins" between curves are not stored here — see implicit-joins row at the bottom. |
| 9 | `adsk::fusion::CoincidentToSurfaceConstraint` | `CoincidentToSurfaceConstraint` | `.point` (SketchPoint), `.surface` (BRepFace or ConstructionPlane) | `Coincident to surface — {point}` | Surface may be in another component; resolve `surface.body.parentComponent` for display, fall back to `"external surface"`. |
| 10 | `adsk::fusion::TangentConstraint` | `TangentConstraint` | `.curveOne`, `.curveTwo` (SketchCurve) | `Tangent — {c1} ⌒ {c2}` | none |
| 11 | `adsk::fusion::EqualConstraint` | `EqualConstraint` | `.curveOne`, `.curveTwo` (SketchCurve — line/arc/circle pair, mixing requires matching kinds) | `Equal — {c1} = {c2}` | none |
| 12 | `adsk::fusion::ConcentricConstraint` | `ConcentricConstraint` | `.entityOne`, `.entityTwo` (SketchCircle, SketchArc, or SketchEllipse) | `Concentric — {e1} ⊙ {e2}` | This subtype **does** use `entityOne/entityTwo` (one of the few that match doc 1's claim). |
| 13 | `adsk::fusion::MidPointConstraint` | `MidPointConstraint` | `.point` (SketchPoint), `.midPointCurve` (SketchCurve) | `Midpoint — {point} mid {curve}` | **Known bug** (doc 2): `.point` raises for midpoint-to-midpoint configurations. **Defensive pattern: see section 9 landmine M-1.** |
| 14 | `adsk::fusion::SymmetryConstraint` | `SymmetryConstraint` | `.entityOne`, `.entityTwo` (SketchCurve or SketchPoint), `.symmetryLine` (SketchLine) | `Symmetric — {e1} ↔ {e2} about {symLine}` | none |
| 15 | `adsk::fusion::OffsetConstraint` | `OffsetConstraint` | `.parentCurves` (ObjectCollection), `.childCurves` (ObjectCollection), `.distance` (ModelParameter) | `Offset {n}→{m} curves @ {distance.expression}` | Collections, not single entities — render counts in the label, expand only on row click. |
| 16 | `adsk::fusion::PolygonConstraint` | `PolygonConstraint` | `.lines` (ObjectCollection of SketchLine), `.centerSketchPoint` (SketchPoint) | `Polygon ({n} sides) about {center}` | Inscribed vs circumscribed is not exposed via API; do not attempt to display it. |
| 17 | `adsk::fusion::CircularPatternConstraint` | `CircularPatternConstraint` | **No usable accessors** — read-only stub (doc 2, confirmed by Brian Ekins on Autodesk forum). | `Circular pattern (read-only)` | Only `deleteMe()` works. Disable "Select entities" button for this row; "Delete" remains enabled. |
| 18 | `adsk::fusion::RectangularPatternConstraint` | `RectangularPatternConstraint` | **No usable accessors** — read-only stub. | `Rectangular pattern (read-only)` | Same handling as #17. |
| 19 | `adsk::fusion::LineOnPlanarSurfaceConstraint` | `LineOnPlanarSurfaceConstraint` | `.line` (SketchLine), `.planarSurface` (BRepFace or ConstructionPlane) | `Line on surface — {line}` | Surface may be external; same fallback as #9. |
| 20 | `adsk::fusion::LineParallelToPlanarSurfaceConstraint` | `LineParallelToPlanarSurfaceConstraint` | `.line`, `.planarSurface` | `Line ∥ surface — {line}` | same |
| 21 | `adsk::fusion::PerpendicularToSurfaceConstraint` | `PerpendicularToSurfaceConstraint` | `.line`, `.planarSurface` | `Line ⊥ surface — {line}` | same |
| **PSEUDO** | *(implicit coincident endpoint join)* | reconstructed from `SketchPoint.connectedEntities` | `point` (the shared SketchPoint), `entities` (list of SketchCurves whose endpoints share `point`) | `Endpoint join — {point} connects {curve list}` (badge: "implicit") | **Not a real `GeometricConstraint`.** Surface only when `SketchPoint.connectedEntities.count > 1`. Has no `entityToken` of its own — use the SketchPoint's token prefixed with `"join:"` as the row key. **`deleteMe()` is not applicable** — deletion would require breaking the shared point, which is not safe via API. Disable Delete for these rows. |

**Label template substitutions** (resolved by `labels.EntityLabeler`):
- `{line}` → e.g. `"Line 3"` (1-indexed by position in `sketch.sketchCurves.sketchLines`).
- `{point}` → e.g. `"Point 7"` (1-indexed in `sketch.sketchPoints`).
- `{e1}`, `{c1}` etc. → kind-aware name (e.g. `"Circle 2"`, `"Arc 4"`).
- `{distance.expression}` → the parameter expression string, e.g. `"10 mm"`.

**Dimension subclasses** are enumerated separately (via `sketch.sketchDimensions`) and follow a parallel but simpler dispatch in `dispatch.py`:
`SketchAngularDimension`, `SketchConcentricCircleDimension`, `SketchDiameterDimension`, `SketchDistanceBetweenLineAndPlanarSurfaceDimension`, `SketchDistanceBetweenTwoLinesDimension`, `SketchEllipseMajorRadiusDimension`, `SketchEllipseMinorRadiusDimension`, `SketchLinearDimension`, `SketchOffsetCurvesDimension`, `SketchOffsetDimension`, `SketchRadialDimension`, `SketchTangentDistanceDimension`. Each exposes `.parameter.expression` (read-only display in MVP), plus `.entityOne` / `.entityTwo` (kinds vary). Build the same row schema.

---

## 6. Event handler registration pattern

The Fusion API uses C++ event objects bridged to Python. If a Python handler instance is dropped, the C++ side holds a dangling reference and the next callback crashes Fusion silently. **Always pin handlers in a module-level list.**

### Pattern

```python
# lib/events.py
import adsk.core, adsk.fusion

_handlers: list[adsk.core.EventHandler] = []
_subscriptions: list[tuple[adsk.core.Event, adsk.core.EventHandler]] = []


class _DocumentActivatedHandler(adsk.core.DocumentEventHandler):
    def __init__(self, on_change):
        super().__init__()
        self._on_change = on_change

    def notify(self, args: adsk.core.DocumentEventArgs):
        try:
            self._on_change()
        except Exception:
            import traceback
            adsk.core.Application.get().userInterface.messageBox(
                "ConstraintLens handler error:\n" + traceback.format_exc()
            )


class _CommandTerminatedHandler(adsk.core.ApplicationCommandEventHandler):
    def __init__(self, on_change):
        super().__init__()
        self._on_change = on_change

    def notify(self, args: adsk.core.ApplicationCommandEventArgs):
        try:
            self._on_change()
        except Exception:
            pass  # never let a handler exception escape into Fusion


def register_all(app: adsk.core.Application, ui: adsk.core.UserInterface, on_change) -> None:
    h1 = _DocumentActivatedHandler(on_change)
    app.documentActivated.add(h1)
    _handlers.append(h1)
    _subscriptions.append((app.documentActivated, h1))

    h2 = _CommandTerminatedHandler(on_change)
    ui.commandTerminated.add(h2)
    _handlers.append(h2)
    _subscriptions.append((ui.commandTerminated, h2))


def unregister_all() -> None:
    for event, handler in _subscriptions:
        try:
            event.remove(handler)
        except Exception:
            pass
    _subscriptions.clear()
    _handlers.clear()
```

### Which events to subscribe to and when

| Event | Subscribe in | Why | Cost of firing |
|---|---|---|---|
| `app.documentActivated` | `lifecycle.start()` | Active sketch may change when user switches documents. | Cheap (sketch may be `None` — handler short-circuits). |
| `ui.commandTerminated` | `lifecycle.start()` | Fires after every Fusion command, including sketch edits. The reliable "something changed" signal — Autodesk does not expose a `sketchModified` event. | Re-scans the active sketch; acceptable for MVP because sketches are bounded in size. |
| `palette.closed` | `lifecycle.start()` (on the palette object itself) | Stops sending updates when the user closes the palette. | One-shot. |
| `palette.navigatingURL` | `lifecycle.start()` | Intercept any link clicks in the HTML so they open in the system browser rather than the embedded Qt browser. | Rare. |
| `palette.incomingFromHTML` | `lifecycle.start()` | Receives `JS → Python` messages (see section 7). | One per user action. |

**Do NOT subscribe to** `app.documentSaving`, `app.documentSaved`, or per-sketch entity events — none of them fire reliably on the constraint-list edits that matter, and `commandTerminated` already covers the cases.

**Lifetime rule:** handlers are created in `register_all()` and only ever destroyed in `unregister_all()`. Never re-instantiate a handler mid-session; replace the callback target via a closure capturing a mutable reference instead.

---

## 7. Palette HTML ↔ Python message contract

Direction notation: **JS→PY** = JavaScript calls `adsk.fusionSendData(action, jsonString)`, handled in Python via `palette.incomingFromHTML`. **PY→JS** = Python calls `palette.sendInfoToHTML(action, jsonString)`, received in JS via `window.fusionJavaScriptHandler.handle(action, data)`.

All payloads are JSON. Unknown action names are logged and ignored (forward-compat).

### JS → PY actions

| Action | Direction | Payload schema | Notes |
|---|---|---|---|
| `paletteReady` | JS→PY | `{}` | Sent once on palette load. Python responds with a `data` push. |
| `requestRefresh` | JS→PY | `{}` | Manual refresh button. Python re-scans and pushes `data`. |
| `selectEntities` | JS→PY | `{"rowKey": "<token-or-pseudo-key>"}` | Selects the referenced entities in the viewport. |
| `selectConstraint` | JS→PY | `{"token": "<entityToken>"}` | Selects the constraint object itself (not valid for pseudo rows — JS must not send these). |
| `deleteConstraint` | JS→PY | `{"token": "<entityToken>"}` | Deletes via `constraint.deleteMe()`. Python pushes `data` after. |
| `openLogConsole` | JS→PY | `{}` | (Deferred) opens a Python-side debug log dump in a message box. |

### PY → JS actions

| Action | Direction | Payload schema | Notes |
|---|---|---|---|
| `data` | PY→JS | see below | Full snapshot. Sent on `paletteReady`, `requestRefresh`, every subscribed event, and after any destructive action. |
| `noActiveSketch` | PY→JS | `{"reason": "<string>"}` | Sent when `design.activeEditObject` is not a `Sketch`. Palette renders an empty state. |
| `error` | PY→JS | `{"message": "<string>", "context": "<string>"}` | Recoverable errors only — fatal errors fall back to `ui.messageBox`. |
| `actionResult` | PY→JS | `{"action": "deleteConstraint", "ok": true, "message": "<string>"}` | Optional toast; the subsequent `data` push is the authoritative source of truth. |

### `data` payload schema

```json
{
  "sketch": {
    "name": "Sketch1",
    "componentName": "Body1",
    "isFullyConstrained": false,
    "healthState": "WarningHealthState",
    "errorOrWarningMessage": "Under-constrained: 2 points free"
  },
  "constraints": [
    {
      "rowKey": "abc123def456",
      "token": "abc123def456",
      "kind": "ParallelConstraint",
      "objectType": "adsk::fusion::ParallelConstraint",
      "label": "Parallel — Line 2 ∥ Line 4",
      "glyph": "parallel.svg",
      "entities": [
        {"token": "...", "kind": "SketchLine", "label": "Line 2"},
        {"token": "...", "kind": "SketchLine", "label": "Line 4"}
      ],
      "isDeletable": true,
      "isPseudo": false,
      "errors": []
    }
  ],
  "dimensions": [
    {
      "rowKey": "...",
      "token": "...",
      "kind": "SketchLinearDimension",
      "label": "Linear: Line 1 → Line 3 = 40 mm",
      "parameterExpression": "40 mm",
      "isDeletable": true,
      "errors": []
    }
  ],
  "implicitJoins": [
    {
      "rowKey": "join:<sketchPointToken>",
      "token": null,
      "kind": "ImplicitCoincidentJoin",
      "label": "Endpoint join — Point 5 connects Line 1, Line 2",
      "entities": [
        {"token": "...", "kind": "SketchPoint", "label": "Point 5"},
        {"token": "...", "kind": "SketchLine", "label": "Line 1"},
        {"token": "...", "kind": "SketchLine", "label": "Line 2"}
      ],
      "isDeletable": false,
      "isPseudo": true,
      "errors": []
    }
  ]
}
```

The `errors` array on a row is non-empty when an accessor raised (e.g. `MidPointConstraint.point` bug, see section 9). The row is still rendered so the user can delete it; the entity chips are replaced by an "accessor error" placeholder.

### Why this contract is shaped this way

- **All actions are token-based**, never positional. Lists may re-order between scans; positional indices would break delete-after-refresh.
- **Pseudo rows use `rowKey` only**, never `token`, because they don't have one. JS code branches on `isPseudo` rather than `token == null`.
- **Python always pushes a fresh `data` after every destructive action.** JS never mutates its local state speculatively — fewer race conditions, no rollback logic to write.

---

## 8. Fixture sketch script

The fixture creates a deterministic sketch in 30 seconds with: a rectangle (4 lines, shared endpoints), a circle, **4 explicit geometric constraint types** (Horizontal, Vertical, Parallel, Tangent), and **2 dimensions** (linear width, circle diameter). Save as `tests/fixture_sketch.py`, then in Fusion: **Tools → Scripts and Add-Ins → Scripts → +/folder → point at this file → Run**.

```python
# tests/fixture_sketch.py
# Run from Fusion: Tools → Scripts and Add-Ins → Scripts → Run.
# Creates a fully-known fixture sketch for ConstraintLens dev iteration.

import adsk.core
import adsk.fusion
import traceback


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox("Open a Fusion design (not a drawing) first.")
            return

        root = design.rootComponent
        sketch = root.sketches.add(root.xYConstructionPlane)
        sketch.name = "ConstraintLens_Fixture"

        # Drawing the rectangle as four lines with shared endpoints,
        # so we get the implicit coincident-join behavior to test against.
        lines = sketch.sketchCurves.sketchLines
        P = adsk.core.Point3D.create
        bottom = lines.addByTwoPoints(P(0, 0, 0), P(4, 0, 0))
        right = lines.addByTwoPoints(bottom.endSketchPoint, P(4, 2, 0))
        top = lines.addByTwoPoints(right.endSketchPoint, P(0, 2, 0))
        left = lines.addByTwoPoints(top.endSketchPoint, bottom.startSketchPoint)

        # Circle, positioned to allow a tangent with the top edge.
        circles = sketch.sketchCurves.sketchCircles
        circle = circles.addByCenterRadius(P(2.0, 1.4, 0), 0.5)

        # Four explicit geometric constraint subtypes.
        gc = sketch.geometricConstraints
        gc.addHorizontal(bottom)         # HorizontalConstraint
        gc.addVertical(left)             # VerticalConstraint
        gc.addParallel(top, bottom)      # ParallelConstraint
        gc.addTangent(circle, top)       # TangentConstraint

        # Two dimensions: one linear (rectangle width), one diameter (circle).
        dims = sketch.sketchDimensions
        dims.addDistanceDimension(
            bottom.startSketchPoint,
            bottom.endSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            P(2.0, -0.7, 0),
        )
        dims.addDiameterDimension(circle, P(3.2, 2.0, 0))

        ui.messageBox(
            "ConstraintLens fixture created.\n"
            f"Sketch: {sketch.name}\n"
            f"Geometric constraints: {sketch.geometricConstraints.count}\n"
            f"Dimensions: {sketch.sketchDimensions.count}\n"
            f"Fully constrained: {sketch.isFullyConstrained}"
        )
    except Exception:
        if ui:
            ui.messageBox("Failed:\n" + traceback.format_exc())
```

After running: open the sketch for edit (so `design.activeEditObject` is the sketch), then click **Constraint Lens** in the Sketch panel. You should see exactly: 4 explicit geometric constraint rows, 2 dimension rows, and 4 implicit coincident-join pseudo-rows (one per rectangle corner).

---

## 9. Known API landmines

Each landmine is named (M-N) so code comments can reference it.

### M-1 — `MidPointConstraint.point` raises on midpoint-to-midpoint
Documented in research doc 2. The scanner must guard every accessor lookup:

```python
def _safe(getter, default=None):
    try:
        return getter()
    except Exception:
        return default

point = _safe(lambda: constraint.point)
curve = _safe(lambda: constraint.midPointCurve)
errors = []
if point is None:
    errors.append("midpoint-to-midpoint: .point accessor unavailable (Fusion bug)")
```

The row is still emitted; the palette renders `<accessor error>` for the missing chip.

### M-2 — `CircularPatternConstraint` / `RectangularPatternConstraint` are read-only stubs
Per Brian Ekins (cited in doc 2). No entity accessors are usable. The dispatch descriptor sets `entities=[]` and the palette disables the "Select entities" button for these row kinds — only "Delete" remains active.

### M-3 — Coincident endpoint joins are not constraints
Per Brian Ekins (doc 2). They are shared `SketchPoint` instances. The scanner walks `sketch.sketchPoints` and emits a pseudo-row whenever `point.connectedEntities.count > 1`. Pseudo rows:
- Use `rowKey = "join:" + point.entityToken`.
- Have `token = null`.
- Have `isDeletable = false` (deleting the shared point is destructive and out of MVP scope).

### M-4 — `AssemblyConstraint` is preview API
Per the January 2026 Fusion API "What's New" page (doc 2). MVP **does not import, scan, or expose** `AssemblyConstraint`. Track the disclaimer on every Fusion release; revisit when removed.

### M-5 — `SketchConstraints` selection filter omits dimensions
Per doc 1 / doc 2. ConstraintLens does not rely on this filter; the scanner reads `sketchDimensions` directly from the `Sketch` object, so this landmine cannot affect us. Documented here so a future contributor doesn't try to "simplify" by using the filter.

### M-6 — Iterators are `.item(i)`, not `[i]`
The collection classes (`GeometricConstraints`, `SketchPoints`, etc.) support `for x in coll` and `coll.item(i)` and `coll.count`, but **not subscripting** (`coll[0]` raises). Spec: use `for` loops; reach for `.item(i)` only when index access is required (e.g. building 1-based labels — `for i in range(coll.count): coll.item(i)`).

### M-7 — Handlers freed by GC crash Fusion silently
See section 6. **Single defensive pattern:** the module-level `_handlers` list in `lib/events.py`. No exceptions.

### M-8 — `Palette.sendInfoToHTML` may freeze Fusion if the data panel is being browsed (UP-38529)
Per doc 2. Defensive pattern: gate every `sendInfoToHTML` call on `palette.isVisible == True`. Skip the push otherwise; the next event refreshes on its own.

### M-9 — `Sketch.ShowUnderconstrained` only returns a text summary
Per doc 2. MVP does not parse this output; the deferred underconstrained button surfaces the raw text in a banner. Do not attempt to map counts back to entities — there is no API surface for it.

### M-10 — No granular CAD undo for constraint operations
Per doc 2. MVP does not implement an undo stack; delete actions show a confirmation dialog in v1, not MVP. Document this in the README user-facing notes so users know to use Fusion's `Ctrl+Z` (which undoes the whole sketch-edit chunk, not the single constraint delete).

### M-11 — `executeTextCommand` must run inside a sketch edit context
Empirically required for `Sketch.ShowUnderconstrained`. The deferred button enables only when `design.activeEditObject is a Sketch`. See open question 2.

### M-12 — Python version churn
Per doc 2 — Fusion has gone 3.7 → 3.9.7 → 3.12 → 3.14 in roughly four release cycles. Spec rules: ship `.py` source only (no `.pyc`); no native extensions; no dependencies outside the Python stdlib and the Autodesk-provided `adsk.*` modules.

### M-13 — Doc-1 / Doc-2 conflict on accessor naming
Doc 1 says `entityOne` / `entityTwo` exist on every `GeometricConstraint`. Doc 2 (and the Autodesk reference) shows accessor names differ by subtype. **Resolution: follow doc 2.** This spec's dispatch table (section 5) is authoritative; any code resembling `getattr(c, 'entityOne', None)` as a generic accessor strategy is incorrect.

### M-14 — Doc-1 / Doc-2 conflict on highlight mechanism
Doc 1 mentions `isLightBulbOn` for highlighting. That property controls browser-tree visibility, not selection highlight. **Resolution:** use `ui.activeSelections.add(...)` exclusively (doc 2). `isLightBulbOn` is not referenced anywhere in MVP code.

---

## 10. Open questions

Maximum five, each with a proposed validation approach. These cannot be resolved without running code inside Fusion.

1. **Exact panel id for the Sketch toolbar button.** Doc 2 mentions placement under the "Inspect" panel of the Solid workspace, but the canonical id (e.g. `SolidScriptsAddinsPanel` vs `SketchInspectPanel`) needs verification. **Validation:** in the Text Commands window, run `Commands.GetItemList` and grep for sketch panels; pick the one that shows when in sketch edit mode.

2. **Whether `executeTextCommand("Sketch.ShowUnderconstrained")` requires an active sketch edit context.** Doc 2 cites `bachi.net` for the text-command output but does not confirm the precondition. **Validation:** call the command via `app.executeTextCommand` outside sketch edit; observe whether it returns the count text, an error string, or raises. Wrap accordingly.

3. **Refresh strategy when `palette.isVisible == False`.** UP-38529 (M-8) suggests skipping pushes when not visible — but does the palette emit a `shown` event we can hook to push a delayed refresh? **Validation:** trace `palette.*` event firing during minimize/restore and document the cycle.

4. **Stability of `entityToken` for `GeometricConstraint` objects across save-reload.** Doc 1 implies general stability via `Design.findEntityByToken`; doc 2 does not confirm this specifically for constraints. **Validation:** capture a constraint's token, save and reload the document, attempt `findEntityByToken(token)`; if it returns null, fall back to rowKey-by-position (less robust — would change `messaging.py` schema).

5. **Whether `VerticalConstraint` is actually surfaced by the API or only created implicitly.** Neither research doc explicitly lists it as a `GeometricConstraint` subclass — but `GeometricConstraints.addVertical(line)` is documented. **Validation:** the fixture sketch (section 8) creates one via `addVertical`; the spike script then iterates `sketch.geometricConstraints` and prints each `objectType` — confirm `"adsk::fusion::VerticalConstraint"` appears. If not, update the dispatch table to mark it as "creation-only, never enumerated."

---

# Confirmed decisions (locked)

The three forks the spec previously deferred to the project owner have been resolved.

1. **Target Fusion version & Python — latest only.**
   ConstraintLens targets the January 2026 Fusion build and later, running on Python 3.14. Implementation rules that follow from this:
   - `Palettes.add(..., useQtWebBrowser=True)` is called unconditionally; no CEF fallback path is written.
   - Type annotations use 3.12+ syntax: `list[X]`, `dict[K, V]`, `X | None`. **Do not** add `from __future__ import annotations` or import `Optional`/`List` from `typing`.
   - `match` statements are permitted in `dispatch.py` if they read cleaner than the descriptor table; the descriptor table remains the source of truth either way.

2. **Distribution — GitHub Releases only for MVP.**
   The deliverable is a zipped `ConstraintLens/` add-in folder published as a GitHub Release, plus a README install snippet pointing at `~/Autodesk/Autodesk Fusion 360/API/AddIns/`. Implementation rules:
   - No `installer/`, `store_assets/`, or signing directories in the repo.
   - No App Store metadata, help-URL pages, or screenshot kit.
   - The README install snippet must cover both Windows and macOS path conventions.
   - App Store submission is explicitly out of MVP scope; revisit only after the deferred v1 features in section 2 land.

3. **Workspace coverage — Solid sketches only.**
   The toolbar button is registered in the Solid workspace only (panel id to be confirmed per open question 1). Implementation rules:
   - `lifecycle.py` registers exactly one command-button placement; do not loop over workspaces.
   - The scanner is intentionally workspace-agnostic (it operates on the `Sketch` passed in), so future workspaces are an additive change to `lifecycle.py` only.
   - Sheet Metal / Form / Surface / Drawing support is a v1 polish item; do not write feature flags for it in MVP.
