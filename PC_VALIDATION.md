# PC validation checklist

Step-by-step list of what to do when you sit down at the Fusion-equipped PC for the first time. Designed to take roughly 15-20 minutes if everything works first try.

Each step has a **pass** criterion and a **failure → action** path. Paste the spike-probe output and any failures back here.

---

## 0. Prerequisites

- [ ] Fusion 360 installed and updated to the **January 2026 release or later** (Python 3.14, Qt Web Browser backend).
- [ ] This repository cloned locally. The branch `claude/fusion-constraintlens-spec-94gPu` is the latest spec + scaffold.

---

## 1. Install the add-in

- [ ] Copy or symlink the `ConstraintLens/` directory into the Fusion add-ins folder:
  - **Windows**: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\ConstraintLens\`
  - **macOS**: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/ConstraintLens/`
- [ ] In Fusion: **Tools → Scripts and Add-Ins → Add-Ins** tab. **ConstraintLens** should appear in the list.
- [ ] Select it and click **Run**.

**Pass**: no error dialog.
**Failure → action**: paste the dialog message back. Most likely cause is a missing/malformed `ConstraintLens.manifest`.

---

## 2. Run the spike probe (highest value step)

The probe answers all five open questions in `SPEC.md` §10 in one shot.

- [ ] Open any Fusion design (or create a new empty document).
- [ ] **Tools → Scripts and Add-Ins → Scripts** tab → **+** → point at the **folder** `tests/fixture_sketch/` → **Run**. A message box confirms the fixture was created with 4 constraints + 2 dimensions. *(Fusion requires the script to live inside a folder with the same name — `fixture_sketch/fixture_sketch.py`.)*
- [ ] **Double-click** the new `ConstraintLens_Fixture` sketch in the browser to enter sketch edit.
- [ ] Back to Scripts tab → **+** → point at the **folder** `tests/spike_probe/` → **Run**.
- [ ] The probe writes `constraintlens_probe.txt` to the OS temp directory and previews the first 1500 chars in a message box. **Open the temp file and paste its full contents back into chat.**

**Pass**: temp file exists, probe completes without a Python traceback.
**Failure → action**: paste the traceback.

What the probe answers, mapped back to `SPEC.md` open questions:

| Probe section | SPEC §10 question | What I'm looking for |
|---|---|---|
| Q1 Panel ids | Q1 Panel id for the toolbar button | Whether `SketchInspectPanel` (or similar) exists when the active workspace is the sketch context; if so, I'll relocate the button. |
| Q2 ShowUnderconstrained | Q2 Text-command precondition | Whether `executeTextCommand("Sketch.ShowUnderconstrained")` returns text outside sketch edit, raises, or returns empty. |
| Q3 Palette events (static introspection) | Q3 Visibility refresh strategy | Confirms the event surface; the manual minimize/restore test in step 5 confirms behavior. |
| Q4 Token capture | Q4 entityToken stability across save-reload | The probe captures one token. After step 5 you'll save+reload and re-resolve to confirm. |
| Q5 Constraint inventory | Q5 VerticalConstraint enumeration | The probe lists `distinct objectTypes` — confirms whether `"adsk::fusion::VerticalConstraint"` appears. |

---

## 3. Smoke-test the add-in against the fixture

- [ ] Confirm the **Constraint Lens** button appears somewhere in the toolbar (current best-guess: **Solid → Tools → Scripts and Add-Ins** panel). If you don't see it, the probe's Q1 output will tell us the right panel id.
- [ ] With `ConstraintLens_Fixture` open for edit, click **Constraint Lens**.

**Pass criteria** — the docked panel on the right should show:
- Status banner: `ConstraintLens_Fixture · <component name> — under-constrained` (orange) or `fully constrained` (green) depending on whether the fixture is fully constrained as designed.
- **Geometric constraints (4)** section with: Horizontal, Vertical, Parallel, Tangent rows.
- **Dimensions (2)** section with: Linear and Diameter rows.
- **Endpoint joins (4)** section with one row per rectangle corner (each labeled "Endpoint join — Point N connects Line A, Line B"), each with the **implicit** badge.

**Failure → action**: screenshot the panel + paste the contents of Fusion's **Text Commands** window (`File → View → Show Text Commands`).

---

## 4. Smoke-test the interactions

- [ ] **Click a constraint row** — the referenced geometry should highlight (turn blue) in the viewport.
- [ ] **Click the ⌖ button** on a constraint row — selects the constraint object itself (so you can use Fusion's Delete key).
- [ ] **Click the × button** on a row — the constraint should disappear and the list should refresh automatically. A toast appears at the bottom of the panel.
- [ ] Try the × on an implicit-join row — the button should be disabled (these aren't real constraints; you cannot delete them).
- [ ] Click **Refresh** in the toolbar — manual re-scan; should be a no-op if nothing changed.

**Failure → action**: note exactly which interaction misbehaves.

---

## 5. Exercise the landmine guards

- [ ] **Scripts tab → + → `tests/fixture_midpoint/`** → **Run**. It creates `ConstraintLens_Midpoint_M1` with two midpoint constraints sharing the same sketch point — the canonical M-1 trigger configuration.
- [ ] Open that sketch for edit. The panel should show two MidPoint rows. **If one of them carries an `accessor` badge with an error message, M-1 is real and the defensive guard worked.** If not, M-1 doesn't trigger via this configuration on the January 2026 build — note that finding.
- [ ] **Test palette visibility (Q3)** — close the panel via its X button, then click **Constraint Lens** in the toolbar again. The panel should reopen with the current sketch data.
- [ ] **Test entityToken stability (Q4)** — from the spike probe output, copy the captured `entityToken`. Save the document. Close the document tab; reopen it. Open Fusion's **Text Commands** window and run:
  ```
  > Python: adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct).findEntityByToken('<paste-token>')
  ```
  Pass if it returns a non-empty list with a `MidPointConstraint`-or-similar object. Fail if it returns empty.

---

## 6. What to paste back

When you have time, paste back:

1. The full contents of `%TEMP%\constraintlens_probe.txt` (Windows) or `/tmp/constraintlens_probe.txt` (macOS).
2. The result of the entityToken save-reload test (step 5 last item).
3. Any unexpected error dialog text or behavior from steps 1, 3, 4.
4. Optionally: a screenshot of the panel against the fixture sketch.

I'll fold the findings into a single corrective commit (most likely a panel-id swap and any small adjustments revealed by the probe).
