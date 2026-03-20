from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _load_template(path: str) -> np.ndarray | None:
    resolved = Path(path)
    if not resolved.exists():
        return None
    return cv2.imread(str(resolved), cv2.IMREAD_GRAYSCALE)


def _match_with_scales(
    frame_gray: np.ndarray,
    template_gray: np.ndarray,
    scales: list[float],
) -> tuple[float, tuple[int, int] | None]:
    best_score = -1.0
    best_center: tuple[int, int] | None = None

    for scale in scales:
        if scale <= 0:
            continue
        tw = max(1, int(template_gray.shape[1] * scale))
        th = max(1, int(template_gray.shape[0] * scale))
        if tw > frame_gray.shape[1] or th > frame_gray.shape[0]:
            continue

        resized = cv2.resize(template_gray, (tw, th), interpolation=cv2.INTER_AREA)
        result = cv2.matchTemplate(frame_gray, resized, cv2.TM_CCOEFF_NORMED)
        _, score, _, max_loc = cv2.minMaxLoc(result)
        if score <= best_score:
            continue

        x, y = max_loc
        best_score = float(score)
        best_center = (x + tw // 2, y + th // 2)

    return best_score, best_center


def detect_templates(
    frame: np.ndarray,
    config: dict[str, Any],
    include_keys: set[str] | None = None,
) -> dict[str, tuple[int, int, float]]:
    template_cfg = config.get("templates", {})
    template_paths = template_cfg.get("paths", {})
    default_threshold = float(template_cfg.get("threshold", 0.83))
    per_template_thresholds = template_cfg.get("thresholds", {})
    per_template_regions = template_cfg.get("regions", {})
    scales = template_cfg.get("scales", [1.0])
    if not isinstance(scales, list):
        scales = [1.0]

    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hits: dict[str, tuple[int, int, float]] = {}

    for key, path in template_paths.items():
        if include_keys is not None and key not in include_keys:
            continue
        if not isinstance(path, str):
            continue
        template = _load_template(path)
        if template is None:
            continue

        threshold = default_threshold
        custom_threshold = per_template_thresholds.get(key)
        if isinstance(custom_threshold, (int, float)):
            threshold = float(custom_threshold)

        search_gray = frame_gray
        region_offset_x = 0
        region_offset_y = 0
        custom_region = per_template_regions.get(key)
        if isinstance(custom_region, list) and len(custom_region) == 4:
            rx, ry, rw, rh = (int(v) for v in custom_region)
            rx = max(0, min(frame_gray.shape[1] - 1, rx))
            ry = max(0, min(frame_gray.shape[0] - 1, ry))
            rw = max(1, min(frame_gray.shape[1] - rx, rw))
            rh = max(1, min(frame_gray.shape[0] - ry, rh))
            search_gray = frame_gray[ry : ry + rh, rx : rx + rw]
            region_offset_x = rx
            region_offset_y = ry

        score, center = _match_with_scales(search_gray, template, [float(s) for s in scales])
        if center is None or score < threshold:
            continue
        cx, cy = center
        hits[key] = (int(cx + region_offset_x), int(cy + region_offset_y), float(score))

    return hits
