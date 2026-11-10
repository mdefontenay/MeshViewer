"""The Formulas window: the equations a section uses, typeset."""
from __future__ import annotations

import re

from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPalette, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

# ---------------------------------------------------------------------------
# "Formulas" — a window in the middle of the app with the equations
# ---------------------------------------------------------------------------

def render_tex(tex, color="#000000", size=17):
    """LaTeX-like formula -> QPixmap (matplotlib's mathtext: no TeX install needed),
    or None when matplotlib is not there."""
    try:
        import io

        import matplotlib
        from matplotlib import mathtext
        from matplotlib.font_manager import FontProperties
    except ImportError:
        return None
    try:
        with matplotlib.rc_context({"mathtext.fontset": "cm",      # Computer Modern
                                    "savefig.transparent": True}):
            buf = io.BytesIO()
            tex = tex.replace(r"\frac", r"\dfrac")              # full-size fractions
            mathtext.math_to_image(f"${tex}$", buf, prop=FontProperties(size=size), dpi=144,
                                   format="png", color=color)
    except Exception:                                           # noqa: BLE001
        return None
    pm = QPixmap()
    pm.loadFromData(buf.getvalue(), "PNG")
    pm.setDevicePixelRatio(2)
    return pm


def _plain(tex):
    """Readable fallback for a formula without matplotlib."""
    t = tex
    for a, b in ((r"\frac", ""), (r"\sqrt", "√"), (r"\left", ""), (r"\right", ""),
                 (r"\rho", "ρ"), (r"\mu", "μ"), (r"\nu", "ν"), (r"\tau", "τ"),
                 (r"\gamma", "γ"), (r"\delta", "δ"), (r"\cdot", "·"), (r"\,", " "),
                 (r"\max", "max"), (r"\min", "min"), (r"\log", "log"), (r"\times", "×"),
                 (r"\mathrm", ""), ("{", "("), ("}", ")"), ("\\", "")):
        t = re.sub(a, b, t)
    return t


class FormulasDialog(QFrame):
    """A card next to the "Formulas" link that opened it: title, then for each formula a
    short explanation and the formula. Items: a sub-title string, (explanation, LaTeX),
    (explanation, LaTeX, url) — the formula links to the url — or ("link", text, url).
    Click outside or press Esc to close."""

    def __init__(self, title, items, parent):
        super().__init__(parent.window(), Qt.Popup | Qt.FramelessWindowHint |
                         Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QFrame()
        body.setObjectName("ValuesBody")
        outer.addWidget(body)
        bl = QVBoxLayout(body)
        bl.setContentsMargins(2, 2, 2, 2)
        scroll = QScrollArea()                     # scrolls when the window is small
        scroll.setObjectName("FormulasScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        bl.addWidget(scroll)
        inner = QWidget()
        inner.setObjectName("FormulasInner")
        scroll.setWidget(inner)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(20, 14, 20, 16)
        lay.setSpacing(4)
        inner.setMinimumWidth(500)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        lay.addWidget(t)
        color = self.palette().color(QPalette.WindowText).name()
        for item in items:
            if isinstance(item, str):                    # a sub-title
                lab = QLabel(item)
                lab.setObjectName("Caption")
                lab.setContentsMargins(0, 10, 0, 0)
                lay.addWidget(lab)
                continue
            if item[0] == "link":                        # ("link", text, url)
                _, text, url = item
                b = QPushButton(text)
                b.setObjectName("LinkButton")
                b.setFlat(True)
                b.setCursor(Qt.PointingHandCursor)
                b.setToolTip(url)
                b.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
                lay.addSpacing(8)
                lay.addWidget(b, 0, Qt.AlignLeft)
                continue
            text, tex = item[0], item[1]
            url = item[2] if len(item) > 2 else None
            lab = QLabel(text)
            lab.setObjectName("InfoLine")
            lab.setWordWrap(True)
            lab.setContentsMargins(0, 6, 0, 0)
            lay.addWidget(lab)
            if tex:
                f = QLabel()
                pm = render_tex(tex, color)
                if pm is None:
                    f.setText(_plain(tex))
                else:
                    f.setPixmap(pm)
                f.setContentsMargins(12, 0, 0, 0)
                if url:                                  # the formula is a link
                    f.setCursor(Qt.PointingHandCursor)
                    f.setToolTip(f"Open {url}")
                    f.mousePressEvent = lambda _e, u=url: QDesktopServices.openUrl(QUrl(u))
                lay.addWidget(f)
        win = parent.window().geometry()
        width = max(inner.sizeHint().width(), 500) + 24        # + room for the scroll bar
        inner.setFixedWidth(width - 24)
        h = min(inner.heightForWidth(width - 24) if inner.hasHeightForWidth()
                else inner.sizeHint().height(), win.height() - 60) + 8
        self.resize(width, h)
        scroll.setFixedHeight(h - 4)
        # next to the link that opened it (just left of the inspector), inside the window
        at = parent.mapToGlobal(QPoint(0, 0))
        side = parent.window().findChild(QWidget, "Inspector")
        x = (side.mapToGlobal(QPoint(0, 0)).x() - self.width() - 8) if side is not None \
            else at.x() - self.width() - 8
        x = min(x, win.right() - self.width() - 8)
        y = min(max(at.y() - 12, win.top() + 40), win.bottom() - self.height() - 8)
        self.move(max(x, win.left() + 8), max(y, win.top() + 8))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)


class FormulasButton(QPushButton):
    """Small "Formulas" link; `items` is a list (or a function returning one) of
    sub-title strings and (explanation, LaTeX formula) pairs."""

    def __init__(self, title, items, text="Formulas", parent=None):
        super().__init__(text, parent)
        self.setObjectName("LinkButton")
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("The formulas used here")
        self._title = title
        self._items = items
        self.dialog = None
        self.clicked.connect(self.open)

    def open(self):
        items = self._items() if callable(self._items) else self._items
        self.dialog = FormulasDialog(self._title, items, self)
        self.dialog.show()
