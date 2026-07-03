from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import requests

from app.gyeonggi_client import GyeonggiAPIError, GyeonggiClient, load_gyeonggi_config


class GyeonggiClientTest(unittest.TestCase):
    def test_loads_gyeonggi_config_from_env(self) -> None:
        env = {
            "GYEONGGI_API_KEY": "test-key",
            "GYEONGGI_API_BASE_URL": "https://openapi.gg.go.kr",
        }

        with patch.dict(os.environ, env, clear=True):
            config = load_gyeonggi_config()

        self.assertEqual(config.api_key, "test-key")
        self.assertEqual(config.base_url, "https://openapi.gg.go.kr")

    def test_rejects_base_url_with_query_string(self) -> None:
        env = {
            "GYEONGGI_API_KEY": "test-key",
            "GYEONGGI_API_BASE_URL": "https://openapi.gg.go.kr?KEY=test-key",
        }

        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError) as context:
                load_gyeonggi_config()

        message = str(context.exception)
        self.assertNotIn("test-key", message)
        self.assertIn("쿼리스트링", message)

    @patch("app.gyeonggi_client.requests.get")
    def test_fetch_endpoint_uses_gyeonggi_openapi_params(self, mock_get) -> None:
        mock_get.return_value.text = '{"JobFndtnEduTraing": []}'
        mock_get.return_value.raise_for_status.return_value = None

        client = GyeonggiClient(api_key="test-key", base_url="https://openapi.gg.go.kr")

        response_text = client.fetch_endpoint("JobFndtnEduTraing", page=2, page_size=10)

        self.assertEqual(response_text, '{"JobFndtnEduTraing": []}')
        mock_get.assert_called_once_with(
            "https://openapi.gg.go.kr/JobFndtnEduTraing",
            params={
                "KEY": "test-key",
                "Type": "json",
                "pIndex": 2,
                "pSize": 10,
            },
            timeout=10,
        )

    @patch("app.gyeonggi_client.requests.get")
    def test_fetch_endpoint_redacts_key_from_request_errors(self, mock_get) -> None:
        mock_get.side_effect = requests.RequestException(
            "failed for https://openapi.gg.go.kr/JobFndtnEduTraing?KEY=real-secret"
        )
        client = GyeonggiClient(api_key="real-secret", base_url="https://openapi.gg.go.kr")

        with self.assertRaises(GyeonggiAPIError) as context:
            client.fetch_endpoint("JobFndtnEduTraing")

        self.assertNotIn("real-secret", str(context.exception))


if __name__ == "__main__":
    unittest.main()
