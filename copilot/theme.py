"""Light and dark palettes (Apple's system greys, Murmury's green), following the Mac's appearance.

Style sheets are written with $tokens and filled from the palette in use; `watch` re-applies them when the
appearance changes while the app is open.
"""

from __future__ import annotations

from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

LIGHT = {
    # text
    "text": "#1d1d1f", "secondary": "#6e6e73", "tertiary": "#86868b", "faint": "#aeaeb2",
    # surfaces
    "panel": "#ffffff", "panel_border": "rgba(0,0,0,30)", "glass": "rgba(255,255,255,244)",
    "group": "#f5f5f7", "group_border": "rgba(0,0,0,13)", "rule": "rgba(0,0,0,18)",
    "drop": "#fafafa", "drop_border": "rgba(0,0,0,50)", "drop_hover": "#f2faf5",
    "card": "#f5f5f7", "card_border": "rgba(0,0,0,13)", "quote_bar": "rgba(0,0,0,40)",
    "input": "#ffffff", "input_border": "rgba(0,0,0,35)",
    # controls
    "accent": "#1fa463", "accent_hover": "#22b46d", "link": "#168a52", "link_hover": "#0f6b3e",
    "button": "#ffffff", "button_border": "rgba(0,0,0,40)", "button_hover": "#f5f5f7",
    "disabled_bg": "#e5e5ea", "disabled_fg": "#aeaeb2", "segbar": "#e3e3e8", "seg_on": "#ffffff",
    "seg_on_border": "rgba(0,0,0,22)", "switch_off": "#e3e3e8", "danger": "#d64545",
    # answers
    "tag_fg": "#137a48", "tag_bg": "#e3f4ea",
}

DARK = {
    "text": "#f5f5f7", "secondary": "#a1a1a6", "tertiary": "#8e8e93", "faint": "#636366",
    "panel": "#1e1e20", "panel_border": "rgba(255,255,255,26)", "glass": "rgba(30,30,32,242)",
    "group": "#2c2c2e", "group_border": "rgba(255,255,255,14)", "rule": "rgba(255,255,255,20)",
    "drop": "#232325", "drop_border": "rgba(255,255,255,55)", "drop_hover": "#1d2b23",
    "card": "#2c2c2e", "card_border": "rgba(255,255,255,14)", "quote_bar": "rgba(255,255,255,45)",
    "input": "#2c2c2e", "input_border": "rgba(255,255,255,40)",
    "accent": "#2bb673", "accent_hover": "#34c97f", "link": "#4cd38c", "link_hover": "#7ee2ad",
    "button": "#3a3a3c", "button_border": "rgba(255,255,255,30)", "button_hover": "#48484a",
    "disabled_bg": "#3a3a3c", "disabled_fg": "#6e6e73", "segbar": "#3a3a3c", "seg_on": "#636366",
    "seg_on_border": "rgba(255,255,255,20)", "switch_off": "#48484a", "danger": "#ff6961",
    "tag_fg": "#7ee2ad", "tag_bg": "#1d3a2a",
}


def is_dark() -> bool:
    app = QGuiApplication.instance()
    return bool(app) and app.styleHints().colorScheme() == Qt.ColorScheme.Dark


def palette() -> dict:
    return DARK if is_dark() else LIGHT


def fill(style: str) -> str:
    return Template(style).substitute(palette())


def apply_saved() -> None:
    """At start: the appearance chosen with the sun/moon button, if any; otherwise the Mac's."""
    from .setup import settings_store  # inside the function: setup.py imports theme
    saved = settings_store().value("appearance", "")
    if saved in ("light", "dark"):
        set_dark(saved == "dark", remember=False)


def set_dark(dark: bool, remember: bool = True) -> None:
    app = QGuiApplication.instance()
    if not app:
        return
    try:  # macOS draws native controls with the app's appearance, which Qt's colour scheme does not change
        from AppKit import NSAppearance, NSApplication
        name = "NSAppearanceNameDarkAqua" if dark else "NSAppearanceNameAqua"
        NSApplication.sharedApplication().setAppearance_(NSAppearance.appearanceNamed_(name))
    except Exception:
        pass
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark if dark else Qt.ColorScheme.Light)
    if remember:
        from .setup import settings_store
        settings_store().setValue("appearance", "dark" if dark else "light")


def toggle() -> None:
    set_dark(not is_dark())


def refresh_native(root) -> None:
    """Native macOS controls keep drawing with the appearance they were created in: re-polish them."""
    from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QLineEdit
    for kind in (QComboBox, QAbstractSpinBox, QLineEdit):
        for widget in root.findChildren(kind):
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)
            widget.update()


def watch(callback) -> None:
    """Call `callback` when the Mac switches between light and dark."""
    app = QGuiApplication.instance()
    if app:
        app.styleHints().colorSchemeChanged.connect(lambda _: callback())
