from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.youthcenter_client import YouthCenterClient, load_youthcenter_config


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


if __name__ == "__main__":
    unittest.main()
