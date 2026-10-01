# ConstraintLens — Fusion 360 add-in entry point (see SPEC.md section 4).
#
# Owns only run(context) / stop(context). All logic lives under ./lib.
#
# Fusion loads each add-in folder as a package, so the import is relative. Fusion
# runs every add-in in one Python interpreter: an absolute `from lib import …`
# (with the folder added to sys.path) would share a module name with any other
# add-in that has a `lib` package, and whichever loaded first would win.

import os
import traceback

import adsk.core

from .lib import lifecycle

_ADDIN_DIR = os.path.dirname(os.path.realpath(__file__))


def run(context):
    try:
        lifecycle.start(_ADDIN_DIR)
    except Exception:
        ui = adsk.core.Application.get().userInterface
        if ui:
            ui.messageBox("ConstraintLens failed to start:\n" + traceback.format_exc())


def stop(context):
    try:
        lifecycle.stop()
    except Exception:
        ui = adsk.core.Application.get().userInterface
        if ui:
            ui.messageBox("ConstraintLens failed to stop cleanly:\n" + traceback.format_exc())
