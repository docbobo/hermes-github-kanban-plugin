import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "github-project-manage.py"
ROUTE_SUFFIX = "/webhooks/github-issues-to-kanban"


def load_module():
    spec = importlib.util.spec_from_file_location("github_project_manage", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ResolveWebhookUrlTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config_path = os.path.join(self.tmp.name, "config.json")
        self.module = load_module()
        setattr(self.module, "CONFIG_PATH", self.config_path)

    def write_config(self, config):
        with open(self.config_path, "w") as f:
            json.dump(config, f)

    def test_configured_base_url(self):
        self.write_config({"webhook_base_url": "https://kanban.example.com"})
        self.assertEqual(
            self.module.resolve_webhook_url(),
            f"https://kanban.example.com{ROUTE_SUFFIX}",
        )

    def test_trailing_slash_stripped(self):
        self.write_config({"webhook_base_url": "https://kanban.example.com/"})
        self.assertEqual(
            self.module.resolve_webhook_url(),
            f"https://kanban.example.com{ROUTE_SUFFIX}",
        )

    def test_full_url_in_config_not_duplicated(self):
        full = f"https://kanban.example.com{ROUTE_SUFFIX}"
        self.write_config({"webhook_base_url": full})
        self.assertEqual(self.module.resolve_webhook_url(), full)

    def test_unset_returns_none_with_actionable_error(self):
        self.write_config({})
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertIsNone(self.module.resolve_webhook_url())
        self.assertIn("webhook --set-url", stderr.getvalue())

    def test_override_base_url_appends_route(self):
        self.write_config({})
        self.assertEqual(
            self.module.resolve_webhook_url("https://override.example.com/"),
            f"https://override.example.com{ROUTE_SUFFIX}",
        )

    def test_override_full_url_is_kept(self):
        self.write_config({})
        full = f"https://override.example.com{ROUTE_SUFFIX}"
        self.assertEqual(self.module.resolve_webhook_url(full), full)

    def test_override_requires_absolute_http_url(self):
        self.write_config({})
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertIsNone(self.module.resolve_webhook_url("kanban.example.com"))
        self.assertIn("absolute http(s) URL", stderr.getvalue())


class WebhookUrlCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = self.tmp.name
        self.config_dir = os.path.join(self.home, ".hermes", "scripts")
        os.makedirs(self.config_dir)
        self.config_path = os.path.join(
            self.config_dir, "github-kanban-bridge-config.json"
        )

    def run_script(self, *args):
        env = dict(os.environ, HOME=self.home)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_prints_configured_url(self):
        with open(self.config_path, "w") as f:
            json.dump({"webhook_base_url": "https://kanban.example.com"}, f)
        result = self.run_script("webhook-url")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout.strip(),
            f"https://kanban.example.com{ROUTE_SUFFIX}",
        )

    def test_unset_fails_without_localhost_fallback(self):
        result = self.run_script("webhook-url")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("--set-url", result.stderr)
        self.assertNotIn("localhost", result.stderr)

    def test_onboard_aborts_before_network_when_unset(self):
        result = self.run_script("onboard", "owner/repo")
        self.assertEqual(result.returncode, 1)
        self.assertIn("--set-url", result.stderr)
        self.assertNotIn("token", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
