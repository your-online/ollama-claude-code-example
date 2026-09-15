"""Synthetic commerce fixture generation; no model or network access."""

import datetime as dt
import os
import random
import secrets
import sqlite3
import tempfile
from pathlib import Path


def generate_database(path: Path, seed: int = 20260915) -> None:
    """Create a complete database atomically, refusing to replace existing data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    fd, temporary = tempfile.mkstemp(prefix=".fixture-", suffix=".sqlite", dir=path.parent)
    os.close(fd)
    temporary = Path(temporary)
    try:
        _populate(temporary, seed)
        # Atomic no-clobber publication, including concurrent init processes.
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _populate(path: Path, seed: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    con = sqlite3.connect(path)
    try:
        con.executescript((Path(__file__).with_name("schema.sql")).read_text())

        def add(table, *values):
            con.execute(f"INSERT INTO {table} VALUES ({','.join('?' for _ in values)})", values)

        regions = [
            ("Noord", "NL"),
            ("Zuid", "NL"),
            ("West", "NL"),
            ("Oost", "NL"),
            ("Vlaanderen", "BE"),
            ("Brussel", "BE"),
        ]
        for i, (name, country) in enumerate(regions, 1):
            add("regions", i, name, country)
        for i in range(1, 19):
            add("employees", i, f"Accountmanager {i:02}", (i - 1) % 6 + 1)
        for i in range(1, 181):
            add(
                "customers",
                i,
                f"{rng.choice(['Atlas', 'Meridiaan', 'Horizon', 'Nova', 'Delta'])} Demo {i:03} BV",
                rng.choice(["SMB", "Midmarket", "Enterprise"]),
                rng.randint(1, 6),
                rng.randint(1, 18),
            )
        cats = ["Laptops", "Schermen", "Netwerk", "Opslag", "Accessoires", "Vergaderen"]
        for i, name in enumerate(cats, 1):
            add("categories", i, name)
        for i in range(1, 13):
            add("suppliers", i, f"Demo Supplier {i:02}", rng.choice(["NL", "BE", "DE", "FR"]))
        products = {}
        for i in range(1, 97):
            cat = (i - 1) % 6 + 1
            price = rng.randint(1500, 240000)
            cost = price * rng.randint(40, 80) // 100
            products[i] = (price, cost)
            add(
                "products",
                i,
                f"SKU-{i:04}",
                f"{cats[cat - 1]} Pro {i:03}",
                cat,
                rng.randint(1, 12),
                price,
                cost,
            )
        for i, name in enumerate(["Utrecht", "Eindhoven", "Antwerpen"], 1):
            add("warehouses", i, name, [3, 2, 5][i - 1])
            for p in products:
                add("inventory", p, i, rng.randint(0, 120), rng.randint(10, 35))
        item_id = payment_id = shipment_id = return_id = ticket_id = 0
        start = dt.date(2025, 1, 1)
        for oid in range(1, 2401):
            customer = rng.randint(1, 180)
            date = start + dt.timedelta(days=rng.randrange(608))
            status = rng.choices(["completed", "processing", "cancelled"], [85, 9, 6])[0]
            add(
                "orders",
                oid,
                customer,
                date.isoformat(),
                status,
                rng.choice(["web", "sales", "partner"]),
            )
            total = 0
            for pid in rng.sample(list(products), rng.randint(1, 6)):
                item_id += 1
                price, cost = products[pid]
                qty, discount = rng.randint(1, 12), rng.choice([0, 0, 0, 500, 1000, 1500])
                line = (qty * price * (10000 - discount) + 5000) // 10000
                total += line
                add("order_items", item_id, oid, pid, qty, price, cost, discount)
                if status == "completed" and rng.random() < 0.065:
                    return_id += 1
                    returned = rng.randint(1, qty)
                    refund = (returned * price * (10000 - discount) + 5000) // 10000
                    add(
                        "returns",
                        return_id,
                        item_id,
                        (date + dt.timedelta(days=20)).isoformat(),
                        returned,
                        refund,
                        rng.choice(["defect", "verkeerd besteld", "beschadigd"]),
                    )
            if status != "cancelled":
                paid = int(total * rng.choice([1, 1, 1, 1, 0.5, 0.75, 0]))
                if paid:
                    parts = [paid] if rng.random() < 0.7 else [paid // 2, paid - paid // 2]
                    for part in parts:
                        payment_id += 1
                        add(
                            "payments",
                            payment_id,
                            oid,
                            (date + dt.timedelta(days=7)).isoformat(),
                            part,
                            rng.choice(["bank", "card", "ideal"]),
                        )
                if status == "completed":
                    # Some orders have split shipments: joining raw tables can double count.
                    for _ in range(rng.choice([1, 1, 1, 2])):
                        shipment_id += 1
                        add(
                            "shipments",
                            shipment_id,
                            oid,
                            rng.randint(1, 3),
                            (date + dt.timedelta(days=1)).isoformat(),
                            (date + dt.timedelta(days=4)).isoformat(),
                            (date + dt.timedelta(days=rng.randint(2, 8))).isoformat(),
                            rng.choice(["DHL", "PostNL", "DPD"]),
                        )
            if rng.random() < 0.24:
                ticket_id += 1
                add(
                    "tickets",
                    ticket_id,
                    customer,
                    oid,
                    (date + dt.timedelta(days=5)).isoformat(),
                    rng.choice(["open", "pending", "closed"]),
                    rng.choice(["low", "medium", "high"]),
                    rng.choice(
                        ["Levering vertraagd", "Factuurvraag", "Product defect", "Retourstatus"]
                    ),
                )
        add("audit_challenges", "blind-test", secrets.token_hex(12))
        con.commit()
        assert not con.execute("PRAGMA foreign_key_check").fetchall()
    except BaseException:
        con.close()
        path.unlink(missing_ok=True)
        raise
    finally:
        con.close()
