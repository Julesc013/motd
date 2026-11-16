"""Native PowerShell contracts; generated scripts run only in temporary folders.

Set MOTD_TEST_POWERSHELL to a specific pwsh/powershell executable to test a
version boundary. Otherwise use pwsh (or Windows PowerShell) from PATH.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
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
        self.assertIn("#Requires -Version 1.0", artifact)
        self.assertNotIn("ConvertFrom-Json", artifact)
        self.assertIn("$MotdConfig = @{", artifact)
        self.assertNotIn("#!/usr/bin/env bash", artifact)

    def test_source_is_ascii_even_when_configuration_is_unicode(self):
        config = motd.preset_config()
        config["shell"] = "powershell"
        config["display"]["title"] = "Labo \u2014 caf\u00e9 \U0001f600"
        config["messages"] = ["\u4f60\u597d '$env:TEMP' ` \" literal"]
        artifact = motd.generate_artifact(config)
        artifact.encode("ascii")  # Historical Windows PS can read this without a BOM.
        self.assertEqual(motd.extract_config(artifact)["messages"], config["messages"])

    def test_core_does_not_reintroduce_known_post_v1_grammar(self):
        # This checks explicit design boundaries, not historical execution.
        # Only running an actual old engine can verify that engine.
        source = re.sub(r"(?m)^\s*#.*$", "", motd.PS_TEMPLATE)
        for expression in (r"\btry\s*\{", r"\bcatch\s*\{", r"\bfinally\s*\{",
                           r"\[CmdletBinding", r"\bConvertFrom-Json\b",
                           r"-(?:join|split|in|notin)\b", r"\$PSScriptRoot\b",
                           r"\$IsWindows\b", r"Collections\.Generic"):
            with self.subTest(expression=expression):
                self.assertNotRegex(source, expression)
        self.assertIn("trap {", source)
        self.assertNotRegex(source, r"\$MotdConfig\.")


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

    def render(self, *arguments, config=None, timeout=12, env=None):
        self.script.write_text(motd.generate_artifact(config or self.config), encoding="utf-8")
        return subprocess.run([POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive",
                               "-File", str(self.script), *arguments],
                              capture_output=True, text=True, encoding="utf-8",
                              timeout=timeout, cwd=self.root, env=env)

    def probe(self, command, *, timeout=12):
        """Inspect public runtime helpers after a hook-free temporary demo."""
        self.script.write_text(motd.generate_artifact(self.config), encoding="utf-8")
        env = os.environ.copy()
        env["MOTD_PS_TEST_SCRIPT"] = str(self.script)
        return subprocess.run([POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
                               ". $env:MOTD_PS_TEST_SCRIPT -Demo -Plain | Out-Null; " + command],
                              capture_output=True, text=True, encoding="utf-8", timeout=timeout,
                              env=env, cwd=self.root)

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

    def test_live_io_connections_and_sessions_keep_units_and_scope(self):
        self.config["display"]["sections"] = ["system", "io", "connections", "sessions"]
        result = self.render("-NoHooks", "-Plain")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("synthetic", result.stdout)
        self.assertIn("I/O  cumulative process R+W bytes", result.stdout)
        self.assertRegex(result.stdout, r"totals are not rates|unavailable \(OS API/access missing\)")
        self.assertRegex(result.stdout, r"CONNECTIONS (\d+ TCP / \d+ listen / \d+ UDP|unavailable)")
        self.assertRegex(result.stdout, r"SESSIONS\s+(.+\(current\)|local registered records)")
        self.assertNotIn("all healthy", result.stdout.lower())

    def test_live_local_memory_storage_and_process_observations(self):
        self.config["display"]["sections"] = ["system", "resources", "processes"]
        result = self.render("-NoHooks", "-Plain", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CPU total (s)", result.stdout)
        self.assertIn("STORAGE", result.stdout)
        if sys.platform.startswith("linux") or os.name == "nt":
            self.assertRegex(result.stdout, r"MEMORY\s+[\d,.]+ (GiB|MiB) / [\d,.]+ (GiB|MiB)")
        self.assertRegex(result.stdout, r"CPU\s+[\d,.]+s\s+\d+\s+\S+")
        self.assertRegex(result.stdout, r"MEM\s+[\d,.]+[GMKB]\s+\d+\s+\S+")

    def test_forced_color_and_explicit_plain_precedence(self):
        result = self.render("-Demo", "-Color")
        self.assertEqual(result.returncode, 0, result.stderr)
        if "NO_COLOR" in os.environ:
            self.assertNotIn("\x1b[", result.stdout)
        else:
            self.assertIn("\x1b[32m", result.stdout)
        plain = self.render("-Demo", "-Color", "-Plain")
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertNotIn("\x1b[", plain.stdout)

    def test_present_empty_no_color_disables_forced_color(self):
        env = os.environ.copy()
        env["NO_COLOR"] = ""
        result = self.render("-Demo", "-Color", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("\x1b[", result.stdout)

    def test_all_requested_sizes_and_charsets_expand_actual_content(self):
        self.config["display"]["sections"] = list(motd.SECTION_IDS)
        self.config["display"]["rows"] = 50
        for width in (40, 80):
            for charset in ("-Ascii", "-Unicode"):
                captures = {}
                for rows in (25, 50):
                    with self.subTest(width=width, rows=rows, charset=charset):
                        result = self.render("-Demo", "-Plain", charset, "-Width", str(width), "-Rows", str(rows))
                        self.assertEqual(result.returncode, 0, result.stderr)
                        captures[rows] = result.stdout.splitlines()
                        self.assertTrue(all(len(line) == width for line in captures[rows]), result.stdout)
                        self.assertLessEqual(len(captures[rows]), rows - 1)
                        for label in ("SYSTEM", "SERVICES", "PROCESSES", "SESSIONS", "CONNECTIONS", "ATTENTION", "HINTS", "I/O"):
                            self.assertIn(label, result.stdout)
                        self.assertIn("6.0G/16.0G" if width == 40 else "6.0 GiB / 16.0 GiB", result.stdout)
                        if charset == "-Unicode":
                            self.assertTrue(captures[rows][0].startswith("\u250c"))
                            self.assertIn("\u2588", result.stdout)
                        else:
                            result.stdout.encode("ascii")
                self.assertGreater(len(captures[50]), len(captures[25]) + 10)

    def test_v1_command_launcher_works_with_a_script_path_containing_spaces(self):
        # -File was introduced after Windows PowerShell1. The documented
        # universal launch path is a literal & call within -Command.
        self.script.write_text(motd.generate_artifact(self.config), encoding="utf-8")
        command = "& '" + str(self.script).replace("'", "''") + "' -Demo -Plain -Width 40 -Rows 25"
        result = subprocess.run([POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
                                capture_output=True, text=True, encoding="utf-8", timeout=12)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HOME LAB", result.stdout)
        self.assertTrue(all(len(line) == 40 for line in result.stdout.splitlines()))

    def test_trap_preserves_failure_and_rejects_partial_observations(self):
        result = self.probe("$failed = Read-MotdObservation { 17; throw 'deliberate unavailable'; 42 }; "
                            "$empty = Read-MotdObservation { }; "
                            "Write-Output ('failed=' + $failed.Ok + ';value=' + ($null -eq $failed.Value) + ';error=' + $failed.Error); "
                            "Write-Output ('empty=' + $empty.Ok + ';count=' + $empty.Value.Count)")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("failed=False;value=True;error=deliberate unavailable", result.stdout)
        self.assertIn("empty=True;count=0", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_unavailable_network_api_does_not_render_zero_connections(self):
        result = self.probe("function Read-MotdObservation { @{ Ok=$false; Value=@(); Error='unavailable fixture' } }; "
                            "$MotdCurrentSection='connections'; $MotdSections['connections']=@{ Lines=(New-MotdList) }; "
                            "$Demo=$false; Add-MotdConnections; "
                            "$MotdSections['connections'].Lines | ForEach-Object { $_.Text }")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CONNECTIONS unavailable", result.stdout)
        self.assertNotIn("0 TCP", result.stdout)

    def test_unicode_cells_count_wide_and_combining_text(self):
        self.config["display"]["title"] = "\u4f60\u597d cafe\u0301 \U0001f600"
        result = self.render("-Demo", "-Plain", "-Unicode", "-Width", "40", "-Rows", "25")
        self.assertEqual(result.returncode, 0, result.stderr)
        # Two CJK glyphs and one emoji consume six cells; the combining acute
        # consumes no additional cell. This does not claim ZWJ grapheme parity.
        import unicodedata
        def cell_width(line):
            return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in line)
        self.assertTrue(all(cell_width(line) == 40 for line in result.stdout.splitlines()), result.stdout)

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
