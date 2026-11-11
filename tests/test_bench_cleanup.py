"""Safety boundaries for cleanup; these checks never open AutoHotkey or desktop windows."""

import pytest

from bench.calculator import owned_window


def test_any_preexisting_window_is_protected_even_if_not_identified_as_calculator():
    before = 'window=42 pid=7\ncalculator=99\npid=8\n'
    with pytest.raises(ValueError, match='pre-existing'):
        owned_window(before, {'hwnd': '42', 'pid': 7})
    with pytest.raises(ValueError, match='pre-existing'):
        owned_window(before, {'hwnd': '99', 'pid': 8})
    assert owned_window(before, {'hwnd': '100', 'pid': 9}) == ('100', 9)


def test_stop_acknowledges_only_a_finished_worker_with_verified_cleanup(tmp_path):
    from bench.stop import cleanup_verified
    from test_bench_outcome import finished_trial

    assert cleanup_verified(finished_trial(tmp_path / 'clean'))
    assert not cleanup_verified(finished_trial(tmp_path / 'dirty', cleanup={'passed': False, 'cursor_scheme_restored': True}))
    unfinished = finished_trial(tmp_path / 'unfinished')
    (unfinished / 'finished.json').unlink()
    assert not cleanup_verified(unfinished)
    # A task, conduct or controller failure is not a cleanup failure; stop only waits for cleanup.
    crashed = finished_trial(tmp_path / 'crashed', conduct={'passed': False, 'problems': ['x']})
    (crashed / 'crash.txt').write_text('Traceback', encoding='utf-8')
    assert cleanup_verified(crashed)


def test_cleanup_requires_window_and_process_identity():
    with pytest.raises(ValueError, match='identity'):
        owned_window('', {'hwnd': '42'})
    with pytest.raises(ValueError, match='identity'):
        owned_window('', {'hwnd': '42', 'pid': 0})
