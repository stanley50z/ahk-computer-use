"""Accept UTF-8 JSON emitted by both ordinary files and Windows PowerShell 5.1."""

from bench.run import load_actor_json


def test_actor_json_with_utf8_bom_is_read_without_changing_original_bytes(tmp_path):
    path = tmp_path / 'result.json'
    original = b'\xef\xbb\xbf{"status":"blocked"}'
    path.write_bytes(original)
    assert load_actor_json(path) == {'status': 'blocked'}
    assert path.read_bytes() == original
