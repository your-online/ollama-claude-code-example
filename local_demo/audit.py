"""An independent integer-arithmetic oracle and read-only SQL comparison."""

import sqlite3
import time
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path


def read_only(path):
    con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def expected_top_customers(path):
    """Compute Q1 2026 results from raw rows, independently of the submitted SQL."""
    con = read_only(path)
    try:
        orders = {r["id"]: dict(r) for r in con.execute("SELECT * FROM orders")}
        items = {r["id"]: dict(r) for r in con.execute("SELECT * FROM order_items")}
        customers = {r["id"]: dict(r) for r in con.execute("SELECT * FROM customers")}
        regions = {r["id"]: r["name"] for r in con.execute("SELECT * FROM regions")}
        eligible = {
            oid
            for oid, o in orders.items()
            if o["status"] == "completed" and "2026-01-01" <= o["ordered_at"] < "2026-04-01"
        }
        totals = defaultdict(int)
        for oid in eligible:
            totals[orders[oid]["customer_id"]] += 0
        for item in items.values():
            if item["order_id"] in eligible:
                cents = (
                    item["quantity"] * item["unit_price_cents"] * (10000 - item["discount_bps"])
                    + 5000
                ) // 10000
                totals[orders[item["order_id"]]["customer_id"]] += cents
        for refund in con.execute("SELECT * FROM returns"):
            oid = items[refund["order_item_id"]]["order_id"]
            if oid in eligible:
                totals[orders[oid]["customer_id"]] -= refund["refund_cents"]
        ranked = sorted(totals, key=lambda cid: (-totals[cid], cid))[:5]
        return [
            {
                "customer_name": customers[cid]["name"],
                "region_name": regions[customers[cid]["region_id"]],
                "net_cents": totals[cid],
            }
            for cid in ranked
        ]
    finally:
        con.close()


def execute_candidate(path, sql):
    if len(sql) > 20000:
        raise ValueError("SQL exceeds the 20,000-character limit.")
    con = read_only(path)
    allowed = {
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_RECURSIVE,
    }

    def authorize(action, first, second, database, source):
        if action not in allowed:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION and (second or "").lower() in {
            "load_extension",
            "readfile",
            "writefile",
            "randomblob",
            "zeroblob",
        }:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    con.set_authorizer(authorize)
    deadline = time.monotonic() + 2
    con.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    if hasattr(con, "setlimit"):
        con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 200000)
    try:
        rows = con.execute(sql).fetchmany(6)
        if len(rows) != 5:
            raise ValueError("The candidate must return exactly five rows.")
        result = []
        for row in rows:
            try:
                cents = Decimal(str(row["net_revenue_eur"])) * 100
                if not cents.is_finite() or cents != cents.to_integral_value():
                    raise ValueError("Return amounts rounded to whole cents.")
                result.append(
                    {
                        "customer_name": row["customer_name"],
                        "region_name": row["region_name"],
                        "net_cents": int(cents),
                    }
                )
            except (IndexError, InvalidOperation) as exc:
                raise ValueError(
                    "Required columns: customer_name, region_name, net_revenue_eur."
                ) from exc
        return result
    finally:
        con.close()


def verify_query(path, sql):
    expected = expected_top_customers(path)
    actual = execute_candidate(path, sql)
    return {"matches": actual == expected, "expected": expected, "actual": actual}
