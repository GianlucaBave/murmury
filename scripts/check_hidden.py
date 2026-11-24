"""Check that Murmury's window stays out of screen capture, on this Mac, now.

    uv run --with pillow python scripts/check_hidden.py

Shows three boxes for a few seconds: magenta, set up exactly like Murmury's floating window; cyan, Murmury's
source viewer made by the same make_viewer() the app uses (hidden before its first show); and green, an
ordinary window. Captures the screen three ways: ScreenCaptureKit (what Zoom, Meet and Teams use),
`screencapture` (macOS screenshots) and CGWindowListCreateImage (older capture). It does this twice:
first with hiding switched off, where magenta and cyan must show up (so the test can see them), then
switched on, where both must be gone. The green box must be in every capture (so the capture itself works).
Run it again after each macOS update. Nothing is saved outside a temporary folder.
"""
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from copilot.app import configure_native_window, make_viewer  # noqa: E402

HERE = Path(__file__).parent
VIEWER_STYLE = "#panel, QPlainTextEdit { background: #00ffff; border: none; }"  # one colour, so it can be counted


def count(path: Path, rgb: tuple[int, int, int]) -> int:
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    return int(np.all(np.abs(a - np.array(rgb)) < 25, axis=-1).sum())


def settle(app: QApplication) -> None:
    for _ in range(30):
        app.processEvents()
        time.sleep(0.03)


def viewer_box(hide: bool):
    """Murmury's source viewer made as app.main() makes it, set up before its first show, painted cyan."""
    viewer, _ = make_viewer(hide_from_capture=hide)
    viewer.setStyleSheet(VIEWER_STYLE)
    viewer.setGeometry(260, 560, 360, 260)
    viewer.stack.setCurrentWidget(viewer.text)
    viewer.show()  # not activated, like the other boxes: the check must not switch apps or Spaces while it captures
    return viewer


def capture(tool: Path, folder: Path) -> dict[str, Path]:
    folder.mkdir()
    shots = {"ScreenCaptureKit (Zoom, Meet, Teams)": folder / "sck.png",
             "screencapture (macOS screenshots)": folder / "screencapture.png"}
    subprocess.run([str(tool), str(shots["ScreenCaptureKit (Zoom, Meet, Teams)"])], capture_output=True, timeout=60)
    subprocess.run(["screencapture", "-x", str(shots["screencapture (macOS screenshots)"])], timeout=30)
    try:
        import Quartz
        img = Quartz.CGWindowListCreateImage(Quartz.CGRectInfinite, Quartz.kCGWindowListOptionOnScreenOnly,
                                             Quartz.kCGNullWindowID, Quartz.kCGWindowImageDefault)
        if img:
            path = folder / "cgwindowlist.png"
            url = Quartz.CFURLCreateWithFileSystemPath(None, str(path), Quartz.kCFURLPOSIXPathStyle, False)
            dest = Quartz.CGImageDestinationCreateWithURL(url, "public.png", 1, None)
            Quartz.CGImageDestinationAddImage(dest, img, None)
            Quartz.CGImageDestinationFinalize(dest)
            shots["CGWindowListCreateImage (older capture)"] = path
    except Exception:
        pass
    return shots


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="murmury-capture-"))
    tool = tmp / "sckshot"
    subprocess.run(["swiftc", "-O", str(HERE / "sckshot.swift"), "-o", str(tool), "-framework", "ScreenCaptureKit"],
                   check=True, capture_output=True)
    app = QApplication([])
    boxes = []
    for colour, x in (("#ff00ff", 260), ("#00ff00", 700)):
        w = QWidget()
        w.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        w.setStyleSheet(f"background:{colour};")
        w.setGeometry(x, 250, 360, 260)
        w.show()
        app.processEvents()
        configure_native_window(w, hide_from_capture=False)
        boxes.append(w)
    magenta = boxes[0]
    viewer = viewer_box(hide=False)
    settle(app)
    rounds = {False: capture(tool, tmp / "hiding-off")}  # the test must see the magenta box and the viewer here
    configure_native_window(magenta, hide_from_capture=True)  # Murmury's hiding switched on
    first, viewer = viewer, viewer_box(hide=True)  # a new viewer, hidden before it is ever shown, as app.main() does
    first.hide()
    settle(app)
    rounds[True] = capture(tool, tmp / "hiding-on")
    for w in boxes + [viewer]:
        w.close()
    app.processEvents()
    ok = True
    for hidden, shots in rounds.items():
        print("Hiding on (must be 0 px):" if hidden else "Hiding off (must show up, or the test can't see it):")
        for name, path in shots.items():
            if not path.exists():
                print(f"  {name}: no capture (screen recording permission?)")
                ok = False
                continue
            box, shown, control = count(path, (255, 0, 255)), count(path, (0, 255, 255)), count(path, (0, 255, 0))
            passed = control > 0 and ((box == 0 and shown == 0) if hidden else (box > 0 and shown > 0))
            ok &= passed
            print(f"  {'PASS' if passed else 'FAIL'}  {name}: Murmury-style window {box} px, "
                  f"source viewer {shown} px, ordinary window {control} px")
    print("\nHidden from every capture." if ok else "\nNOT proven hidden everywhere: do not rely on it.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
