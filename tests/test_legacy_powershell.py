"""Version gates in the standalone harness, executed in an actual engine."""

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("motd_legacy_ps_subject", ROOT / "motd.py")
motd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(motd)
POWERSHELL = os.environ.get("MOTD_TEST_POWERSHELL") or shutil.which("pwsh") or shutil.which("powershell")


@unittest.skipUnless(POWERSHELL, "Set MOTD_TEST_POWERSHELL to execute the version-gate contracts")
class LegacyPowerShellVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        probe = subprocess.run(
            [POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
             "$PSVersionTable.PSVersion.ToString()"],
            capture_output=True, text=True, timeout=20,
        )
        if probe.returncode:
            raise AssertionError(probe.stderr)
        cls.version = probe.stdout.strip()
        cls.major, cls.minor = [int(part) for part in cls.version.split(".")[:2]]

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="motd-legacy-version-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.script = self.root / "generated artifact.ps1"
        self.marker = self.root / "unexpected-hook.txt"
        self.report = self.root / "evidence.xml"

    def run_harness(self, minor=None, live=False):
        command = [POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-File",
                   str(ROOT / "tools/test_legacy_powershell.ps1"), "-Artifact", str(self.script),
                   "-ExpectedMajor", str(self.major), "-Output", str(self.report)]
        if minor is not None:
            command.extend(["-ExpectedMinor", str(minor)])
        if live:
            command.append("-IncludeLive")
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                timeout=90, cwd=self.root)
        self.assertTrue(self.report.exists(), result.stdout + result.stderr)
        return result, ET.parse(self.report).getroot()

    def test_minor_mismatch_and_invalid_constraint_refuse_before_artifact_execution(self):
        # This marker is outside any hook guard: version refusal must happen
        # before the input script can run, not merely suppress configured hooks.
        marker_path = str(self.marker).replace("'", "''")
        self.script.write_text("Set-Content -LiteralPath '" + marker_path + "' -Value 'ran'\n",
                               encoding="ascii")
        for minor in (self.minor - 1 if self.minor else 1, -2):
            with self.subTest(expected_minor=minor):
                result, evidence = self.run_harness(minor)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.marker.exists())
                self.assertEqual(evidence.attrib["status"], "failed")
                self.assertEqual(evidence.attrib["actual-version"], self.version)
                self.assertEqual(int(evidence.attrib["expected-major"]), self.major)
                self.assertEqual(int(evidence.attrib["expected-minor"]), minor)
                expected_error = ("Supply -ExpectedMinor" if minor < -1 else
                                  "Expected PowerShell " + str(self.major) + "." + str(minor))
                self.assertIn(expected_error, evidence.attrib["fatal-error"])
                self.assertEqual(evidence.findall("artifact"), [])
                self.assertEqual(evidence.findall(".//case"), [])

    def test_matching_minor_and_major_only_default_execute_real_cases_without_hooks(self):
        config = motd.preset_config("workshop", shell="powershell")
        config["display"]["design"] = "cards"
        marker_path = str(self.marker).replace("'", "''")
        hook = {"argv": [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command",
                         "Set-Content -LiteralPath '" + marker_path + "' -Value 'ran'"],
                "timeout_seconds": 5, "on_failure": "stop"}
        config["hooks"] = {"before": [hook], "after": [hook]}
        self.script.write_text(motd.generate_artifact(config), encoding="ascii")
        for minor in (self.minor, None):
            with self.subTest(expected_minor=minor):
                result, evidence = self.run_harness(minor, live=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(evidence.attrib["status"], "passed")
                self.assertEqual(evidence.attrib["actual-version"], self.version)
                self.assertEqual(int(evidence.attrib["expected-minor"]), -1 if minor is None else minor)
                self.assertEqual(int(evidence.attrib["cases"]), 9)
                self.assertEqual(int(evidence.attrib["failed"]), 0)
                self.assertEqual(len(evidence.findall("artifact/case")), 8)
                self.assertEqual(evidence.find("case").attrib["kind"], "live-local-no-hooks")
                self.assertFalse(self.marker.exists())


if __name__ == "__main__":
    unittest.main()
