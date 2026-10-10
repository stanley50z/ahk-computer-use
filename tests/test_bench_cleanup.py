"""Safety boundaries for cleanup; these checks never open AutoHotkey or desktop windows."""

import pytest

from bench.run import owned_window, cleanup_finished


def test_any_preexisting_window_is_protected_even_if_not_identified_as_calculator():
    before = 'window=42 pid=7\ncalculator=99\npid=8\n'
    with pytest.raises(ValueError, match='pre-existing'):
        owned_window(before, {'hwnd': '42', 'pid': 7})
    with pytest.raises(ValueError, match='pre-existing'):
        owned_window(before, {'hwnd': '99', 'pid': 8})
    assert owned_window(before, {'hwnd': '100', 'pid': 9}) == ('100', 9)


def test_cleanup_requires_window_and_process_identity_and_does_not_trust_completion_marker():
    with pytest.raises(ValueError, match='identity'):
        owned_window('', {'hwnd': '42'})
    with pytest.raises(ValueError, match='identity'):
        owned_window('', {'hwnd': '42', 'pid': 0})
    assert not cleanup_finished({'worker_finished': True, 'cleanup': {'passed': False}})
    assert not cleanup_finished({'worker_finished': True})
    assert not cleanup_finished({'worker_finished': True, 'cleanup': {'passed': True}})
    assert not cleanup_finished({'worker_finished': True, 'cleanup': {'passed': True, 'cursor_scheme_restored': False}})
    assert cleanup_finished({'worker_finished': True, 'cleanup': {'passed': True, 'cursor_scheme_restored': True}})
