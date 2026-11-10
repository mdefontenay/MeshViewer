"""Small things only macOS needs, through PyObjC (does nothing elsewhere).

    join_active_space(widget)   a window of the app's own (Settings, About) opens on the
                                Space you are in — also over a full-screen window —
                                instead of macOS switching to the desktop to show it
    increase_contrast()         System Settings ▸ Accessibility ▸ Increase contrast is on
"""
from __future__ import annotations

import sys

_MOVE_TO_ACTIVE_SPACE = 1 << 1           # NSWindowCollectionBehaviorMoveToActiveSpace
_FULL_SCREEN_AUXILIARY = 1 << 8          # NSWindowCollectionBehaviorFullScreenAuxiliary


def _ns_window(widget):
    import objc
    view = objc.objc_object(c_void_p=int(widget.winId()))
    return view.window()


def join_active_space(widget):
    if sys.platform != "darwin":
        return
    try:
        win = _ns_window(widget)
        if win is not None:
            behavior = win.collectionBehavior() & ~(1 << 7)   # not FullScreenPrimary
            win.setCollectionBehavior_(behavior | _MOVE_TO_ACTIVE_SPACE | _FULL_SCREEN_AUXILIARY)
    except Exception:                                     # noqa: BLE001 no PyObjC: as before
        pass


def increase_contrast():
    if sys.platform != "darwin":
        return False
    try:
        from AppKit import NSWorkspace
        return bool(NSWorkspace.sharedWorkspace().accessibilityDisplayShouldIncreaseContrast())
    except Exception:                                     # noqa: BLE001
        return False
