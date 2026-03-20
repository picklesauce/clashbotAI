from __future__ import annotations

import argparse

import cv2

from config import load_config
from ocr import OcrStabilizer, extract_ocr_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Test loot OCR against one screenshot")
    parser.add_argument("--image", required=True, help="Path to attack screenshot")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument(
        "--passes",
        type=int,
        default=1,
        help="How many repeated reads to run through stabilizer",
    )
    args = parser.parse_args()

    frame = cv2.imread(args.image, cv2.IMREAD_COLOR)
    if frame is None:
        raise FileNotFoundError(f"Could not load image: {args.image}")

    config = load_config(args.config)
    stabilizer = OcrStabilizer(config)
    data = {}
    for _ in range(max(1, args.passes)):
        raw = extract_ocr_data(frame, config)
        data = stabilizer.update(raw)

    print("OCR results:")
    print(f"  enemy_gold:   {data.get('enemy_gold', 0)}")
    print(f"  enemy_elixir: {data.get('enemy_elixir', 0)}")
    print(f"  home_gold:    {data.get('home_gold', 0)}")
    print(f"  home_elixir:  {data.get('home_elixir', 0)}")

    if data.get("enemy_gold", 0) == 0 and data.get("enemy_elixir", 0) == 0:
        print(
            "\nNote: Both enemy values are zero. Verify `pytesseract` and the system "
            "Tesseract binary are installed, then retune regions if needed."
        )


if __name__ == "__main__":
    main()
