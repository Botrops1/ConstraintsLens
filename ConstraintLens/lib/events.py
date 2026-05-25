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

    Use this from any module that creates its own event handlers (e.g.
    CommandCreated). Without pinning, Python GC can drop the handler ref
    while the C++ side still holds a pointer — Fusion crashes silently
    on the next callback (landmine M-7).
    """
    event.add(handler)
    _handlers.append(handler)
    _subscriptions.append((event, handler))


def register_app(app: adsk.core.Application, ui: adsk.core.UserInterface, on_change) -> None:
    h1 = _DocumentActivatedHandler(on_change)
    app.documentActivated.add(h1)
    _handlers.append(h1)
    _subscriptions.append((app.documentActivated, h1))

    h2 = _CommandTerminatedHandler(on_change)
    ui.commandTerminated.add(h2)
    _handlers.append(h2)
    _subscriptions.append((ui.commandTerminated, h2))


def register_selection_changed(ui: adsk.core.UserInterface, on_change) -> bool:
    """Subscribe to ui.activeSelectionChanged. Returns True if subscribed."""
    event = getattr(ui, "activeSelectionChanged", None)
    if event is None:
        return False
    try:
        handler = _ActiveSelectionChangedHandler(on_change)
        event.add(handler)
        _handlers.append(handler)
        _subscriptions.append((event, handler))
        return True
    except Exception:
        return False


def register_palette(
    palette: adsk.core.Palette,
    on_message,
    on_closed,
) -> None:
    h_in = _PaletteIncomingHandler(on_message)
    palette.incomingFromHTML.add(h_in)
    _handlers.append(h_in)
    _subscriptions.append((palette.incomingFromHTML, h_in))

    h_closed = _PaletteClosedHandler(on_closed)
    palette.closed.add(h_closed)
    _handlers.append(h_closed)
    _subscriptions.append((palette.closed, h_closed))


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
