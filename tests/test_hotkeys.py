import pytest

from copilot import hotkeys
from copilot.hotkeys import EVENT_HOT_KEY_EXISTS_ERR, HotKeyError, HotKeys, parse_combo


class FakeBackend:
    """Stands in for Carbon, so these tests run on any OS."""

    def __init__(self, register_status=0, install_status=0):
        self.register_status, self.install_status = register_status, install_status
        self.registered, self.removed, self.unregistered = {}, False, []
        self.on_pressed = None

    def install(self, on_pressed):
        self.on_pressed = on_pressed
        return self.install_status

    def register(self, hotkey_id, key_code, modifiers):
        if self.register_status == 0:
            self.registered[hotkey_id] = (key_code, modifiers)
        return self.register_status

    def unregister(self, hotkey_id):
        self.unregistered.append(hotkey_id)

    def remove(self):
        self.removed = True


def test_parse_combo_option_space_and_option_k():
    assert parse_combo("option+space") == (49, 0x0800)
    assert parse_combo("Alt+K") == (40, 0x0800)
    assert parse_combo("cmd+shift+k") == (40, 0x0100 | 0x0200)


@pytest.mark.parametrize("text", ["space", "option+", "option+nothing", "hyper+k", ""])
def test_parse_combo_rejects_bad_combinations(text):
    with pytest.raises(ValueError):
        parse_combo(text)


def test_register_success_sends_key_code_and_modifier():
    backend = FakeBackend()
    keys = HotKeys(lambda name: None, backend=backend)
    keys.register("ask", "option+space")
    assert list(backend.registered.values()) == [(49, 0x0800)]


def test_registration_fails_when_the_combination_is_taken():
    keys = HotKeys(lambda name: None, backend=FakeBackend(register_status=EVENT_HOT_KEY_EXISTS_ERR))
    with pytest.raises(HotKeyError, match="already used by another app"):
        keys.register("ask", "option+space")
    assert keys.names == {}


def test_registration_fails_for_another_reason_with_a_readable_message():
    keys = HotKeys(lambda name: None, backend=FakeBackend(register_status=-50))
    with pytest.raises(HotKeyError, match="error -50"):
        keys.register("clear", "option+k")


def test_handler_install_failure_is_reported():
    keys = HotKeys(lambda name: None, backend=FakeBackend(install_status=-1))
    with pytest.raises(HotKeyError, match="could not start listening"):
        keys.register("ask", "option+space")


def test_bad_combination_is_a_hotkey_error():
    keys = HotKeys(lambda name: None, backend=FakeBackend())
    with pytest.raises(HotKeyError, match="unknown key"):
        keys.register("ask", "option+nothing")


def test_press_reaches_the_callback_with_the_right_name():
    pressed, backend = [], FakeBackend()
    keys = HotKeys(pressed.append, backend=backend)
    keys.register("ask", "option+space")
    keys.register("clear", "option+k")
    backend.on_pressed(2)
    backend.on_pressed(1)
    backend.on_pressed(99)  # not ours: ignored
    assert pressed == ["clear", "ask"]


def test_unregister_all_releases_every_hotkey_and_the_handler():
    backend = FakeBackend()
    keys = HotKeys(lambda name: None, backend=backend)
    keys.register("ask", "option+space")
    keys.register("clear", "option+k")
    keys.unregister_all()
    assert sorted(backend.unregistered) == [1, 2]
    assert backend.removed and keys.names == {}


def test_no_op_off_macos(monkeypatch):
    monkeypatch.setattr(hotkeys.sys, "platform", "win32")
    keys = HotKeys(lambda name: None)
    assert not keys.available
    keys.unregister_all()  # does nothing, does not raise
    with pytest.raises(HotKeyError, match="macOS"):
        keys.register("ask", "option+space")


def test_falls_back_when_carbon_cannot_load(monkeypatch):
    def broken():
        raise OSError("no Carbon")

    monkeypatch.setattr(hotkeys, "CarbonBackend", broken)
    keys = HotKeys(lambda name: None, platform="darwin")
    assert not keys.available


def test_native_call_that_raises_becomes_a_hotkey_error():
    class Crashing(FakeBackend):
        def register(self, hotkey_id, key_code, modifiers):
            raise OSError("boom")

    with pytest.raises(HotKeyError, match="could not register"):
        HotKeys(lambda name: None, backend=Crashing()).register("ask", "option+space")


def test_install_that_raises_becomes_a_hotkey_error():
    class Crashing(FakeBackend):
        def install(self, on_pressed):
            raise OSError("boom")

    with pytest.raises(HotKeyError, match="could not start listening"):
        HotKeys(lambda name: None, backend=Crashing()).register("ask", "option+space")


def test_macos_refusing_option_only_gets_a_clear_message():
    keys = HotKeys(lambda name: None, backend=FakeBackend(register_status=hotkeys.EVENT_INTERNAL_ERR))
    with pytest.raises(HotKeyError, match="only Option"):
        keys.register("ask", "option+space")
