from __future__ import annotations

import unittest
from unittest.mock import patch

from app.policy_detail_tool import PolicyDetailTool


class PolicyDetailToolTest(unittest.TestCase):
    @patch("app.policy_detail_tool.requests.get")
    def test_fetch_extracts_visible_text_from_html(self, mock_get) -> None:
        mock_response = mock_get.return_value
        mock_response.text = """
        <html>
          <head><style>.hidden { display: none; }</style></head>
          <body>
            <script>window.secret = "ignore";</script>
            <h1>청년 취업 지원</h1>
            <p>지원대상: 경기도 거주 미취업 청년</p>
            <p>신청기간: 2026년 7월 1일 ~ 7월 31일</p>
          </body>
        </html>
        """
        mock_response.encoding = "utf-8"
        mock_response.apparent_encoding = "utf-8"
        mock_response.raise_for_status.return_value = None

        detail = PolicyDetailTool().fetch("https://example.com/detail")

        self.assertEqual(detail.fetch_status, "ok")
        self.assertIn("청년 취업 지원", detail.plain_text)
        self.assertIn("지원대상", detail.plain_text)
        self.assertNotIn("window.secret", detail.plain_text)
        mock_get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
