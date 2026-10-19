# Payu Operations Agent

A small, read-only MVP for reviewing order-operation exports and highlighting records that need human attention.

> **Current scope:** CSV-in, report-out. This repository is not connected to Payu's live backend. Sample rows are synthetic. It does not change orders, contact customers, process payments, or assume Payu's real status rules.

## What it checks

- Missing values in core operational fields
- Duplicate order IDs
- Optionally stale records, only when you provide a staleness threshold
- A concise JSON report and a human-readable terminal summary

It deliberately does **not** infer payment, stock, fulfillment, or delivery contradictions because Payu's actual status values and transition rules have not yet been verified.

## Requirements

- Python 3.10+
- No third-party packages required

## Quick start

Run against the included synthetic sample:

```bash
python -m payu_agent analyze data/sample_orders.csv
```

Write a JSON report:

```bash
python -m payu_agent analyze data/sample_orders.csv --json-out report.json
```

Flag orders not updated within 24 hours (uses the current machine's local time):

```bash
python -m payu_agent analyze data/sample_orders.csv --stale-hours 24
```

For repeatable tests of staleness, pass an explicit reference time:

```bash
python -m payu_agent analyze data/sample_orders.csv --stale-hours 24 --now 2026-10-19T12:00:00+07:00
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

## CSV input fields

Expected headers:

- `order_id`
- `created_at`
- `order_status`
- `payment_status`
- `stock_status`
- `fulfillment_status`
- `delivery_status`
- `item_total`
- `delivery_fee`
- `estimated_item_margin`
- `last_updated_at`
- `issue_note`

Dates should be ISO 8601 (for example, `2026-10-19T10:00:00+07:00`). Monetary columns should contain numeric values when known. Keep customer names, phone numbers, addresses, OTPs, and payment credentials out of exports unless there is a clear, necessary, approved reason to include them.

## Safety and limitations

- Read-only: reads a CSV and prints/writes a report.
- No network calls, database credentials, or external side effects.
- Missing fields are warnings, not proof that an order is broken.
- A stale record is only flagged when `--stale-hours` is explicitly set.
- This is an operational review helper, not an autonomous agent connected to live systems.

## Next milestone

Map the actual Payu backend schema and status lifecycle from verified code/schema, then add documented rules with tests. Do not connect production data until the mapping is reviewed and access is explicitly configured.
