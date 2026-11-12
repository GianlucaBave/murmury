import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QEnterEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from copilot.chrome import D, GAP, TrafficLights


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def lights(application):
    widget = TrafficLights()
    yield widget
    widget.close()
    widget.deleteLater()
    application.processEvents()


def clicks_at(widget, x):
    fired = []
    widget.close_clicked.connect(lambda: fired.append("close"))
    widget.minimize_clicked.connect(lambda: fired.append("minimize"))
    widget.zoom_clicked.connect(lambda: fired.append("zoom"))
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton, pos=QPoint(int(x), 1 + D // 2))
    return fired


@pytest.mark.parametrize("index,name", list(enumerate(("close", "minimize", "zoom"))))
def test_circle_centres_emit_only_their_own_signal(lights, index, name):
    x = 1 + index * (D + GAP) + D // 2
    assert clicks_at(lights, x) == [name]


@pytest.mark.parametrize("gap", [0, 1])
@pytest.mark.parametrize("fraction,side", [(0.25, 0), (0.75, 1)])
def test_gap_clicks_go_to_the_nearer_circle(lights, gap, fraction, side):
    x = 1 + gap * (D + GAP) + D + fraction * GAP
    assert clicks_at(lights, x) == [("close", "minimize", "zoom")[gap + side]]


@pytest.mark.parametrize("gap", [0, 1])
def test_exact_gap_midpoint_belongs_to_the_left_circle(lights, gap):
    x = 1 + gap * (D + GAP) + D + GAP / 2
    assert clicks_at(lights, x) == [("close", "minimize")[gap]]


def test_past_the_last_circle_has_no_hit(lights):
    assert lights._which(60) is None


def test_enter_and_leave_change_hover_state(application, lights):
    application.sendEvent(lights, QEvent(QEvent.Type.Leave))
    assert lights.hovered is False
    position = QPointF(1 + D / 2, 1 + D / 2)
    application.sendEvent(lights, QEnterEvent(position, position, position))
    assert lights.hovered is True
    application.sendEvent(lights, QEvent(QEvent.Type.Leave))
    assert lights.hovered is False


def test_fixed_size_matches_the_three_circles_and_gaps(lights):
    assert lights.width() == 3 * D + 2 * GAP + 2
    assert lights.height() == D + 2
    assert lights.minimumSize() == lights.maximumSize() == lights.size()
