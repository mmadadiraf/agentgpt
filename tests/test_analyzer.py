import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from payu_agent.__main__ import analyze_orders, read_orders


class AnalyzerTests(unittest.TestCase):
    def test_missing_field_is_flagged(self):
        report = analyze_orders([{
            "order_id": "X-1",
            "created_at": "2026-10-19T10:00:00+07:00",
            "order_status": "received",
            "payment_status": "",
            "stock_status": "unknown",
            "fulfillment_status": "pending",
            "delivery_status": "not_started",
            "last_updated_at": "2026-10-19T10:00:00+07:00",
        }])
        self.assertEqual(report["orders_reviewed"], 1)
        self.assertEqual(report["orders_with_issues"], 1)
        self.assertIn("missing_required_field", report["issue_counts"])

    def test_duplicate_order_ids_are_flagged(self):
        row = {
            "order_id": "DUP",
            "created_at": "2026-10-19T10:00:00+07:00",
            "order_status": "received",
            "payment_status": "unconfirmed",
            "stock_status": "unknown",
            "fulfillment_status": "pending",
            "delivery_status": "not_started",
            "last_updated_at": "2026-10-19T10:00:00+07:00",
        }
        report = analyze_orders([row, row])
        self.assertEqual(report["issue_counts"]["duplicate_order_id"], 2)

    def test_staleness_is_only_checked_when_requested(self):
        row = {
            "order_id": "OLD",
            "created_at": "2026-10-18T10:00:00+07:00",
            "order_status": "received",
            "payment_status": "unconfirmed",
            "stock_status": "unknown",
            "fulfillment_status": "pending",
            "delivery_status": "not_started",
            "last_updated_at": "2026-10-18T10:00:00+07:00",
        }
        reference = datetime.fromisoformat("2026-10-19T12:00:00+07:00")
        default_report = analyze_orders([row], now=reference)
        stale_report = analyze_orders([row], stale_hours=24, now=reference)
        self.assertNotIn("stale_record", default_report["issue_counts"])
        self.assertIn("stale_record", stale_report["issue_counts"])

    def test_csv_requires_expected_headers(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.csv"
            path.write_text("order_id,order_status\nX,received\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_orders(path)


if __name__ == "__main__":
    unittest.main()
