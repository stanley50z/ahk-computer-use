"""Native tool IDs are bound by the independent observer, without requiring another actor tool."""

import pytest

from bench.run import bind_owned_window


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
