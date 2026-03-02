import argparse
import csv
import json
from pathlib import Path

import pytesseract
from PIL import Image

from ocr_utils import average_confidence, extract_water_meter_value
from preprocessing import preprocess_for_ocr


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def run_ocr(image_path: Path, lang: str) -> dict:
    base_image = Image.open(image_path)
    processed_image = preprocess_for_ocr(str(image_path))

    raw_text = pytesseract.image_to_string(base_image, lang=lang)
    raw_data = pytesseract.image_to_data(
        base_image,
        lang=lang,
        output_type=pytesseract.Output.DICT,
    )
    raw_conf = average_confidence(raw_data)

    processed_text = pytesseract.image_to_string(processed_image, lang=lang)
    processed_data = pytesseract.image_to_data(
        processed_image,
        lang=lang,
        output_type=pytesseract.Output.DICT,
    )
    processed_conf = average_confidence(processed_data)

    final_text = processed_text if processed_conf >= raw_conf else raw_text
    final_conf = max(raw_conf, processed_conf)
    value = extract_water_meter_value(final_text)

    return {
        "file": image_path.name,
        "value": value,
        "confidence": round(final_conf, 2),
        "selected": "processed" if processed_conf >= raw_conf else "raw",
        "raw_confidence": round(raw_conf, 2),
        "processed_confidence": round(processed_conf, 2),
        "raw_text": raw_text.strip(),
        "processed_text": processed_text.strip(),
    }


def load_ground_truth(path: Path) -> dict:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("ground truth file must be JSON object: {\"image.jpg\": \"12345\"}")

    return {str(key): str(value) for key, value in data.items()}


def main():
    parser = argparse.ArgumentParser(description="OCR benchmark for water meter images")
    parser.add_argument("--images-dir", default="test_images", help="Directory with .jpg/.jpeg/.png test images")
    parser.add_argument("--lang", default="srp", help="Tesseract language (default: srp)")
    parser.add_argument(
        "--ground-truth",
        default="",
        help="Optional JSON file with expected readings, e.g. {\"img1.jpg\":\"12345\"}",
    )
    parser.add_argument("--output-csv", default="ocr_benchmark_results.csv", help="Output CSV report path")
    args = parser.parse_args()

    images_dir = Path(args.images_dir)
    if not images_dir.exists() or not images_dir.is_dir():
        raise FileNotFoundError(f"Images directory not found: {images_dir}")

    ground_truth = load_ground_truth(Path(args.ground_truth)) if args.ground_truth else {}

    image_paths = sorted(
        [path for path in images_dir.iterdir() if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS]
    )

    if not image_paths:
        print("No images found in directory.")
        return

    rows = []
    exact_matches = 0
    total_labeled = 0

    for image_path in image_paths:
        result = run_ocr(image_path, args.lang)
        expected = ground_truth.get(image_path.name)
        is_match = ""
        if expected is not None:
            total_labeled += 1
            is_match = str(result["value"] == expected)
            if result["value"] == expected:
                exact_matches += 1

        result["expected"] = expected if expected is not None else ""
        result["exact_match"] = is_match
        rows.append(result)
        print(f"{image_path.name}: value={result['value']} conf={result['confidence']} selected={result['selected']}")

    output_path = Path(args.output_csv)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "file",
                "value",
                "expected",
                "exact_match",
                "confidence",
                "selected",
                "raw_confidence",
                "processed_confidence",
                "raw_text",
                "processed_text",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved report: {output_path}")
    if total_labeled > 0:
        accuracy = (exact_matches / total_labeled) * 100
        print(f"Labeled images: {total_labeled}")
        print(f"Exact match: {exact_matches}/{total_labeled} ({accuracy:.2f}%)")


if __name__ == "__main__":
    main()