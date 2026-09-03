"""Drive the real palette HTML in a browser and check its behaviour.

The palette is plain HTML/CSS/JS with no build step, so it runs anywhere —
point a browser at ConstraintLens/palette/index.html over file://, call the
same window.fusionJavaScriptHandler.handle() that Fusion calls, and assert on
the resulting DOM. That is much faster than a copy-and-restart cycle in Fusion
and it catches the whole class of bug that lives in app.js.

    pip install playwright && playwright install chromium
    python3 tests/headless/palette_ui_check.py

Deliberately not named test_*.py: `unittest discover` in this directory must
stay runnable with nothing installed. This one needs a browser.

What it cannot tell you is anything about Fusion's Qt web view, the real dock
column, or the Python side — those still need a PC test.
"""

import glob
import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PALETTE = (REPO_ROOT / "ConstraintLens" / "palette" / "index.html").as_uri()


def chromium_path():
    """A pre-installed Chromium if there is one, else let Playwright choose.

    A `pip install playwright` looks for its own build number, so a browser
    that came with the environment has to be named explicitly. In CI,
    `playwright install chromium` puts one where Playwright expects it and
    this returns None.
    """
    named = os.environ.get("CL_CHROMIUM")
    if named:
        return named
    for pattern in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",
                    "/opt/pw-browsers/chromium/chrome-linux/chrome"):
        found = sorted(glob.glob(pattern))
        if found:
            return found[-1]
    return None


def row(key, kind, label, chips):
    return {
        "rowKey": key, "token": key, "kind": kind,
        "objectType": "adsk::fusion::" + kind, "label": label,
        "glyph": "coincident.svg",
        "entities": [{"token": t, "kind": "SketchLine", "label": lbl, "invisible": False}
                     for t, lbl in chips],
        "isDeletable": True, "isPseudo": False, "errors": [], "parameters": [],
    }


SKETCH_ONE = {
    "sketch": {"name": "Sketch1", "componentName": "Comp1", "isFullyConstrained": False},
    "constraints": [
        row("c1", "ParallelConstraint", "Parallel — Line 1 ∥ Line 2",
            [("l1", "Line 1"), ("l2", "Line 2")]),
        row("c2", "TangentConstraint", "Tangent — Line 3 ⌒ Arc 1",
            [("l3", "Line 3"), ("a1", "Arc 1")]),
    ],
    "dimensions": [], "patterns": [], "implicitJoins": [],
}

SKETCH_TWO = {
    "sketch": {"name": "Sketch2", "componentName": "Comp1", "isFullyConstrained": False},
    "constraints": [row("c9", "EqualConstraint", "Equal — Circle 9 = Circle 8",
                        [("z9", "Circle 9")])],
    "dimensions": [], "patterns": [], "implicitJoins": [],
}


class Checks:
    def __init__(self):
        self.failed = []

    def __call__(self, name, got, want):
        if got == want:
            print(f"PASS  {name}")
        else:
            print(f"FAIL  {name}\n        got  {got!r}\n        want {want!r}")
            self.failed.append(name)


def main():
    check = Checks()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium_path())
        page = browser.new_page()
        # Fusion injects this bridge into the view; nothing here reads what is
        # sent, only that sending does not throw.
        page.add_init_script(
            "window.__sent = [];"
            "window.adsk = { fusionSendData: (a, d) => window.__sent.push([a, d]) };"
        )
        page.goto(PALETTE)

        def deliver(action, payload):
            page.evaluate(
                "([a, p]) => window.fusionJavaScriptHandler.handle(a, JSON.stringify(p))",
                [action, payload],
            )

        def filter_value():
            return page.eval_on_selector("#filter", "el => el.value")

        def rows():
            return page.eval_on_selector_all("#root .row", "els => els.map(e => e.dataset.rowKey)")

        def highlighted():
            return sorted(page.eval_on_selector_all(
                "#root .row.highlighted", "els => els.map(e => e.dataset.rowKey)"))

        def chips():
            return page.eval_on_selector_all("#entity-readout .chip",
                                             "els => els.map(e => e.textContent.trim())")

        deliver("data", SKETCH_ONE)
        check("every row renders", rows(), ["c1", "c2"])

        # Selecting one entity on the canvas fills the filter box for you (#22).
        deliver("selectionResult", {"tokens": ["l1"], "prefix": "Selected:"})
        check("one selection auto-filters", filter_value(), "Line 1")
        check("the list narrows to it", rows(), ["c1"])
        check("the readout shows its chip", chips(), ["Line 1"])

        # ...and takes it back when the selection moves on. Without this the
        # list stayed narrowed to an entity that was no longer selected, and
        # rows it had highlighted were filtered out of the DOM entirely.
        deliver("selectionResult", {"tokens": [], "prefix": "Selected:"})
        check("deselecting clears the auto-filter", filter_value(), "")
        check("every row comes back", rows(), ["c1", "c2"])

        deliver("selectionResult", {"tokens": ["l1"], "prefix": "Selected:"})
        deliver("selectionResult", {"tokens": ["l1", "l3"], "prefix": "Selected:"})
        check("selecting several clears the auto-filter", filter_value(), "")
        check("both their rows highlight", highlighted(), ["c1", "c2"])

        # A filter someone typed is theirs; no selection change may discard it.
        page.fill("#filter", "tangent")
        deliver("selectionResult", {"tokens": [], "prefix": "Selected:"})
        check("a typed filter survives deselection", filter_value(), "tangent")
        check("and is still applied", rows(), ["c2"])
        deliver("selectionResult", {"tokens": ["l1", "l3"], "prefix": "Selected:"})
        check("a typed filter survives a multi-selection", filter_value(), "tangent")
        deliver("selectionResult", {"tokens": ["l1"], "prefix": "Selected:"})
        check("but one selection still wins over it", filter_value(), "Line 1")

        # Moving to another sketch retires an auto-filter naming the old one's
        # geometry; a rescan of the same sketch must leave it alone.
        deliver("data", SKETCH_TWO)
        check("switching sketch clears the auto-filter", filter_value(), "")
        check("the new snapshot renders", rows(), ["c9"])
        deliver("selectionResult", {"tokens": ["z9"], "prefix": "Selected:"})
        deliver("data", SKETCH_TWO)
        check("a rescan of the same sketch keeps it", filter_value(), "Circle 9")
        page.fill("#filter", "equal")
        deliver("data", SKETCH_ONE)
        check("a typed filter survives a sketch change", filter_value(), "equal")

        # The token index is memoized per snapshot, so it has to be dropped
        # with the snapshot.
        deliver("data", SKETCH_TWO)
        deliver("selectionResult", {"tokens": ["z9"], "prefix": "Selected:"})
        check("the token index is rebuilt for a new snapshot", filter_value(), "Circle 9")
        deliver("selectionResult", {"tokens": ["l1"], "prefix": "Selected:"})
        check("a token from the old snapshot no longer resolves",
              page.eval_on_selector("#entity-readout", "el => el.textContent.trim()"),
              "Selected entity not in any row.")

        page.fill("#filter", "parallel")
        page.click("#filter-clear")
        check("the clear button clears a typed filter", filter_value(), "")

        # The help sheet's four dismiss paths (v1.6.3).
        def help_open():
            return page.eval_on_selector("#help-overlay", "el => el.className !== 'hidden'")

        page.click("#help-toggle")
        check("? opens the help sheet", help_open(), True)
        page.click("#help-close")
        check("its ✕ closes it", help_open(), False)
        page.click("#help-toggle")
        page.keyboard.press("Escape")
        check("Esc closes it", help_open(), False)
        page.click("#help-toggle")
        page.mouse.click(5, 5)   # the backdrop strip left over the name bar
        check("the backdrop closes it", help_open(), False)

        browser.close()

    if check.failed:
        print("\nFAILED: " + ", ".join(check.failed))
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
