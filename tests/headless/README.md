# Headless tests

Plain `unittest` over the add-in's pure logic. **Not Fusion scripts** — they run
anywhere Python 3.11+ does, with no Fusion installed, and CI runs them on every
push.

```sh
cd tests/headless && python3 -m unittest discover -v
```

`stubs/adsk/` is a hand-written stand-in for the Fusion `adsk` package: just
enough of it that `ConstraintLens/lib/*.py` imports, which is the handler base
classes those modules subclass and the entity classes they use in `isinstance`
checks and annotations. `fakes.py` builds sketch-shaped objects on top of it
that count every accessor read, which is how a test can assert that a scan
describes each constraint once rather than twice.

## What this can and cannot tell you

**Can:** sectioning and row contents from `build_payload`, how many times an
accessor is read, label and value formatting, the labeler cache's invalidation
rules, the unit conversion tables, defensive behaviour when an accessor raises.

**Cannot:** anything about real Fusion objects, palette geometry, docking,
event delivery, or whether an API call behaves as its documentation claims.
Those still need a PC test — see `PC_VALIDATION.md`.

The palette's HTML/CSS/JS is testable headlessly too, via Playwright against
`ConstraintLens/palette/index.html` over `file://`; see the note in `CLAUDE.md`.
