"""Evaluation script - compare output.json against ground_truth.json and calculate metrics."""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


# Paths
PARENT_DIR = Path(__file__).parent.parent
OUTPUT_FILE = Path(__file__).parent / "output.json"
GROUND_TRUTH_FILE = PARENT_DIR / "ground_truth.json"


def load_data(filepath: Path) -> List[Dict[str, Any]]:
    """Load JSON data from file."""
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    with open(filepath, "r") as f:
        return json.load(f)


def compare_values(actual: Any, expected: Any) -> bool:
    """Compare two values with tolerance for floats."""
    if actual is None and expected is None:
        return True
    if actual is None or expected is None:
        return False
    if isinstance(expected, float) and isinstance(actual, (int, float)):
        # For floats, check if they match to 2 decimal places
        return abs(float(actual) - float(expected)) < 0.01
    return actual == expected


def calculate_field_accuracy(
    outputs: List[Dict], ground_truth: List[Dict], field: str
) -> Tuple[int, int]:
    """Calculate accuracy for a specific field."""
    correct = 0
    total = 0

    for output, truth in zip(outputs, ground_truth):
        if output.get("id") == truth.get("id"):
            total += 1
            if compare_values(output.get(field), truth.get(field)):
                correct += 1

    return correct, total


def evaluate():
    """Evaluate outputs against ground truth."""
    try:
        outputs = load_data(OUTPUT_FILE)
        truths = load_data(GROUND_TRUTH_FILE)

        if not outputs:
            print("❌ output.json is empty. Run extract.py first.")
            return

        print(f"\n📊 EVALUATION RESULTS")
        print("=" * 60)

        # Overall accuracy
        correct_records = 0
        total_records = 0

        # Field-level accuracy
        fields = [
            "product_line",
            "origin_port_code",
            "origin_port_name",
            "destination_port_code",
            "destination_port_name",
            "incoterm",
            "cargo_weight_kg",
            "cargo_cbm",
            "is_dangerous",
        ]

        field_scores = {}
        for field in fields:
            correct, total = calculate_field_accuracy(outputs, truths, field)
            field_scores[field] = (correct, total)
            accuracy = (correct / total * 100) if total > 0 else 0
            print(f"  {field:<25} {correct:3d}/{total:<3d}  {accuracy:6.1f}%")

        # Overall record accuracy (all fields match)
        for output, truth in zip(outputs, truths):
            if output.get("id") == truth.get("id"):
                total_records += 1
                all_match = True
                for field in fields:
                    if not compare_values(output.get(field), truth.get(field)):
                        all_match = False
                        break
                if all_match:
                    correct_records += 1

        print("=" * 60)
        overall_accuracy = (
            correct_records / total_records * 100 if total_records > 0 else 0
        )
        print(f"  OVERALL ACCURACY:        {correct_records:3d}/{total_records:<3d}  {overall_accuracy:6.1f}%")
        print("=" * 60)

        # Show first few mismatches for debugging
        print(f"\n🔍 SAMPLE MISMATCHES (first 3):")
        mismatch_count = 0
        for output, truth in zip(outputs, truths):
            if output.get("id") == truth.get("id"):
                mismatches = []
                for field in fields:
                    actual = output.get(field)
                    expected = truth.get(field)
                    if not compare_values(actual, expected):
                        mismatches.append((field, actual, expected))

                if mismatches and mismatch_count < 3:
                    print(f"\n  {output.get('id')}:")
                    for field, actual, expected in mismatches:
                        print(
                            f"    {field}: got {actual!r}, expected {expected!r}"
                        )
                    mismatch_count += 1

    except FileNotFoundError as e:
        print(f"❌ {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    evaluate()
