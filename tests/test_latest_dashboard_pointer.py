# -*- coding: utf-8 -*-
"""Tests for reports/latest_dashboard pointer helpers."""

import tempfile
import unittest
from pathlib import Path

from src.notification import is_dashboard_report_filename, update_latest_dashboard_pointer


class LatestDashboardPointerTests(unittest.TestCase):
    def test_is_dashboard_report_filename(self) -> None:
        self.assertTrue(
            is_dashboard_report_filename("report_20260516_120000_stocks3.md")
        )
        self.assertFalse(is_dashboard_report_filename("report_20260516_120000.md"))
        self.assertFalse(
            is_dashboard_report_filename("market_review_20260516_120000.md")
        )
        self.assertFalse(is_dashboard_report_filename(""))

    def test_skips_non_dashboard_names(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td) / "reports"
            rd.mkdir()
            saved = rd / "notes.md"
            saved.write_text("x", encoding="utf-8")
            update_latest_dashboard_pointer(saved, reports_dir=rd)
            self.assertFalse((rd / "latest_dashboard.md").exists())
            self.assertFalse((rd / ".latest_dashboard").exists())

    def test_updates_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td) / "reports"
            rd.mkdir()
            saved = rd / "report_20260516_120000_stocks2.md"
            saved.write_text("body", encoding="utf-8")
            update_latest_dashboard_pointer(saved, reports_dir=rd)

            link = rd / "latest_dashboard.md"
            fallback = rd / ".latest_dashboard"

            if link.exists() and link.is_symlink():
                self.assertEqual(Path(link.readlink()).name, saved.name)
                self.assertFalse(fallback.exists())
                self.assertEqual(link.resolve(), saved.resolve())
            else:
                self.assertTrue(fallback.is_file())
                text = fallback.read_text(encoding="utf-8").strip()
                self.assertEqual(text, str(saved.resolve()))


if __name__ == "__main__":
    unittest.main()
