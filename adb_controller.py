import os
import random
import subprocess
import time

import numpy as np

DEVICE_SERIAL = os.environ.get("ADB_DEVICE_SERIAL", "localhost:5555")
COC_PACKAGE = "com.supercell.clashofclans"


def _run(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["adb", "-s", DEVICE_SERIAL, *args],
        capture_output=True,
        check=True,
    )


def _human_delay() -> None:
    time.sleep(max(0, random.gauss(0.12, 0.04)))


def screenshot() -> np.ndarray:
    result = _run("exec-out", "screencap", "-p")
    raw = np.frombuffer(result.stdout, dtype=np.uint8)
    import cv2
    img = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("Failed to decode screenshot from ADB")
    return img


def tap(x: int, y: int) -> None:
    _human_delay()
    _run("shell", "input", "tap", str(x), str(y))


def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
    _human_delay()
    _run("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))


def is_device_connected() -> bool:
    try:
        result = _run("get-state")
    except subprocess.CalledProcessError:
        return False
    return result.stdout.decode("utf-8", errors="ignore").strip() == "device"


def is_clash_foreground() -> bool:
    try:
        result = _run("shell", "dumpsys", "window", "windows")
    except subprocess.CalledProcessError:
        return False
    text = result.stdout.decode("utf-8", errors="ignore")
    return COC_PACKAGE in text


def ensure_ready() -> bool:
    return is_device_connected() and is_clash_foreground()
