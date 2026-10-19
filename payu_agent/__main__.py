"""Command-line entry point for the read-only operations analyzer."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = (
    "order_id",
    "created_at",
    "order_status",
    "payment_status",
    "stock_status",
    "fulfillment_status",
    "delivery_status",
    "last_updated_at",
)

NUMERIC_FIELDS = ("item_total", "delivery_fee", "estimated_item_margin")


def parse_datetime(value: str) -> datetime | None:
    """Parse ISO-8601 datetime, accepting a trailing Z."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed


def read_orders(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV is missing a header row.")
        missing_headers = sorted(set(REQUIRED_FIELDS) - set(reader.fieldnames))
        if missing_headers:
            raise ValueError("CSV is missing required headers: " + ", ".join(missing_headers))
        return [
            {str(key): (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
        ]


def analyze_orders(
    rows: list[dict[str, str]],
    *,
    stale_hours: float | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    id_counts = Counter(row.get("order_id", "").strip() for row in rows)
    reference_now = now or datetime.now().astimezone()
    if reference_now.tzinfo is None:
        reference_now = reference_now.astimezone()

    for index, row in enumerate(rows, start=2):
        order_id = row.get("order_id", "").strip() or f"(row {index})"
        row_issues: list[dict[str, str]] = []

        for field in REQUIRED_FIELDS:
            if not row.get(field, "").strip():
                row_issues.append({
                    "code": "missing_required_field",
                    "field": field,
                    "message": f"Required field '{field}' is empty.",
                })

        real_id = row.get("order_id", "").strip()
        if real_id and id_counts[real_id] > 1:
            row_issues.append({
                "code": "duplicate_order_id",
                "field": "order_id",
                "message": f"Order ID '{real_id}' appears {id_counts[real_id]} times.",
            })

        for field in NUMERIC_FIELDS:
            value = row.get(field, "").strip()
            if value:
                try:
                    float(value)
                except ValueError:
                    row_issues.append({
                        "code": "invalid_numeric_value",
                        "field": field,
                        "message": f"'{field}' must be numeric when provided.",
                    })

        for field in ("created_at", "last_updated_at"):
            value = row.get(field, "").strip()
            if value and parse_datetime(value) is None:
                row_issues.append({
                    "code": "invalid_datetime",
                    "field": field,
                    "message": f"'{field}' must be a valid ISO-8601 datetime.",
                })

        if stale_hours is not None and row.get("last_updated_at", "").strip():
            updated = parse_datetime(row["last_updated_at"])
            if updated is not None:
                comparison_now = reference_now
                if updated.tzinfo is None:
                    updated = updated.astimezone()
                if comparison_now.tzinfo is None:
                    comparison_now = comparison_now.astimezone()
                age = comparison_now - updated
                if age > timedelta(hours=stale_hours):
                    row_issues.append({
                        "code": "stale_record",
                        "field": "last_updated_at",
                        "message": f"Record has not been updated for more than {stale_hours:g} hours.",
                    })

        if row_issues:
            issues.append({
                "order_id": order_id,
                "csv_row": index,
                "issue_count": len(row_issues),
                "issues": row_issues,
            })

    counts = Counter(issue["code"] for item in issues for issue in item["issues"])
    return {
        "report_version": 1,
        "mode": "read_only_csv_review",
        "orders_reviewed": len(rows),
        "orders_with_issues": len(issues),
        "total_issues": sum(item["issue_count"] for item in issues),
        "issue_counts": dict(sorted(counts.items())),
        "stale_threshold_hours": stale_hours,
        "issues": issues,
        "disclaimer": (
            "This report flags data-quality signals only. It does not confirm an order is broken "
            "and does not apply unverified Payu status-transition rules."
        ),
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [
        "Payu Operations Agent — Read-only review",
        f"Orders reviewed : {report['orders_reviewed']}",
        f"Orders flagged  : {report['orders_with_issues']}",
        f"Total issues    : {report['total_issues']}",
    ]
    if report["issue_counts"]:
        lines.append("")
        lines.append("Issue counts:")
        for code, count in report["issue_counts"].items():
            lines.append(f"  - {code}: {count}")
    if report["issues"]:
        lines.append("")
        lines.append("Flagged records:")
        for item in report["issues"]:
            lines.append(f"  Order {item['order_id']} (CSV row {item['csv_row']}):")
            for issue in item["issues"]:
                lines.append(f"    [{issue['code']}] {issue['message']}")
    lines.append("")
    lines.append(report["disclaimer"])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only CSV review for order operations.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="Analyze an order CSV export.")
    analyze.add_argument("csv_path", type=Path, help="Path to the CSV export.")
    analyze.add_argument("--json-out", type=Path, help="Optional path for a JSON report.")
    analyze.add_argument(
        "--stale-hours",
        type=float,
        default=None,
        help="Optional age threshold; stale records are only checked when set.",
    )
    analyze.add_argument(
        "--now",
        type=str,
        default=None,
        help="Optional ISO-8601 reference time for repeatable stale checks.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.stale_hours is not None and args.stale_hours < 0:
        parser.error("--stale-hours must be zero or greater.")

    now = None
    if args.now:
        now = parse_datetime(args.now)
        if now is None:
            parser.error("--now must be a valid ISO-8601 datetime.")

    try:
        rows = read_orders(args.csv_path)
        report = analyze_orders(rows, stale_hours=args.stale_hours, now=now)
    except (OSError, csv.Error, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(render_text(report))
    if args.json_out:
        try:
            args.json_out.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"Could not write JSON report: {exc}", file=sys.stderr)
            return 2
        print(f"\nJSON report written to: {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
