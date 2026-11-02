"""Safety tests for three-lane routing without network calls."""
import unittest
from scripts.jarvis_env_selector import ACTIONS, resolve


class TestEnvironmentRouting(unittest.TestCase):
    def test_all_actions_have_requirements(self):
        for action in ACTIONS:
            env, req = resolve(action)
            self.assertIn(env, {"raw", "qa", "analytics"})
            self.assertTrue(req.endswith((".lock", ".txt")))

    def test_raw_production_unchanged(self):
        self.assertEqual(resolve("source_download"), ("raw", "requirements-qa.lock"))
        self.assertEqual(resolve("raw_repair"), ("raw", "requirements-qa.lock"))

    def test_quality_routes_to_qa(self):
        self.assertEqual(resolve("quality_validation")[0], "qa")

    def test_indicator_routes_to_analytics(self):
        self.assertEqual(resolve("indicator_calculation")[0], "analytics")

    def test_unknown_work_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve("arbitrary_shell_command")


if __name__ == "__main__":
    unittest.main()
