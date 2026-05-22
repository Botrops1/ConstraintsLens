# lib/selection.py — viewport selection helpers (SPEC.md section 4).

import adsk.core


def select_entities(ui: adsk.core.UserInterface, entities: list) -> None:
    """Replace the viewport selection with the given entities."""
    sel = ui.activeSelections
    sel.clear()
    for ent in entities:
        if ent is None:
            continue
        try:
            sel.add(ent)
        except Exception:
            # Individual add failures shouldn't abort the whole selection.
            pass


def select_constraint(ui: adsk.core.UserInterface, constraint) -> None:
    """Select the constraint object itself (Delete-key affordance)."""
    sel = ui.activeSelections
    sel.clear()
    if constraint is None:
        return
    try:
        sel.add(constraint)
    except Exception:
        pass
