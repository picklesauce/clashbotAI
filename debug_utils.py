from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
import json

import cv2
import numpy as np

from models import Action, Detection


def draw_overlay(
    frame: np.ndarray,
    detections: list[Detection],
    regions: dict[str, list[int]],
    template_hits: dict[str, tuple[int, int, float]] | None = None,
    template_regions: dict[str, list[int]] | None = None,
) -> np.ndarray:
    canvas = frame.copy()

    for det in detections:
        x1, y1, x2, y2 = det.bbox
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"{det.class_name} {det.confidence:.2f}"
        cv2.putText(canvas, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    for name, region in regions.items():
        if len(region) != 4:
            continue
        x, y, w, h = region
        cv2.rectangle(canvas, (x, y), (x + w, y + h), (255, 180, 0), 2)
        cv2.putText(canvas, name, (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 180, 0), 2)

    if template_regions:
        for name, region in template_regions.items():
            if len(region) != 4:
                continue
            x, y, w, h = region
            cv2.rectangle(canvas, (x, y), (x + w, y + h), (180, 120, 255), 1)
            cv2.putText(
                canvas,
                f"tm:{name}",
                (x, max(20, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (180, 120, 255),
                1,
            )

    if template_hits:
        for name, hit in template_hits.items():
            if len(hit) < 3:
                continue
            x, y, score = int(hit[0]), int(hit[1]), float(hit[2])
            cv2.drawMarker(canvas, (x, y), (0, 0, 255), cv2.MARKER_CROSS, 20, 2)
            cv2.putText(
                canvas,
                f"{name}:{score:.2f}",
                (x + 6, max(20, y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                2,
            )

    return canvas


def write_debug_snapshot(
    debug_dir: str,
    frame: np.ndarray,
    detections: list[Detection],
    ocr_data: dict[str, int],
    template_hits: dict[str, tuple[int, int, float]],
    actions: list[Action],
    regions: dict[str, list[int]],
    template_regions: dict[str, list[int]] | None = None,
) -> None:
    out_dir = Path(debug_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S_%fZ")

    overlay = draw_overlay(
        frame,
        detections,
        regions,
        template_hits=template_hits,
        template_regions=template_regions,
    )
    image_path = out_dir / f"{ts}.png"
    cv2.imwrite(str(image_path), overlay)

    meta_path = out_dir / "events.jsonl"
    payload: dict[str, Any] = {
        "timestamp": ts,
        "image": image_path.name,
        "ocr_data": ocr_data,
        "template_hits": template_hits,
        "detections": [asdict(d) for d in detections],
        "actions": [asdict(a) for a in actions],
    }
    with meta_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
