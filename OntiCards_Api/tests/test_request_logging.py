import unittest

from werkzeug.datastructures import MultiDict

from core.request_logging import redact_mapping, redact_url


class RequestLoggingTest(unittest.TestCase):
    def test_redact_url_hides_sensitive_values_and_preserves_other_query_data(self):
        safe = redact_url(
            "https://example.test/path?page=2&access_token=abc123&API-KEY=secret-value"
        )

        self.assertIn("page=2", safe)
        self.assertNotIn("abc123", safe)
        self.assertNotIn("secret-value", safe)
        self.assertEqual(safe.count("%3Credacted%3E"), 2)

    def test_redact_url_handles_repeated_and_blank_parameters(self):
        safe = redact_url("https://example.test/path?tag=a&tag=b&token=&empty=")

        self.assertIn("tag=a&tag=b", safe)
        self.assertIn("token=%3Credacted%3E", safe)
        self.assertIn("empty=", safe)

    def test_redact_mapping_supports_multidict_without_mutating_it(self):
        form = MultiDict([
            ("username", "alice"),
            ("password", "correct horse battery staple"),
            ("tag", "one"),
            ("tag", "two"),
        ])

        safe = redact_mapping(form)

        self.assertEqual(safe["username"], "alice")
        self.assertEqual(safe["password"], "<redacted>")
        self.assertEqual(safe["tag"], ["one", "two"])
        self.assertEqual(form["password"], "correct horse battery staple")


if __name__ == "__main__":
    unittest.main()
