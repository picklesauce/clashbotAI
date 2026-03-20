import argparse
import logging
import time
from typing import Any

import cv2

import adb_controller
from config import load_config
from debug_utils import draw_overlay, write_debug_snapshot
from models import Action, Detection
from ocr import OcrStabilizer, extract_ocr_data
from state_machine import StateMachine
from template_matcher import detect_templates

TICK_INTERVAL = 1.0 / 10  # ~10 fps
LOGGER = logging.getLogger(__name__)


def execute_action(action: Action) -> None:
    if action.type == "tap":
        adb_controller.tap(action.x, action.y)
    elif action.type == "swipe":
        if action.x2 is None or action.y2 is None:
            raise ValueError("Swipe action requires x2 and y2")
        adb_controller.swipe(action.x, action.y, action.x2, action.y2, action.duration_ms)
    if action.delay_ms > 0:
        time.sleep(action.delay_ms / 1000.0)


def run(
    config: dict[str, Any],
    dry_run: bool = False,
    debug_dir: str | None = None,
    debug_every: int = 20,
    preview: bool = False,
    preview_scale: float = 1.0,
) -> None:
    sm = StateMachine(config=config)
    vision_cfg = config.get("vision", {})
    use_ocr = bool(vision_cfg.get("use_ocr", False))
    ocr_stabilizer = OcrStabilizer(config) if use_ocr else None

    print(f"Bot started (dry_run={dry_run}). Press Ctrl+C to stop.")
    tick_index = 0

    try:
        while True:
            tick_start = time.monotonic()
            tick_index += 1

            if not adb_controller.ensure_ready():
                LOGGER.warning("ADB device or Clash of Clans is not ready; retrying")
                time.sleep(1.0)
                continue

            frame = adb_controller.screenshot()
            detections: list[Detection] = []
            raw_ocr = extract_ocr_data(frame, config) if use_ocr else {}
            ocr_data = ocr_stabilizer.update(raw_ocr) if ocr_stabilizer is not None else raw_ocr
            wall_threshold = int(config.get("thresholds", {}).get("upgrade_min_resource", 10_000_000))
            require_both_for_wall_upgrade = bool(
                config.get("thresholds", {}).get("require_both_for_wall_upgrade", True)
            )
            home_gold = int(ocr_data.get("home_gold", 0))
            home_elixir = int(ocr_data.get("home_elixir", 0))
            if require_both_for_wall_upgrade:
                allow_wall_scans = home_gold >= wall_threshold and home_elixir >= wall_threshold
            else:
                allow_wall_scans = home_gold >= wall_threshold or home_elixir >= wall_threshold

            template_paths = config.get("templates", {}).get("paths", {})
            include_template_keys = set(template_paths.keys())
            if not allow_wall_scans:
                include_template_keys -= {"wall_sample", "wall_upgrade_button", "wall_upgrade_button_alt"}

            template_hits = detect_templates(frame, config, include_keys=include_template_keys)
            sensor_data = dict(ocr_data)
            sensor_data["template_hits"] = template_hits
            actions = sm.tick(detections, ocr_data=sensor_data)

            for action in actions:
                if dry_run:
                    print(f"[DRY-RUN] {action}")
                else:
                    try:
                        execute_action(action)
                    except Exception as exc:  # keep loop alive on transient action failures
                        LOGGER.exception("Action failed: %s", exc)

            if debug_dir and tick_index % max(debug_every, 1) == 0:
                write_debug_snapshot(
                    debug_dir=debug_dir,
                    frame=frame,
                    detections=detections,
                    ocr_data=ocr_data,
                    template_hits=template_hits,
                    actions=actions,
                    regions=config.get("regions", {}),
                    template_regions=config.get("templates", {}).get("regions", {}),
                )

            if preview:
                view = draw_overlay(
                    frame,
                    detections,
                    regions=config.get("regions", {}),
                    template_hits=template_hits,
                    template_regions=config.get("templates", {}).get("regions", {}),
                )
                if preview_scale != 1.0:
                    new_w = max(1, int(view.shape[1] * preview_scale))
                    new_h = max(1, int(view.shape[0] * preview_scale))
                    view = cv2.resize(view, (new_w, new_h), interpolation=cv2.INTER_AREA)
                cv2.imshow("ClashBot Preview", view)
                # q or ESC exits the bot loop.
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break

            elapsed = time.monotonic() - tick_start
            sleep_time = TICK_INTERVAL - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    except KeyboardInterrupt:
        print("\nBot stopped.")
    finally:
        if preview:
            cv2.destroyAllWindows()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    parser = argparse.ArgumentParser(description="Clash of Clans farming bot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions instead of executing them",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config YAML (defaults to BOT_CONFIG_PATH or config.yaml)",
    )
    parser.add_argument(
        "--debug-dir",
        default=None,
        help="If set, saves periodic overlay frames and jsonl debug events",
    )
    parser.add_argument(
        "--debug-every",
        type=int,
        default=2,
        help="Write one debug snapshot every N ticks",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Show live overlay preview window",
    )
    parser.add_argument(
        "--preview-scale",
        type=float,
        default=0.8,
        help="Scale factor for preview window (e.g. 0.8)",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    run(
        config=config,
        dry_run=args.dry_run,
        debug_dir=args.debug_dir,
        debug_every=args.debug_every,
        preview=args.preview,
        preview_scale=args.preview_scale,
    )


if __name__ == "__main__":
    main()
