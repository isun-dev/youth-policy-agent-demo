from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import requests

from app.youthcenter_client import (
    YouthCenterAPIError,
    YouthCenterClient,
    load_youthcenter_config,
)


class YouthCenterClientTest(unittest.TestCase):
    def test_loads_youthcenter_config_from_env(self) -> None:
        env = {
            "YOUTHCENTER_API_KEY": "test-key",
            "YOUTHCENTER_API_BASE_URL": "https://api.example.com",
        }

        with patch.dict(os.environ, env, clear=True):
            config = load_youthcenter_config()

        self.assertEqual(config.api_key, "test-key")
        self.assertEqual(config.base_url, "https://api.example.com")

    def test_rejects_base_url_with_query_string(self) -> None:
        env = {
            "YOUTHCENTER_API_KEY": "test-key",
            "YOUTHCENTER_API_BASE_URL": "https://api.example.com?apiKeyNm=test-key",
        }

        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError) as context:
                load_youthcenter_config()

        message = str(context.exception)
        self.assertNotIn("test-key", message)
        self.assertIn("쿼리스트링", message)

    @patch("app.youthcenter_client.requests.get")
    def test_fetch_policies_uses_configured_key_param(self, mock_get) -> None:
        mock_get.return_value.text = "<response />"
        mock_get.return_value.raise_for_status.return_value = None

        client = YouthCenterClient(
            api_key="test-key",
            base_url="https://api.example.com",
        )

        xml_text = client.fetch_policies(page=2, page_size=10)

        self.assertEqual(xml_text, "<response />")
        mock_get.assert_called_once_with(
            "https://api.example.com",
            params={
                "apiKeyNm": "test-key",
                "pageNum": 2,
                "pageSize": 10,
                "rtnType": "json",
            },
            timeout=10,
        )

    @patch("app.youthcenter_client.requests.get")
    def test_fetch_policies_redacts_key_from_request_errors(self, mock_get) -> None:
        mock_get.side_effect = requests.RequestException(
            "failed for https://api.example.com?apiKeyNm=real-secret&pageNum=1"
        )

        client = YouthCenterClient(
            api_key="real-secret",
            base_url="https://api.example.com",
        )

        with self.assertRaises(YouthCenterAPIError) as context:
            client.fetch_policies()

        message = str(context.exception)
        self.assertNotIn("real-secret", message)
        self.assertIn("apiKeyNm=[REDACTED]", message)

    @patch("app.youthcenter_client.requests.get")
    def test_fetch_policies_redacts_key_from_http_errors(self, mock_get) -> None:
        mock_response = mock_get.return_value
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            "401 Client Error for url: https://api.example.com?apiKeyNm=real-secret&pageNum=1"
        )

        client = YouthCenterClient(
            api_key="real-secret",
            base_url="https://api.example.com",
        )

        with self.assertRaises(YouthCenterAPIError) as context:
            client.fetch_policies()

        message = str(context.exception)
        self.assertNotIn("real-secret", message)
        self.assertIn("apiKeyNm=[REDACTED]", message)
        self.assertIn("HTTP 상태: 401", message)


if __name__ == "__main__":
    unittest.main()
