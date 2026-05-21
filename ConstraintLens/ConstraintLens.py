# ConstraintLens — Fusion 360 add-in entry point (see SPEC.md section 4).
#
# Owns only run(context) / stop(context). All logic lives under ./lib.

import os
import sys
import traceback

import adsk.core

_ADDIN_DIR = os.path.dirname(os.path.realpath(__file__))
if _ADDIN_DIR not in sys.path:
    sys.path.insert(0, _ADDIN_DIR)

from lib import lifecycle  # noqa: E402


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
