# lib/events.py — GC-safe event handler registry (SPEC.md sections 4, 6, M-7).

import traceback

import adsk.core


# Module-level pinning lists — every handler instance and every event<->handler
# pair lives here for the lifetime of the add-in. Dropping these references
# crashes Fusion silently (landmine M-7).
_handlers: list[adsk.core.EventHandler] = []
_subscriptions: list[tuple[object, adsk.core.EventHandler]] = []


class _DocumentActivatedHandler(adsk.core.DocumentEventHandler):
    def __init__(self, on_change):
        super().__init__()
        self._on_change = on_change

    def notify(self, args):
        try:
            self._on_change()
        except Exception:
            _report(traceback.format_exc(), "documentActivated")


class _CommandTerminatedHandler(adsk.core.ApplicationCommandEventHandler):
    def __init__(self, on_change):
        super().__init__()
        self._on_change = on_change

    def notify(self, args):
        try:
            self._on_change()
        except Exception:
            # Never let a handler exception escape into Fusion.
            pass


class _PaletteIncomingHandler(adsk.core.HTMLEventHandler):
    def __init__(self, on_message):
        super().__init__()
        self._on_message = on_message

    def notify(self, args):
        try:
            self._on_message(args.action, args.data)
        except Exception:
            _report(traceback.format_exc(), "incomingFromHTML")


class _PaletteClosedHandler(adsk.core.UserInterfaceGeneralEventHandler):
    def __init__(self, on_closed):
        super().__init__()
        self._on_closed = on_closed

    def notify(self, args):
        try:
            self._on_closed()
        except Exception:
            pass


# Selection-changed handler base class isn't named identically across builds —
# fall back to UserInterfaceGeneralEventHandler if ActiveSelectionEventHandler
# isn't exposed in this Fusion's adsk.core.
_SELECTION_HANDLER_BASE = getattr(
    adsk.core,
    "ActiveSelectionEventHandler",
    adsk.core.UserInterfaceGeneralEventHandler,
)


class _ActiveSelectionChangedHandler(_SELECTION_HANDLER_BASE):
    def __init__(self, on_change):
        super().__init__()
        self._on_change = on_change

    def notify(self, args):
        try:
            self._on_change()
        except Exception:
            pass


def pin(event, handler: adsk.core.EventHandler) -> None:
    """Pin a handler to a Fusion event and keep its Python ref alive.

    The single place a handler is ever attached — every register_* function
    below goes through it too, so there is one implementation of the M-7 rule
    to get right. Without pinning, Python GC can drop the handler ref while the
    C++ side still holds a pointer, and Fusion crashes silently on the next
    callback.
    """
    event.add(handler)
    _handlers.append(handler)
    _subscriptions.append((event, handler))


def register_app(app: adsk.core.Application, ui: adsk.core.UserInterface, on_change) -> None:
    pin(app.documentActivated, _DocumentActivatedHandler(on_change))
    pin(ui.commandTerminated, _CommandTerminatedHandler(on_change))


def register_selection_changed(ui: adsk.core.UserInterface, on_change) -> bool:
    """Subscribe to ui.activeSelectionChanged. Returns True if subscribed."""
    event = getattr(ui, "activeSelectionChanged", None)
    if event is None:
        return False
    try:
        pin(event, _ActiveSelectionChangedHandler(on_change))
        return True
    except Exception:
        return False


def register_palette(
    palette: adsk.core.Palette,
    on_message,
    on_closed,
) -> None:
    pin(palette.incomingFromHTML, _PaletteIncomingHandler(on_message))
    pin(palette.closed, _PaletteClosedHandler(on_closed))


class _CustomEventHandler(adsk.core.CustomEventHandler):
    def __init__(self, on_fire):
        super().__init__()
        self._on_fire = on_fire

    def notify(self, args):
        try:
            self._on_fire()
        except Exception:
            # Deliberately silent, unlike the other handlers here: this one can
            # fire twice a second, and _report() would open a message box each
            # time and make Fusion unusable.
            pass


def register_custom_event(app: adsk.core.Application, event_id: str, on_fire):
    """Register a custom event and pin its handler (landmine M-7).

    Returns the CustomEvent, or None if registration failed. Fusion runs the
    handler on the main thread, which is what makes a custom event the only
    safe way for a worker thread to ask for API work.
    """
    try:
        # A stale registration survives a crashed or force-stopped add-in and
        # makes the next registerCustomEvent call fail.
        app.unregisterCustomEvent(event_id)
    except Exception:
        pass
    try:
        event = app.registerCustomEvent(event_id)
    except Exception:
        return None
    if event is None:
        return None
    pin(event, _CustomEventHandler(on_fire))
    return event


def unregister_all() -> None:
    for event, handler in _subscriptions:
        try:
            event.remove(handler)
        except Exception:
            pass
    _subscriptions.clear()
    _handlers.clear()


def _report(message: str, context: str) -> None:
    try:
        ui = adsk.core.Application.get().userInterface
        if ui:
            ui.messageBox(f"ConstraintLens handler error ({context}):\n{message}")
    except Exception:
        pass
