"""Check that Murmury's window stays out of screen capture, on this Windows PC, now.

    uv run --with pillow python scripts/check_hidden_windows.py

Shows two boxes for a few seconds: magenta, set up like Murmury's floating window (frameless, always on top,
tool window, translucent background), and green, an ordinary window. Captures the screen with a GDI screenshot
(Pillow's ImageGrab) twice: first with the magenta box's hiding switched off, where it must show up (so the
test can see it), then switched on through configure_native_window(), where it must be gone. The green box
must be in every capture (so the capture itself works). Zoom, Teams and Meet may capture another way, so also
try a real screen share. Nothing is saved.
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
from PIL import ImageGrab
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QWidget

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from copilot.app import configure_native_window  # noqa: E402


class Box(QWidget):
    def __init__(self, colour: str, x: int, translucent: bool):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        if translucent:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._colour = QColor(colour)
        self.setGeometry(x, 250, 360, 260)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._colour)
        painter.end()


def count(image, rgb: tuple[int, int, int]) -> int:
    a = np.asarray(image.convert("RGB")).astype(int)
    return int(np.all(np.abs(a - np.array(rgb)) < 25, axis=-1).sum())


def settle(app: QApplication) -> None:
    for _ in range(30):
        app.processEvents()
        time.sleep(0.03)


def main() -> int:
    if sys.platform != "win32":
        print("This check is for Windows. On a Mac, run scripts/check_hidden.py.")
        return 2
    parser = argparse.ArgumentParser(description="Check that the window is hidden from screen capture.")
    parser.add_argument("--hold", type=int, default=0, metavar="SECONDS",
                        help="keep both boxes on screen, hiding on, for a real screen share")
    args = parser.parse_args()
    app = QApplication([])
    magenta = Box("#ff00ff", 260, translucent=True)
    green = Box("#00ff00", 700, translucent=False)
    for box in (magenta, green):
        box.show()
    app.processEvents()
    print("Windows", sys.getwindowsversion())
    configure_native_window(magenta, hide_from_capture=False)
    settle(app)
    shots = {False: ImageGrab.grab(all_screens=True)}  # the test must see the magenta box here
    returned = configure_native_window(magenta, hide_from_capture=True)  # the only change: the hiding switched on
    settle(app)
    shots[True] = ImageGrab.grab(all_screens=True)
    if args.hold:
        print(f"\nHolding both boxes for {args.hold} s, hiding on. Start your screen share now: the other "
              "side should see the green box and not the magenta one.")
        end = time.time() + args.hold
        while time.time() < end:
            app.processEvents()
            time.sleep(0.03)
    for box in (magenta, green):
        box.close()
    app.processEvents()
    ok = bool(returned)
    print()
    print(f"configure_native_window(hide_from_capture=True) returned {returned}")
    for hidden, image in shots.items():
        print("Hiding on (must be 0 px):" if hidden else "Hiding off (must show up, or the test can't see it):")
        box_px, control_px = count(image, (255, 0, 255)), count(image, (0, 255, 0))
        passed = control_px > 0 and (box_px == 0 if hidden else box_px > 0)
        ok &= passed
        print(f"  {'PASS' if passed else 'FAIL'}  GDI screenshot (Pillow ImageGrab): "
              f"Murmury-style window {box_px} px, ordinary window {control_px} px")
    print()
    print("Hidden from the GDI screenshot. Now try a real screen share." if ok
          else "NOT proven hidden: do not rely on it.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
