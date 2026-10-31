"""Keep application entry points and persistent identifiers consistent."""
import unittest
from keymousebattery import identity, autostart, cli


class IdentityTests(unittest.TestCase):
    def test_independent_identity(self):
        self.assertEqual(identity.APP_ID, "KeyMouseBattery")
        self.assertEqual(autostart.VALUE_NAME, identity.APP_ID)
        self.assertIn(identity.APP_ID, identity.MUTEX_NAME)
        self.assertIn(identity.APP_ID, identity.SHOW_EVENT_NAME)
        self.assertEqual(identity.LOG_FILE, "keymousebattery.log")

    def test_source_entry_exists(self):
        self.assertTrue((identity.base_dir() / "KeyMouseBattery.pyw").is_file())

    def test_version_uses_project_identity(self):
        output = "\n".join(cli.version())
        self.assertIn(identity.APP_ID, output)
        self.assertIn(identity.PROJECT_URL, output)
        self.assertNotIn("非官方", output)
