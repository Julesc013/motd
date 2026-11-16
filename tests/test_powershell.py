"""Native PowerShell contracts; generated scripts run only in temporary folders.

Set MOTD_TEST_POWERSHELL to a specific pwsh/powershell executable to test a
version boundary. Otherwise use pwsh (or Windows PowerShell) from PATH.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("motd_ps_test_subject", ROOT / "motd.py")
motd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(motd)
POWERSHELL = os.environ.get("MOTD_TEST_POWERSHELL") or shutil.which("pwsh") or shutil.which("powershell")


class PowerShellGenerationTests(unittest.TestCase):
    def test_canonical_runtime_and_checked_recipe(self):
        self.assertEqual(motd.PS_TEMPLATE, (ROOT / "runtime/motd.ps1").read_text(encoding="utf-8"))
        self.assertEqual(motd.PS_TEMPLATE.count("# @MOTD_CONFIG@"), 1)
        config = motd.preset_config("home-lab")
        config["shell"] = "powershell"
        artifact = motd.generate_artifact(config)
        self.assertEqual(motd.extract_config(artifact), motd.validate_config(config))
        self.assertIn("#Requires -Version 5.1", artifact)
        self.assertNotIn("#!/usr/bin/env bash", artifact)

    def test_source_is_ascii_even_when_configuration_is_unicode(self):
        config = motd.preset_config()
        config["shell"] = "powershell"
        config["display"]["title"] = "Labo \u2014 caf\u00e9 \U0001f600"
        config["messages"] = ["\u4f60\u597d '$env:TEMP' ` \" literal"]
        artifact = motd.generate_artifact(config)
        artifact.encode("ascii")  # Windows PS5.1 can read this without a BOM.
        self.assertEqual(motd.extract_config(artifact)["messages"], config["messages"])


@unittest.skipUnless(POWERSHELL, "PowerShell not installed; set MOTD_TEST_POWERSHELL to test this backend")
class PowerShellExecutionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="motd-native-ps-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.script = self.root / "message with spaces.ps1"
        self.config = motd.preset_config("home-lab")
        self.config["shell"] = "powershell"
        self.config["display"]["sections"] = ["system", "resources", "processes", "services", "attention"]
        self.config["display"]["width"] = 100
        self.config["display"]["rows"] = 40

    def render(self, *arguments, config=None, timeout=12):
        self.script.write_text(motd.generate_artifact(config or self.config), encoding="utf-8")
        return subprocess.run([POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive",
                               "-File", str(self.script), *arguments],
                              capture_output=True, text=True, encoding="utf-8",
                              timeout=timeout, cwd=self.root)

    def hook(self, code, *, timeout=2, failure="continue", extra=()):
        return {"argv": [sys.executable, "-c", code, *extra],
                "timeout_seconds": timeout, "on_failure": failure}

    def test_actual_demo_geometry_data_and_resource_bars(self):
        result = self.render("-Demo", "-Plain", "-Width", "80", "-Rows", "20")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DEMO - synthetic", result.stdout)
        self.assertIn("CPU total (s)", result.stdout)
        self.assertIn("[####--------]", result.stdout)
        self.assertNotIn("\x1b", result.stdout)
        self.assertTrue(all(len(line) == 80 for line in result.stdout.splitlines()), result.stdout)
        self.assertLessEqual(len(result.stdout.splitlines()), 19)

    def test_configuration_is_data_and_cannot_execute_powershell(self):
        sentinel = self.root / "unexpected.txt"
        self.config["display"]["title"] = "Literal ' $(New-Item unexpected.txt) ` ; \""
        self.config["messages"] = ["Unicode caf\u00e9 and '$env:PATH' are literal"]
        result = self.render("-Demo", "-Plain")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("$(New-Item unexpected.txt)", result.stdout)
        self.assertIn("caf\u00e9", result.stdout)
        self.assertFalse(sentinel.exists())

    def test_demo_live_preview_help_and_version_do_not_run_hooks(self):
        sentinel = self.root / "hooks-ran.txt"
        hook = self.hook("from pathlib import Path;Path('hooks-ran.txt').write_text('bad')")
        self.config["hooks"] = {"before": [hook], "after": [hook]}
        self.config["display"]["sections"] = ["system", "attention"]
        for args in (("-Demo", "-Plain"), ("-NoHooks", "-Plain"), ("-Help",), ("-Version",)):
            with self.subTest(args=args):
                result = self.render(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(sentinel.exists())

    def test_native_arguments_and_before_after_order_are_preserved(self):
        arguments = ["", "with spaces", "single'quote", 'double"quote', "trailing\\", "back\\\"quote", "caf\u00e9"]
        before = self.hook("import json,sys;from pathlib import Path;Path('argv.json').write_text(json.dumps(sys.argv[1:]));print('BEFORE-MARKER')", extra=arguments)
        after = self.hook("print('AFTER-MARKER')")
        self.config["hooks"] = {"before": [before], "after": [after]}
        self.config["display"]["sections"] = ["system"]
        result = self.render("-Plain")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.root / "argv.json").read_text()), arguments)
        self.assertLess(result.stdout.index("BEFORE-MARKER"), result.stdout.index("HOME LAB"))
        self.assertLess(result.stdout.index("HOME LAB"), result.stdout.index("AFTER-MARKER"))

    def test_hook_timeout_stops_script_when_requested(self):
        self.config["hooks"]["before"] = [self.hook("import time;print('PARTIAL',flush=True);time.sleep(10)", timeout=0.3, failure="stop")]
        start = time.monotonic()
        result = self.render("-Plain", timeout=8)
        self.assertNotEqual(result.returncode, 0)
        self.assertLess(time.monotonic() - start, 8)
        self.assertIn("failed (124)", result.stderr)
        self.assertIn("PARTIAL", result.stdout)
        self.assertNotIn("HOME LAB", result.stdout)

    def test_hook_failure_continue_allows_dashboard_and_after_hook(self):
        self.config["hooks"] = {
            "before": [self.hook("import sys;sys.exit(7)")],
            "after": [self.hook("print('AFTER-FAILURE-MARKER')")],
        }
        self.config["display"]["sections"] = ["system"]
        result = self.render("-Plain")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("failed (7)", result.stderr)
        self.assertIn("HOME LAB", result.stdout)
        self.assertIn("AFTER-FAILURE-MARKER", result.stdout)

    def test_live_unsupported_observations_are_not_zero_or_healthy(self):
        self.config["display"]["sections"] = ["system", "io", "connections", "sessions"]
        result = self.render("-NoHooks", "-Plain")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("synthetic", result.stdout)
        self.assertIn("per-process rates not implemented", result.stdout)
        self.assertIn("connection inventory not implemented", result.stdout)
        self.assertIn("other sessions unavailable", result.stdout)

    def test_live_local_memory_storage_and_process_observations(self):
        self.config["display"]["sections"] = ["system", "resources", "processes"]
        result = self.render("-NoHooks", "-Plain", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CPU total (s)", result.stdout)
        self.assertIn("STORAGE", result.stdout)
        if sys.platform.startswith("linux") or os.name == "nt":
            self.assertRegex(result.stdout, r"MEMORY\s+[\d,.]+ (GiB|MiB) / [\d,.]+ (GiB|MiB)")
        self.assertRegex(result.stdout, r"\d+\s+[\d,.]+\s+[\d,.]+ (GiB|MiB)")

    def test_forced_color_and_explicit_plain_precedence(self):
        result = self.render("-Demo", "-Color")
        self.assertEqual(result.returncode, 0, result.stderr)
        if os.environ.get("NO_COLOR"):
            self.assertNotIn("\x1b[", result.stdout)
        else:
            self.assertIn("\x1b[32m", result.stdout)
        plain = self.render("-Demo", "-Color", "-Plain")
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertNotIn("\x1b[", plain.stdout)

    def test_ascii_mode_preserves_column_width_with_unicode_labels(self):
        self.config["display"]["title"] = "Labo \u4f60\u597d \U0001f600 caf\u00e9"
        result = self.render("-Demo", "-Plain", "-Ascii", "-Width", "80")
        self.assertEqual(result.returncode, 0, result.stderr)
        result.stdout.encode("ascii")
        self.assertTrue(all(len(line) == 80 for line in result.stdout.splitlines()))

    def test_invalid_geometry_is_rejected(self):
        result = self.render("-Demo", "-Width", "10")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Width must be 40..240", result.stderr)

    def test_observed_control_characters_are_sanitized(self):
        self.script.write_text(motd.generate_artifact(self.config), encoding="utf-8")
        env = os.environ.copy()
        env["MOTD_PS_TEST_SCRIPT"] = str(self.script)
        command = ". $env:MOTD_PS_TEST_SCRIPT -Demo -Plain | Out-Null; ConvertTo-MotdText ('a' + [char]27 + '[2J' + [char]10 + 'b')"
        result = subprocess.run([POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
                                capture_output=True, text=True, timeout=8, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "a?[2J?b")


if __name__ == "__main__":
    unittest.main()
