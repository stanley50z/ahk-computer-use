"""The input guard that holds every desktop test until the user has left the keyboard and mouse alone for 5 seconds."""

import ctypes
import time
from types import SimpleNamespace

import pytest

import input_guard
from conftest import pytest_runtest_setup, user32, wait_until
from input_guard import NOTICE_TITLE, InputListener, keyboard_and_mouse, show_notice, wait_for_quiet_input


class Notice:
    """A fake pop-up that remembers the tick it was shown at and whether it was closed."""

    def __init__(self, tick: int):
        self.shown_at, self.closed = tick, False

    def close(self) -> None:
        self.closed = True


class Desk:
    """A fake machine: a millisecond tick clock, the tick of the last input, and user input arriving at given ticks."""

    def __init__(self, now: int, last: int, inputs: tuple[int, ...] = ()):
        self.tick, self.last, self.inputs = now, last, sorted(inputs)
        self.lines: list[str] = []
        self.notices: list[Notice] = []

    def now(self) -> int:
        return self.tick

    def last_input(self) -> int:
        return self.last

    def sleep(self, seconds: float) -> None:
        end = self.tick + round(seconds * 1000)
        self.last = max([self.last, *(tick for tick in self.inputs if self.tick < tick <= end)])
        self.tick = end

    def show_notice(self) -> Notice:
        self.notices.append(Notice(self.tick))
        return self.notices[-1]

    def wait(self) -> None:
        wait_for_quiet_input(self.now, self.last_input, self.sleep, self.show_notice, self.lines.append)


@pytest.mark.parametrize('idle_ms', [5000, 60000])
def test_a_machine_idle_for_five_seconds_starts_the_test_at_once(idle_ms):
    desk = Desk(now=100000, last=100000 - idle_ms)
    desk.wait()
    assert desk.tick == 100000 and desk.lines == [] and desk.notices == []


@pytest.mark.parametrize('idle_ms', [0, 2000, 4999])
def test_input_from_before_the_wait_is_a_silent_wait_until_five_quiet_seconds(idle_ms):
    desk = Desk(now=100000, last=100000 - idle_ms)
    desk.wait()
    assert desk.tick - desk.last == 5000 and desk.last == 100000 - idle_ms
    assert len(desk.lines) == 1 and 'keyboard or mouse' in desk.lines[0]
    assert desk.notices == []


def test_input_during_the_wait_shows_one_notice_until_five_quiet_seconds_after_the_last_input():
    desk = Desk(now=100000, last=99000, inputs=(101000, 102500, 103000))
    desk.wait()
    assert desk.tick == 103000 + 5000, 'every input during the wait restarts the 5 seconds'
    notice, = desk.notices
    assert 101000 <= notice.shown_at < 101500, 'the notice appears soon after the input, not after the remaining wait'
    assert notice.closed
    assert len(desk.lines) == 1


# GetTickCount wraps after 49.7 days, so the last input's tick can be larger than the current one.
@pytest.mark.parametrize('idle_ms, end_tick, waited', [(2000, 4000, True), (7000, 1000, False)])
def test_the_tick_clock_wrapping_around_does_not_skip_or_stall_the_wait(idle_ms, end_tick, waited):
    desk = Desk(now=1000, last=2**32 + 1000 - idle_ms)
    desk.wait()
    assert desk.tick == end_tick and bool(desk.lines) is waited and desk.notices == []


def test_the_notice_closes_when_the_wait_is_interrupted():
    desk = Desk(now=100000, last=99000, inputs=(100100,))
    sleep = desk.sleep

    def interrupted(seconds):
        if desk.notices:
            raise KeyboardInterrupt
        sleep(seconds)
    desk.sleep = interrupted
    with pytest.raises(KeyboardInterrupt):
        desk.wait()
    assert desk.notices[0].closed


def test_the_listener_registers_the_mouse_and_keyboard_only_and_hears_them_in_the_background():
    # Usage page 1: usage 2 is the mouse, 6 the keyboard. A game controller (4, 5) or other HID device is not asked for.
    assert keyboard_and_mouse(42) == [(1, 2, 0x100, 42), (1, 6, 0x100, 42)]  # 0x100: RIDEV_INPUTSINK


def test_the_listener_counts_its_start_and_every_raw_input_message_as_input():
    clock = SimpleNamespace(tick=1000)
    listener = InputListener(lambda: clock.tick)
    assert listener.last_input() == 1000, 'Raw Input reports nothing from before the start, so the start counts'
    clock.tick = 2000
    listener.on_message(0x0113)  # WM_TIMER is not input
    assert listener.last_input() == 1000
    listener.on_message(0x00FF)  # WM_INPUT: a key or mouse event, a move or a wheel step, injected or not
    assert listener.last_input() == 2000


@pytest.mark.parametrize('started_ms_ago, end_tick', [(1000, 104000), (5000, 100000)])
def test_the_first_desktop_test_waits_silently_until_five_seconds_after_the_listener_started(started_ms_ago, end_tick):
    desk = Desk(now=100000 - started_ms_ago, last=0)
    listener = InputListener(desk.now)
    desk.tick = 100000
    wait_for_quiet_input(desk.now, listener.last_input, desk.sleep, desk.show_notice, desk.lines.append)
    assert desk.tick == end_tick and desk.notices == []


@pytest.mark.parametrize('desktop', [True, False])
def test_every_desktop_test_and_only_a_desktop_test_waits_for_quiet_input(monkeypatch, desktop):
    calls = []
    monkeypatch.setattr(input_guard, 'before_desktop_test', calls.append)
    config = object()
    item = SimpleNamespace(config=config, get_closest_marker=lambda name: object() if desktop and name == 'desktop' else None)
    pytest_runtest_setup(item)
    assert calls == ([config] if desktop else [])


@pytest.mark.desktop
def test_the_real_notice_stays_on_top_without_taking_focus_and_closes():
    foreground = user32.GetForegroundWindow()
    notice = show_notice()
    try:
        wait_until(lambda: user32.FindWindowW(None, NOTICE_TITLE), 10, 'the notice never appeared')
        hwnd = user32.FindWindowW(None, NOTICE_TITLE)
        assert user32.IsWindowVisible(hwnd)
        assert user32.GetForegroundWindow() == foreground, 'the notice must not take focus'
        user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        style = user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
        assert style & 0x8, 'WS_EX_TOPMOST'
        assert style & 0x08000000, 'WS_EX_NOACTIVATE'
        time.sleep(1)
        assert user32.GetForegroundWindow() == foreground
    finally:
        notice.close()
    assert not user32.FindWindowW(None, NOTICE_TITLE), 'the notice closes by itself when the test starts'
