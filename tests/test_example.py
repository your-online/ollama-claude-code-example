import hashlib
import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from local_demo.audit import expected_top_customers, verify_query
from local_demo.cli import main
from local_demo.database import generate_database
from local_demo.runtime import (
    launch,
    launch_command,
    launch_environment,
    require_local_model,
    setup_model,
)

REFERENCE_QUERY = """
WITH lines AS (
  SELECT oi.order_id,
    SUM(ROUND(oi.quantity * oi.unit_price_cents * (10000-oi.discount_bps)/10000.0)) cents
  FROM order_items oi GROUP BY oi.order_id
), refunds AS (
  SELECT oi.order_id, SUM(r.refund_cents) cents
  FROM returns r JOIN order_items oi ON oi.id=r.order_item_id GROUP BY oi.order_id
)
SELECT c.name customer_name, reg.name region_name,
       SUM(lines.cents-COALESCE(refunds.cents,0))/100.0 net_revenue_eur
FROM orders o JOIN customers c ON c.id=o.customer_id
JOIN regions reg ON reg.id=c.region_id JOIN lines ON lines.order_id=o.id
LEFT JOIN refunds ON refunds.order_id=o.id
WHERE o.status='completed' AND o.ordered_at>='2026-01-01' AND o.ordered_at<'2026-04-01'
GROUP BY c.id ORDER BY net_revenue_eur DESC, c.id LIMIT 5
"""


class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.workspace = Path(cls.temp.name)
        cls.database = cls.workspace / "data" / "commerce.sqlite"
        generate_database(cls.database)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_fixture_integrity_and_nontrivial_data(self):
        con = sqlite3.connect(self.database)
        try:
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(
                con.execute("SELECT COUNT(*) FROM sqlite_schema WHERE type='table'").fetchone()[0],
                15,
            )
            self.assertEqual(con.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 2400)
            self.assertGreater(con.execute("SELECT COUNT(*) FROM order_items").fetchone()[0], 7000)
        finally:
            con.close()

    def test_business_data_reproducible_but_challenge_random(self):
        second = self.workspace / "second.sqlite"
        generate_database(second)
        con1, con2 = sqlite3.connect(self.database), sqlite3.connect(second)
        try:
            self.assertEqual(
                con1.execute("SELECT * FROM orders").fetchall(),
                con2.execute("SELECT * FROM orders").fetchall(),
            )
            self.assertNotEqual(
                con1.execute(
                    "SELECT secret_code FROM audit_challenges WHERE label='blind-test'"
                ).fetchone(),
                con2.execute(
                    "SELECT secret_code FROM audit_challenges WHERE label='blind-test'"
                ).fetchone(),
            )
        finally:
            con1.close()
            con2.close()

    def test_existing_database_never_replaced(self):
        before = self.database.read_bytes()
        with self.assertRaises(FileExistsError):
            generate_database(self.database, 7)
        self.assertEqual(before, self.database.read_bytes())

    def test_candidate_matches_independent_oracle(self):
        self.assertTrue(verify_query(self.database, REFERENCE_QUERY)["matches"])

    def test_wrong_refund_and_status_logic_is_detected(self):
        for query in [
            REFERENCE_QUERY.replace("COALESCE(refunds.cents,0)", "0"),
            REFERENCE_QUERY.replace("o.status='completed'", "o.status!='completed'"),
            REFERENCE_QUERY.replace("10000-oi.discount_bps", "10000"),
        ]:
            with self.subTest(query=query):
                self.assertFalse(verify_query(self.database, query)["matches"])

    def test_auditor_blocks_writes_and_attachment(self):
        before = hashlib.sha256(self.database.read_bytes()).digest()
        for query in [
            "DELETE FROM orders",
            "ATTACH DATABASE ':memory:' AS other",
            "PRAGMA query_only=OFF",
            "SELECT 1; SELECT 2",
        ]:
            with self.subTest(query=query), self.assertRaises((sqlite3.Error, sqlite3.Warning)):
                verify_query(self.database, query)
        self.assertEqual(before, hashlib.sha256(self.database.read_bytes()).digest())

    def test_fresh_code_roundtrip_no_model(self):
        with (
            patch("local_demo.cli.secrets.token_hex", return_value="abc123"),
            redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(main(["--workspace", str(self.workspace), "challenge"]), 0)
            self.assertNotIn("abc123", output.getvalue())
            self.assertEqual(main(["--workspace", str(self.workspace), "check-code", "abc123"]), 0)
            self.assertEqual(main(["--workspace", str(self.workspace), "check-code", "wrong"]), 1)


class RoundingAndAttributionTests(unittest.TestCase):
    def test_half_cent_and_late_refund_and_cancelled_order(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "small.sqlite"
            con = sqlite3.connect(db)
            con.executescript(
                (Path(__file__).resolve().parents[1] / "local_demo" / "schema.sql").read_text()
            )
            con.execute("INSERT INTO regions VALUES (1,'West','NL')")
            con.execute("INSERT INTO customers VALUES (1,'Example','SMB',1,NULL)")
            con.execute("INSERT INTO products VALUES (1,'X','X',NULL,NULL,101,1)")
            con.executemany(
                "INSERT INTO orders VALUES (?,1,?,?,'web')",
                [
                    (1, "2026-03-31", "completed"),
                    (2, "2026-04-01", "completed"),
                    (3, "2026-02-01", "cancelled"),
                ],
            )
            con.executemany(
                "INSERT INTO order_items VALUES (?,?,1,1,101,1,5000)", [(1, 1), (2, 2), (3, 3)]
            )
            con.execute("INSERT INTO returns VALUES (1,1,'2026-04-20',1,20,'test')")
            con.commit()
            con.close()
            # 101 cents at 50% = 50.5 → 51; late refund subtracts 20; others excluded.
            self.assertEqual(
                expected_top_customers(db),
                [{"customer_name": "Example", "region_name": "West", "net_cents": 31}],
            )


class RuntimeTests(unittest.TestCase):
    def test_cloud_and_remote_aliases_are_rejected(self):
        for name, info in [
            ("model:cloud", {}),
            ("local", {"remote_host": "https://example.com"}),
            ("local", {"remote_model": "remote"}),
        ]:
            with (
                self.subTest(name=name, info=info),
                patch("local_demo.runtime.ollama_api", return_value=info),
            ):
                with self.assertRaises(RuntimeError):
                    require_local_model(name)

    def test_environment_is_local_and_does_not_mutate_parent(self):
        parent = {
            "ANTHROPIC_API_KEY": "secret",
            "ANTHROPIC_CUSTOM_HEADERS": "secret",
            "CLAUDE_CODE_USE_VERTEX": "1",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "https://example.com",
            "PATH": "/bin",
        }
        env = launch_environment(Path("/tmp/example"), parent)
        self.assertEqual(parent["ANTHROPIC_API_KEY"], "secret")
        self.assertEqual(env["ANTHROPIC_API_KEY"], "ollama")
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "http://127.0.0.1:11434")
        self.assertNotIn("ANTHROPIC_CUSTOM_HEADERS", env)
        self.assertNotIn("CLAUDE_CODE_USE_VERTEX", env)
        self.assertNotIn("OTEL_EXPORTER_OTLP_ENDPOINT", env)
        command = launch_command()
        self.assertEqual(command[command.index("--permission-mode") + 1], "manual")
        self.assertNotIn("--dangerously-skip-permissions", command)

    def test_other_loaded_model_blocks_launch_before_inference(self):
        with (
            patch("local_demo.runtime.require_commands"),
            patch("local_demo.runtime.require_local_model"),
            patch(
                "local_demo.runtime.ollama_api",
                return_value={"models": [{"name": "another-model"}]},
            ),
            patch("local_demo.runtime.subprocess.call") as call,
        ):
            with self.assertRaisesRegex(RuntimeError, "Other models"):
                launch(Path("/tmp/example"))
            call.assert_not_called()

    def test_setup_only_creates_metadata_from_existing_local_weights(self):
        captured = []

        def capture(command, **kwargs):
            captured.append(Path(command[-1]).read_text())

        with (
            patch("local_demo.runtime.require_commands"),
            patch("local_demo.runtime.require_local_model") as local,
            patch("local_demo.runtime.subprocess.run", side_effect=capture) as run,
        ):
            setup_model()
            local.assert_called_once_with("gpt-oss:20b")
            self.assertEqual(
                run.call_args.args[0][:4], ["ollama", "create", "local-claude-example", "-f"]
            )
            self.assertIn("PARAMETER num_ctx 16384", captured[0])


if __name__ == "__main__":
    unittest.main()
