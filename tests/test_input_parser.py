from __future__ import annotations

import unittest

from app.input_parser import normalize_employment_status


class InputParserTest(unittest.TestCase):
    def test_normalizes_job_seeker_aliases(self) -> None:
        self.assertEqual(normalize_employment_status("취준생"), "job_seeker")
        self.assertEqual(normalize_employment_status("이직 준비 중"), "job_seeker")

    def test_normalizes_unemployed_aliases(self) -> None:
        self.assertEqual(normalize_employment_status("백수"), "unemployed")
        self.assertEqual(normalize_employment_status("무직"), "unemployed")

    def test_normalizes_employed_aliases(self) -> None:
        self.assertEqual(normalize_employment_status("재직 중"), "employed")
        self.assertEqual(normalize_employment_status("직장인"), "employed")

    def test_unknown_status_returns_none(self) -> None:
        self.assertIsNone(normalize_employment_status("알 수 없음"))


if __name__ == "__main__":
    unittest.main()
