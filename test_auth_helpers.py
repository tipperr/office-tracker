import unittest

from auth_helpers import (
    build_signup_credentials,
    normalize_email,
    validate_signup,
)


class AuthHelpersTests(unittest.TestCase):
    def test_normalize_email(self):
        self.assertEqual(normalize_email(" Friend@Example.COM "), "friend@example.com")

    def test_validate_signup_rejects_invalid_email(self):
        self.assertEqual(
            validate_signup("not-an-email", "password123", "password123"),
            "Enter a valid email address.",
        )

    def test_validate_signup_rejects_short_password(self):
        self.assertEqual(
            validate_signup("friend@example.com", "short", "short"),
            "Use at least 8 characters for your password.",
        )

    def test_validate_signup_rejects_mismatched_passwords(self):
        self.assertEqual(
            validate_signup("friend@example.com", "password123", "password456"),
            "Passwords do not match.",
        )

    def test_build_signup_credentials_includes_optional_fields(self):
        self.assertEqual(
            build_signup_credentials(
                " Friend@Example.COM ",
                "password123",
                "  Friend Name ",
                "https://example.com",
            ),
            {
                "email": "friend@example.com",
                "password": "password123",
                "options": {
                    "data": {"full_name": "Friend Name"},
                    "email_redirect_to": "https://example.com",
                },
            },
        )

    def test_build_signup_credentials_omits_empty_options(self):
        self.assertEqual(
            build_signup_credentials("friend@example.com", "password123"),
            {
                "email": "friend@example.com",
                "password": "password123",
            },
        )


if __name__ == "__main__":
    unittest.main()
