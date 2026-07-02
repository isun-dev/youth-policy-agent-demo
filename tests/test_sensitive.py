from __future__ import annotations

import unittest

from app.sensitive import redact_sensitive_text


class SensitiveTextTest(unittest.TestCase):
    def test_redacts_known_secret_assignments(self) -> None:
        message = (
            "OPENAI_API_KEY=sk-test YOUTHCENTER_API_KEY=youth-secret "
            "url=https://api.example.com?apiKeyNm=query-secret"
        )

        redacted = redact_sensitive_text(message)

        self.assertNotIn("sk-test", redacted)
        self.assertNotIn("youth-secret", redacted)
        self.assertNotIn("query-secret", redacted)
        self.assertEqual(redacted.count("[REDACTED]"), 3)

    def test_redacts_secret_values_from_environment(self) -> None:
        redacted = redact_sensitive_text(
            "request failed with hidden-env-value",
            environ={"OPENAI_API_KEY": "hidden-env-value", "NORMAL_SETTING": "visible"},
        )

        self.assertNotIn("hidden-env-value", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_redacts_bearer_tokens(self) -> None:
        redacted = redact_sensitive_text("Authorization: Bearer sk-live-secret")

        self.assertNotIn("sk-live-secret", redacted)
        self.assertIn("Bearer [REDACTED]", redacted)


if __name__ == "__main__":
    unittest.main()
