from __future__ import annotations

import re
import warnings
from collections import Counter
from collections import deque
from functools import lru_cache
from typing import Any

import cv2
import numpy as np


OCR_CHAR_MAP = str.maketrans(
    {
        "O": "0",
        "o": "0",
        "Q": "0",
        "D": "0",
        "I": "1",
        "l": "1",
        "|": "1",
        "!": "1",
        "Z": "2",
        "z": "2",
        "S": "5",
        "s": "5",
        "$": "5",
        "B": "8",
    }
)

# EasyOCR/PyTorch on macOS MPS can emit this warning repeatedly; it is benign.
warnings.filterwarnings(
    "ignore",
    message=".*pin_memory.*not supported on MPS.*",
    category=UserWarning,
)


def _normalize_ocr_text(raw_text: str) -> str:
    text = raw_text.translate(OCR_CHAR_MAP)
    text = text.replace(",", "").replace(" ", "").replace(".", "")
    return text


def _parse_number(raw_text: str) -> int:
    normalized = _normalize_ocr_text(raw_text)
    digits = re.sub(r"[^\d]", "", normalized)
    return int(digits) if digits else 0


@lru_cache(maxsize=1)
def _easyocr_reader() -> Any | None:
    try:
        import easyocr
    except ImportError:
        return None
    return easyocr.Reader(["en"], gpu=False, verbose=False)


def _easyocr_candidates(crop: np.ndarray) -> list[int]:
    reader = _easyocr_reader()
    if reader is None:
        return []

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    variants = [
        gray,
        cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
        cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1],
    ]

    candidates: list[int] = []
    allowlist = "0123456789OoQDlI|!ZzSs$B,."
    for image in variants:
        results = reader.readtext(image, detail=1, paragraph=False, allowlist=allowlist)
        for _, text, conf in results:
            if float(conf) < 0.05:
                continue
            value = _parse_number(text)
            if value > 0:
                candidates.append(value)
    return candidates


def _read_region(frame: np.ndarray, region: list[int], field_name: str = "") -> int:
    x, y, w, h = region
    crop = frame[y : y + h, x : x + w]
    if crop.size == 0:
        return 0

    # Trim out right-side resource icons on home bars.
    if field_name.startswith("home_"):
        trim_w = int(crop.shape[1] * 0.79)
        crop = crop[:, : max(1, trim_w)]

    easy_candidates = _easyocr_candidates(crop)
    if easy_candidates:
        counts = Counter(easy_candidates)
        best_count = counts.most_common(1)[0][1]
        common = sorted([v for v, c in counts.items() if c == best_count])
        return common[len(common) // 2]
    return 0


def extract_ocr_data(frame: np.ndarray, config: dict[str, Any]) -> dict[str, int]:
    regions = config.get("regions", {})
    data: dict[str, int] = {}
    for key in ("home_gold", "home_elixir", "enemy_gold", "enemy_elixir"):
        region = regions.get(key)
        if isinstance(region, list) and len(region) == 4:
            data[key] = _read_region(frame, region, field_name=key)
        else:
            data[key] = 0
    return data


class OcrStabilizer:
    def __init__(self, config: dict[str, Any]) -> None:
        cfg = config.get("ocr_stability", {})
        self.window = int(cfg.get("median_window", 3))
        self.rules = cfg.get("fields", {})
        self.history: dict[str, deque[int]] = {}
        self.last_good: dict[str, int] = {}

    def _rule(self, key: str) -> dict[str, Any]:
        default = {
            "min_value": 0,
            "max_value": 99_999_999,
            "min_digits": 0,
            "max_digits": 9,
            "max_abs_delta": None,
            "max_ratio": None,
        }
        custom = self.rules.get(key, {})
        if not isinstance(custom, dict):
            return default
        out = dict(default)
        out.update(custom)
        return out

    def _valid_digits(self, value: int, min_digits: int, max_digits: int) -> bool:
        if value == 0:
            return min_digits <= 1
        size = len(str(abs(value)))
        return min_digits <= size <= max_digits

    def _accept(self, key: str, candidate: int) -> bool:
        rule = self._rule(key)
        if candidate < int(rule["min_value"]) or candidate > int(rule["max_value"]):
            return False
        if not self._valid_digits(candidate, int(rule["min_digits"]), int(rule["max_digits"])):
            return False

        prev = self.last_good.get(key)
        if prev is None or prev <= 0 or candidate <= 0:
            return True

        max_abs_delta = rule.get("max_abs_delta")
        if isinstance(max_abs_delta, int) and abs(candidate - prev) > max_abs_delta:
            return False

        max_ratio = rule.get("max_ratio")
        if isinstance(max_ratio, (int, float)) and max_ratio > 1:
            hi = max(prev, candidate)
            lo = max(1, min(prev, candidate))
            if (hi / lo) > float(max_ratio):
                return False
        return True

    def _push(self, key: str, value: int) -> None:
        if key not in self.history:
            self.history[key] = deque(maxlen=max(1, self.window))
        self.history[key].append(int(value))

    def update(self, raw: dict[str, int]) -> dict[str, int]:
        out: dict[str, int] = {}
        for key, value in raw.items():
            candidate = int(value)
            if self._accept(key, candidate):
                self.last_good[key] = candidate
                self._push(key, candidate)
            elif key in self.last_good:
                self._push(key, self.last_good[key])
            else:
                self._push(key, 0)

            values = list(self.history.get(key, []))
            out[key] = int(np.median(values)) if values else 0
        return out
