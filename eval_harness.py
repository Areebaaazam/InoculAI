"""Evaluate SENTINEL without hiding rejected input or unresolved model results."""

import argparse
import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

from sentinel import InputRejected, classify


@dataclass
class Evaluation:
    total: int = 0
    tp: int = 0
    tn: int = 0
    fp: int = 0
    fn: int = 0
    errors: list[tuple[int, str]] = field(default_factory=list)
    fatal: str | None = None

    @property
    def classified(self) -> int:
        return self.tp + self.tn + self.fp + self.fn

    @property
    def accuracy(self) -> float:
        # Rejected rows and abstentions remain in the denominator as errors.
        return (self.tp + self.tn) / self.total if self.total else 0.0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        return 2 * self.precision * self.recall / (self.precision + self.recall) if self.precision + self.recall else 0.0


def evaluate(path: str | Path, threshold: float = 0.5, *, cache_only: bool | None = None) -> Evaluation:
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be finite and in [0, 1]")
    report = Evaluation()
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as source:
            reader = csv.reader(source, strict=True)
            header = next(reader, None)
            if header != ["text", "label"]:
                report.fatal = "CSV header must be exactly text,label"
                report.errors.append((1, report.fatal))
                return report
            while True:
                line = reader.line_num + 1
                try:
                    row = next(reader)
                except StopIteration:
                    break
                except (csv.Error, UnicodeError) as exc:
                    report.total += 1
                    report.errors.append((line, f"unreadable CSV: {type(exc).__name__}"))
                    report.fatal = "unreadable CSV tail; remaining logical rows cannot be counted safely"
                    break
                report.total += 1
                if len(row) != 2 or row[1] not in ("scam", "clean"):
                    report.errors.append((line, "row must have exactly two columns and a scam|clean label"))
                    continue
                try:
                    verdict = classify(row[0], cache_only=cache_only)
                except InputRejected as exc:
                    report.errors.append((line, str(exc)))
                    continue
                if verdict.needs_review:
                    report.errors.append((line, verdict.reason or "classification requires review"))
                    continue
                predicted = verdict.injection or verdict.scam_probability >= threshold
                actual = row[1] == "scam"
                name = "tp" if predicted and actual else "fp" if predicted else "fn" if actual else "tn"
                setattr(report, name, getattr(report, name) + 1)
    except (OSError, UnicodeError, csv.Error) as exc:
        report.fatal = f"CSV cannot be read: {type(exc).__name__}"
        report.errors.append((0, report.fatal))
    if not report.total and not report.fatal:
        report.fatal = "CSV contains no labeled messages"
        report.errors.append((2, report.fatal))
    return report


def print_report(report: Evaluation):
    print(f"Accuracy: {report.accuracy:.2%} (errors count as incorrect)")
    print(f"Precision: {report.precision:.4f}\nRecall: {report.recall:.4f}\nF1: {report.f1:.4f}")
    print(f"Confusion: TP={report.tp} TN={report.tn} FP={report.fp} FN={report.fn}")
    print(f"Coverage: {report.classified}/{report.total}; errors={len(report.errors)}")
    print("Precision/recall/F1 and confusion counts cover resolved rows only.")
    for line, reason in report.errors:
        print(f"ERROR line {line}: {reason}")
    if report.fatal:
        print(f"NO DECK NUMBER: {report.fatal}")
    else:
        suffix = f" (INCOMPLETE: {len(report.errors)} errors; do not use in deck)" if report.errors else ""
        print(f"SENTINEL accuracy: {report.accuracy:.1%} on {report.total} labeled messages{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--cache-only", action="store_true", default=None)
    args = parser.parse_args()
    if not math.isfinite(args.threshold) or not 0 <= args.threshold <= 1:
        parser.error("--threshold must be finite and in [0, 1]")
    report = evaluate(args.csv_path, args.threshold, cache_only=args.cache_only)
    print_report(report)
    return int(bool(report.errors or report.fatal))


if __name__ == "__main__":
    raise SystemExit(main())
