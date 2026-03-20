from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import cv2
import yaml

import adb_controller
from config import load_config


def _click_point(frame, prompt: str) -> list[int]:
    window = "calibrate-point"
    state: dict[str, Any] = {"point": None}

    def _on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state["point"] = [int(x), int(y)]

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.imshow(window, frame)
    cv2.setMouseCallback(window, _on_mouse)

    print(f"{prompt}: click once in the window.")
    while True:
        cv2.waitKey(20)
        if state["point"] is not None:
            preview = frame.copy()
            x, y = state["point"]
            cv2.circle(preview, (x, y), 10, (0, 255, 0), 2)
            cv2.imshow(window, preview)
            break

    cv2.destroyWindow(window)
    return state["point"]


def _select_region(frame, prompt: str) -> list[int]:
    print(f"{prompt}: drag-select region and press ENTER/SPACE in the image window.")
    x, y, w, h = cv2.selectROI("calibrate-region", frame, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow("calibrate-region")
    return [int(x), int(y), int(w), int(h)]


def _save_config(path: str, cfg: dict[str, Any]) -> None:
    resolved = Path(path)
    with resolved.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(cfg, handle, sort_keys=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive config calibration")
    parser.add_argument("--config", default="config.yaml", help="Path to config yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    frame = adb_controller.screenshot()

    coords = cfg.setdefault("coordinates", {})
    regions = cfg.setdefault("regions", {})

    point_keys = [
        "attack_button",
        "find_match_button",
        "next_match_button",
        "return_home_button",
        "wall_upgrade_button",
        "wall_sample",
    ]
    for key in point_keys:
        coords[key] = _click_point(frame, f"Set {key}")
        _save_config(args.config, cfg)
        print(f"Saved {key}: {coords[key]}")

    region_keys = ["home_gold", "home_elixir", "enemy_gold", "enemy_elixir"]
    for key in region_keys:
        regions[key] = _select_region(frame, f"Set OCR region {key}")
        _save_config(args.config, cfg)
        print(f"Saved {key}: {regions[key]}")

    print(f"Calibration complete -> {args.config}")


if __name__ == "__main__":
    main()
