# PyInstaller recipe for Murmury.app.   cd packaging && uv run pyinstaller murmury.spec --noconfirm
from PyInstaller.utils.hooks import collect_all

datas = [("../copilot/assets", "copilot/assets")]
binaries = [("../audiotap/audiotap", "audiotap")]
hiddenimports = ["copilot.claude_code", "copilot.setup", "keyring.backends.macOS", "copilot.providers",
                 "copilot.openai_copilot", "openai"]
for package in ("mlx", "mlx_whisper", "tiktoken", "tiktoken_ext"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(["murmury.py"], pathex=[".."], binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             # torch, numba, llvmlite, scipy: only for mlx-whisper's word timestamps and model conversion, never
             # used here (copilot/listen.py stands in for the timing module); about 570 MB.
             # PySide6.QtPdf and QtPdfWidgets stay: the source viewer (copilot/viewer.py) shows PDF pages with them
             excludes=["torch", "numba", "llvmlite", "scipy", "mlx_whisper.torch_whisper", "tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
                       "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Murmury", console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="Murmury", upx=False)
app = BUNDLE(
    coll, name="Murmury.app", icon="murmury.icns", bundle_identifier="dev.murmury.app",
    info_plist={
        "CFBundleShortVersionString": "0.1.5",
        "CFBundleVersion": "6",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": "Murmury listens to your microphone to tell your voice apart "
                                        "from the other people on the call. Nothing is recorded or saved.",
        "NSAppleEventsUsageDescription": "Murmury opens Terminal so you can sign in to Claude Code.",
    },
)
