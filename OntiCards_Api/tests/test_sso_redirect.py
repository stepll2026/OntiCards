import unittest

from core.sso_redirect import is_allowed_redirect, with_access_token_fragment


class SSORedirectTest(unittest.TestCase):
    def test_token_is_in_fragment_and_existing_query_is_preserved(self):
        redirect = with_access_token_fragment(
            "https://console.example.test/login?lng=en", "signed.token/value"
        )

        self.assertEqual(
            redirect,
            "https://console.example.test/login?lng=en#access_token=signed.token%2Fvalue",
        )
        self.assertNotIn("?access_token", redirect)

    def test_existing_fragment_is_preserved(self):
        redirect = with_access_token_fragment(
            "https://console.example.test/login#source=sso", "token"
        )

        self.assertEqual(
            redirect,
            "https://console.example.test/login#source=sso&access_token=token",
        )

    def test_redirect_allowlist_matches_origins_and_allows_local_paths(self):
        allowed = ["https://console.example.test", "http://localhost:9107"]

        self.assertTrue(is_allowed_redirect("/overview", allowed))
        self.assertTrue(is_allowed_redirect("https://console.example.test/login", allowed))
        self.assertFalse(is_allowed_redirect("//attacker.example/collect", allowed))
        self.assertFalse(is_allowed_redirect("https://attacker.example/collect", allowed))
        self.assertFalse(is_allowed_redirect("javascript:alert(1)", allowed))


if __name__ == "__main__":
    unittest.main()
