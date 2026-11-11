"""Check that global hotkeys work on this Mac, with no call app and no API key.

    uv run python scripts/check_hotkeys.py

Click another app (Zoom, a browser, anything), then press Option+Space and Option+K. Each press prints a line
here. Ctrl+C stops it. Needs a Mac; elsewhere it says so and exits.
"""

import sys

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from copilot.hotkeys import HotKeyError, HotKeys


class Bridge(QObject):
    pressed = Signal(str)


def main() -> int:
    app = QApplication(sys.argv)
    bridge = Bridge()
    bridge.pressed.connect(lambda name: print(f"pressed: {name}", flush=True))
    keys = HotKeys(bridge.pressed.emit)
    if not keys.available:
        print("global hotkeys need macOS")
        return 1
    for name, combo in (("ask", "option+space"), ("clear", "option+k")):
        try:
            keys.register(name, combo)
            print(f"registered {combo} as {name}")
        except HotKeyError as error:
            print(f"failed: {error}")
    print("now press the keys while another app is in front (Ctrl+C to stop)")
    QTimer(app, interval=500, timeout=lambda: None).start()  # lets Python see Ctrl+C
    app.aboutToQuit.connect(keys.unregister_all)
    try:
        app.exec()
    except KeyboardInterrupt:
        keys.unregister_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
