"""Native tool IDs are bound by the independent observer, without requiring another actor tool."""

import pytest

from bench.run import actor_window, bind_owned_window, new_calculator_window


def test_returned_numeric_or_hex_window_id_can_use_observer_pid():
    observed = 'window=100 pid=9\ncalculator=100\npid=9\n'
    assert bind_owned_window('', {'window_id': '100', 'target': {'title': 'Calculator'}}, observed) == ('100', 9)
    assert bind_owned_window('', {'window_id': '0x64'}, observed) == ('100', 9)


def test_preexisting_or_identity_mismatched_window_is_never_bound_for_cleanup():
    observed = 'window=100 pid=9\n'
    with pytest.raises(ValueError, match='pre-existing'):
        bind_owned_window('window=100 pid=9\n', {'window_id': '100'}, observed)
    with pytest.raises(ValueError, match='process identity'):
        bind_owned_window('', {'hwnd': '100', 'pid': 8}, observed)
    with pytest.raises(ValueError, match='observed'):
        bind_owned_window('', {'window_id': '101'}, observed)


def test_without_an_actor_claim_the_one_new_calculator_window_is_the_actors():
    before = 'window=50 pid=9\ncalculator=50\npid=9\n'
    observed = 'window=50 pid=9\nwindow=100 pid=8044\ncalculator=50\npid=9\ncalculator=100\npid=8044\n'
    assert new_calculator_window(before, observed) == ('100', 8044)
    assert actor_window(before, None, observed) == ('100', 8044)
    assert actor_window(before, {'status': 'completed'}, observed) == ('100', 8044), 'a claim without a window id falls back to observation'
    assert actor_window(before, {'window_id': '100'}, observed) == ('100', 8044)
    with pytest.raises(ValueError, match='exactly one'):
        new_calculator_window(before, before)
    two = observed + 'window=101 pid=8044\ncalculator=101\npid=8044\n'
    with pytest.raises(ValueError, match='exactly one'):
        new_calculator_window(before, two)


def test_hidden_preexisting_frame_host_shell_reused_by_the_new_window_is_still_owned():
    before = 'window=50 pid=9\nhiddenwindow=100 pid=8044\n'
    observed = 'window=100 pid=8044\ncalculator=100\npid=8044\n'
    assert bind_owned_window(before, {'window_id': '100'}, observed) == ('100', 8044)
    with pytest.raises(ValueError, match='pre-existing'):
        bind_owned_window('window=100 pid=8044\n', {'window_id': '100'}, observed)
