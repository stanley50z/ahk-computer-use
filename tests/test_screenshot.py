"""The screenshot script: fullscreen, app, and custom captures that report their screen origin and scale."""

import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from PIL import Image

from conftest import REPO, foreground, monitor_rects, reported, run_launcher, visible_frame, wait_until

SCREENSHOT = REPO / "acu" / "screenshot.ahk"


def shoot(*args):
    """Run the screenshot script through the launcher with the given action and options."""
    return run_launcher(SCREENSHOT, "--timeout", "15", "--", *args)


@contextmanager
def foreground_watch():
    """Collect every foreground window seen while the body runs, polled every two milliseconds."""
    seen = set()
    stop = threading.Event()

    def poll():
        while not stop.is_set():
            if hwnd := foreground():
                seen.add(hwnd)
            time.sleep(0.002)

    watcher = threading.Thread(target=poll, daemon=True)
    watcher.start()
    try:
        yield seen
    finally:
        stop.set()
        watcher.join()


def source_rect(stdout):
    """Parse `source=X,Y WxH` into (x, y, width, height)."""
    origin, size = reported(stdout, "source").split(" ")
    x, y = (int(v) for v in origin.split(","))
    w, h = (int(v) for v in size.split("x"))
    return x, y, w, h


def image_size(stdout):
    """Parse `image=WxH` into (width, height)."""
    w, h = (int(v) for v in reported(stdout, "image").split("x"))
    return w, h


@pytest.mark.parametrize("monitor", [1, 2])
def test_fullscreen_captures_one_monitor_downscaled_to_1280(monitor, tmp_path):
    rects = monitor_rects()
    if monitor > len(rects):
        pytest.skip(f"monitor {monitor} is not attached")
    out = tmp_path / "shot.png"

    result = shoot("fullscreen", str(monitor), "--out", str(out))

    assert result.returncode == 0, result.stdout + result.stderr
    assert reported(result.stdout, "saved") == str(out)
    x, y, w, h = source_rect(result.stdout)
    assert (x, y, w, h) == rects[monitor - 1]
    longest = max(w, h)
    expected_scale = longest / 1280 if longest > 1280 else 1  # downscale only, never upscale
    assert float(reported(result.stdout, "scale")) == pytest.approx(expected_scale, abs=1e-4)
    with Image.open(out) as img:
        assert img.size == image_size(result.stdout)
        assert img.size == (round(w / expected_scale), round(h / expected_scale))
        assert img.convert("RGB").getcolors(2) is None, "a real desktop capture has more than two colors"


def test_custom_captures_the_given_rectangle_at_full_size(tmp_path):
    out = tmp_path / "zoom.png"

    result = shoot("custom", "100", "200", "420", "440", "--out", str(out))

    assert result.returncode == 0, result.stdout + result.stderr
    assert source_rect(result.stdout) == (100, 200, 320, 240)
    assert reported(result.stdout, "scale") == "1"
    with Image.open(out) as img:
        assert img.size == (320, 240)


def test_out_creates_missing_directories_and_accepts_forward_slashes(tmp_path):
    out = tmp_path / "deeper" / "still" / "shot.png"

    result = shoot("custom", "0", "0", "64", "64", "--out", str(out).replace("\\", "/"))

    assert result.returncode == 0, result.stdout + result.stderr
    assert reported(result.stdout, "saved") == str(out)
    with Image.open(out) as img:
        assert img.size == (64, 64)


def test_custom_downscales_to_max_and_reports_the_scale(tmp_path):
    out = tmp_path / "wide.png"

    result = shoot("custom", "0", "0", "2560", "1440", "--max", "640", "--out", str(out))

    assert result.returncode == 0, result.stdout + result.stderr
    assert source_rect(result.stdout) == (0, 0, 2560, 1440)
    assert reported(result.stdout, "scale") == "4"
    with Image.open(out) as img:
        assert img.size == (640, 360)


def test_app_captures_a_covered_window_without_activating_it(open_window, tmp_path):
    target = open_window(f"ACU shot target {os.getpid()}", 100, 100, backcolor="2E8B57")
    cover = open_window(f"ACU cover {os.getpid()}", 100, 100)
    wait_until(lambda: foreground() == cover, 2, "precondition: the cover window must be in front")
    out = tmp_path / "app.png"

    with foreground_watch() as seen:
        result = shoot("app", f"ACU shot target {os.getpid()}", "--out", str(out))

    assert result.returncode == 0, result.stdout + result.stderr
    assert seen == {cover}, "a screenshot must not change the foreground window, even for a moment"
    x, y, w, h = source_rect(result.stdout)
    assert (x, y, w, h) == visible_frame(target)
    assert reported(result.stdout, "scale") == "1"
    with Image.open(out) as img:
        assert img.size == (w, h)
        pixel = img.convert("RGB").getpixel((w - 10, h - 10))
        assert all(abs(got - want) <= 8 for got, want in zip(pixel, (0x2E, 0x8B, 0x57))), f"expected the window's own background, got {pixel}"


def test_app_reports_a_missing_window(tmp_path):
    result = shoot("app", "ahk_class NoSuchWindowClass_ACU", "--out", str(tmp_path / "none.png"))

    assert result.returncode == 1, result.stdout + result.stderr
    assert "Target window not found" in result.stdout
    assert not (tmp_path / "none.png").exists()


def test_default_output_goes_to_shots_and_keeps_only_the_newest_30(acu_home):
    shots = acu_home / "shots"
    shots.mkdir(parents=True)
    base = time.time() - 600
    for i in range(35):
        old = shots / f"old-{i:02}.png"
        old.write_bytes(b"not a real png")
        os.utime(old, (base + i, base + i))

    result = shoot("custom", "0", "0", "64", "64")

    assert result.returncode == 0, result.stdout + result.stderr
    saved = Path(reported(result.stdout, "saved"))
    assert saved.parent == shots
    assert saved.name.endswith("-custom.png")
    remaining = sorted(p.name for p in shots.glob("*.png"))
    assert len(remaining) == 30
    assert saved.name in remaining
    # 35 old files plus the new one, keep 30: the six oldest go.
    assert "old-05.png" not in remaining and "old-06.png" in remaining
