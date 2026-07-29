import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).with_name("app.py")


class AuthUiTests(unittest.TestCase):
    def test_login_page_renders_sign_in_and_create_account_forms(self):
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()

        self.assertEqual([title.value for title in app.title], ["Desk-O-Meter"])
        self.assertEqual([tab.label for tab in app.tabs], ["Sign in", "Create account"])
        self.assertEqual(len(app.exception), 0)

    def test_invalid_signup_is_rejected_before_contacting_supabase(self):
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.text_input(key="signup_email").set_value("friend@example.com")
        app.text_input(key="signup_password").set_value("password123")
        app.text_input(key="signup_password_confirmation").set_value("different123")

        app.button[1].click().run()

        self.assertEqual([error.value for error in app.error], ["Passwords do not match."])
        self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
