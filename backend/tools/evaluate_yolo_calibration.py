#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter


@dataclass(frozen=True)
class CalibrationCase:
    filename: str
    expected_count: int
    image_path: Path


def load_manifest(manifest_path: Path, input_dir: Path) -> list[CalibrationCase]:
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required_fields = {"filename", "expected_count"}
        if reader.fieldnames is None or not required_fields.issubset(reader.fieldnames):
            raise ValueError(
                "manifest must contain filename and expected_count columns"
            )

        cases: list[CalibrationCase] = []
        seen_filenames: set[str] = set()
        for line_number, row in enumerate(reader, start=2):
            filename = row["filename"].strip()
            relative_path = Path(filename)
            if (
                not filename
                or relative_path.is_absolute()
                or len(relative_path.parts) != 1
                or relative_path.name != filename
            ):
                raise ValueError(
                    f"invalid filename at manifest line {line_number}: {filename!r}"
                )
            if filename in seen_filenames:
                raise ValueError(f"duplicate filename in manifest: {filename}")

            try:
                expected_count = int(row["expected_count"])
            except ValueError as exc:
                raise ValueError(
                    f"invalid expected_count at manifest line {line_number}"
                ) from exc
            if expected_count < 0:
                raise ValueError(
                    f"expected_count must not be negative at line {line_number}"
                )

            image_path = input_dir / filename
            if not image_path.is_file():
                raise FileNotFoundError(image_path)

            seen_filenames.add(filename)
            cases.append(
                CalibrationCase(
                    filename=filename,
                    expected_count=expected_count,
                    image_path=image_path,
                )
            )

    if not cases:
        raise ValueError("manifest contains no calibration images")
    return cases


def write_report(output_path: Path, results: list[dict[str, object]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    fieldnames = (
        "filename",
        "expected_count",
        "detected_count",
        "difference",
        "absolute_error",
        "inference_seconds",
    )
    with temporary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    temporary_path.replace(output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate CrowdedDetector YOLO counts against a CSV manifest."
    )
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="0")
    parser.add_argument("--confidence", type=float, default=0.35)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--warmup-width", type=int, default=1280)
    parser.add_argument("--warmup-height", type=int, default=720)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    import torch

    from crowded_backend.inference.person_detector import YoloPersonDetector
    from crowded_backend.logging_config import configure_application_logging

    configure_application_logging()
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("exactly one CUDA GPU must be visible")
    if not args.model.is_file():
        raise FileNotFoundError(args.model)
    if not 0.0 < args.confidence <= 1.0:
        raise ValueError("confidence must be in (0, 1]")
    if args.image_size <= 0:
        raise ValueError("image-size must be positive")

    cases = load_manifest(args.manifest, args.input_dir)
    print("GPU 0:", torch.cuda.get_device_name(0))
    print("Calibration images:", len(cases))
    print("Confidence threshold:", args.confidence)
    print("YOLO image size:", args.image_size)

    detector = YoloPersonDetector(
        model_name=str(args.model),
        device=args.device,
        confidence=args.confidence,
        image_size=args.image_size,
        warmup_width=args.warmup_width,
        warmup_height=args.warmup_height,
    )

    results: list[dict[str, object]] = []
    for case in cases:
        payload = case.image_path.read_bytes()
        torch.cuda.synchronize()
        started = perf_counter()
        detected_count = detector.count(payload)
        torch.cuda.synchronize()
        inference_seconds = perf_counter() - started
        difference = detected_count - case.expected_count
        absolute_error = abs(difference)
        results.append(
            {
                "filename": case.filename,
                "expected_count": case.expected_count,
                "detected_count": detected_count,
                "difference": difference,
                "absolute_error": absolute_error,
                "inference_seconds": f"{inference_seconds:.4f}",
            }
        )
        print(
            f"{case.filename}: expected={case.expected_count} "
            f"detected={detected_count} difference={difference:+d} "
            f"seconds={inference_seconds:.4f}"
        )

    write_report(args.output, results)
    count = len(results)
    exact_matches = sum(row["absolute_error"] == 0 for row in results)
    mean_absolute_error = sum(
        int(row["absolute_error"]) for row in results
    ) / count
    mean_difference = sum(int(row["difference"]) for row in results) / count
    maximum_absolute_error = max(int(row["absolute_error"]) for row in results)

    print(f"Exact matches: {exact_matches}/{count}")
    print(f"Mean absolute error: {mean_absolute_error:.3f}")
    print(f"Mean difference: {mean_difference:+.3f}")
    print(f"Maximum absolute error: {maximum_absolute_error}")
    print("Report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
