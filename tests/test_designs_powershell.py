"""Actual native PowerShell presentation contracts; no installed login hooks.

Use MOTD_TEST_POWERSHELL to select an exact installed engine. These current-host
tests do not substitute for tools/test_legacy_powershell.ps1 on historical hosts.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import unicodedata
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("motd_design_ps_subject", ROOT / "motd.py")
motd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(motd)
POWERSHELL = os.environ.get("MOTD_TEST_POWERSHELL") or shutil.which("pwsh") or shutil.which("powershell")
DESIGNS = ("classic", "cards", "ledger", "briefing", "dashboard")
SGR = re.compile(r"\x1b\[[0-9;]*m")


def cells(line):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in "WF" else 1
               for c in SGR.sub("", line))


@unittest.skipUnless(POWERSHELL, "Set MOTD_TEST_POWERSHELL to execute the native design contracts")
class NativePowerShellDesignTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="motd-ps-designs-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.script = self.root / "native design with spaces.ps1"
        self.config = motd.preset_config("workshop", shell="powershell")
        self.config["display"]["sections"] = list(motd.SECTION_IDS)

    def render(self, design, *, width=80, rows=50, unicode=False, colored=False, alerts=True):
        self.config["display"]["design"] = design
        self.script.write_text(motd.generate_artifact(self.config), encoding="utf-8")
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env.pop("NO_COLOR", None)
        result = subprocess.run(
            [POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(self.script),
             "-DemoAlerts" if alerts else "-Demo", "-NoHooks", "-Color" if colored else "-Plain",
             "-Unicode" if unicode else "-Ascii", "-Width", str(width), "-Rows", str(rows)],
            capture_output=True, text=True, encoding="utf-8", timeout=25, env=env, cwd=self.root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        lines = result.stdout.splitlines()
        self.assertTrue(lines)
        self.assertLessEqual(len(lines), rows - 1, result.stdout)
        self.assertTrue(all(cells(line) == width for line in lines), result.stdout)
        self.assertIn("DEMO", result.stdout)
        return result.stdout

    def test_every_design_fits_all_requested_sizes_and_character_sets(self):
        for design in DESIGNS:
            for width, rows in ((40, 25), (40, 50), (80, 25), (80, 50)):
                for unicode in (False, True):
                    with self.subTest(design=design, width=width, rows=rows, unicode=unicode):
                        text = self.render(design, width=width, rows=rows, unicode=unicode)
                        self.assertIn("91%", text)
                        if not unicode:
                            text.encode("ascii")

    def test_designs_have_distinct_structures_and_dashboard_reflows(self):
        outputs = {design: self.render(design) for design in DESIGNS}
        self.assertEqual(len(set(outputs.values())), len(DESIGNS))
        self.assertEqual(outputs["classic"].count("+------------------------------------------------------------------------------+"), 1)
        self.assertIn("+ " + motd.SECTION_TEXT["resources"][0] + " ", outputs["cards"])
        self.assertIn("+ " + motd.SECTION_TEXT["system"][0] + " ", outputs["cards"])
        self.assertFalse(outputs["ledger"].splitlines()[2].lstrip().startswith("|"))
        self.assertFalse(outputs["ledger"].splitlines()[2].rstrip().endswith("|"))
        self.assertIn(motd.SECTION_TEXT["system"][0] + ": demo-host", outputs["ledger"])
        self.assertLess(outputs["briefing"].index(motd.SECTION_TEXT["system"][0]), outputs["briefing"].index(motd.SECTION_TEXT["attention"][0]))
        self.assertIn(motd.SECTION_TEXT["attention"][0], outputs["briefing"])
        self.assertIn("WARN demo disk usage 91%", outputs["briefing"])
        self.assertIn("+  +", outputs["dashboard"])
        self.assertLess(outputs["dashboard"].index(motd.SECTION_TEXT["system"][0]), outputs["dashboard"].index(motd.SECTION_TEXT["resources"][0]))
        self.assertIn("6.0G/16.0G", outputs["dashboard"])
        narrow = self.render("dashboard", width=40)
        self.assertNotIn("+  +", narrow)
        self.assertIn("+ " + motd.SECTION_TEXT["resources"][0] + " ", narrow)

    def test_compact_and_extreme_geometry_preserve_complete_frames(self):
        for design in DESIGNS:
            for width, rows, padding, gap in ((40, 8, 0, 0), (40, 15, 3, 2), (240, 200, 3, 2)):
                with self.subTest(design=design, width=width, rows=rows, padding=padding, gap=gap):
                    self.config["display"].update(padding=padding, section_gap=gap, density="comfortable")
                    text = self.render(design, width=width, rows=rows)
                    if rows <= 15:
                        self.assertIn("Hidden:", text)
                    if design in ("classic", "cards", "dashboard"):
                        visible = [line for line in text.splitlines() if line.strip()]
                        borders = [line for line in visible if line.startswith("+")]
                        self.assertTrue(all(line.endswith("+") for line in borders))

    def test_priority_selects_complete_sections_when_space_is_limited(self):
        self.config["display"]["priority"] = ["hints", *[x for x in motd.SECTION_IDS if x != "hints"]]
        text = self.render("cards", width=40, rows=10)
        self.assertIn("+ " + motd.SECTION_TEXT["hints"][0] + " ", text)
        self.assertNotIn("+ " + motd.SECTION_TEXT["attention"][0] + " ", text)
        self.assertIn("Hidden:", text)

    def test_dashboard_preserves_configured_section_order_at_both_widths(self):
        order = ["hints", "services", "resources", "system", "attention"]
        self.config["display"]["sections"] = order
        for width in (40, 80):
            with self.subTest(width=width):
                text = self.render("dashboard", width=width, rows=80)
                positions = [text.index("+ " + motd.SECTION_TEXT[section][0] + " ") for section in order]
                self.assertEqual(positions, sorted(positions))

    def test_long_titles_cannot_hide_demo_or_identity_without_system_section(self):
        self.config["display"]["title"] = "A long title " * 6
        self.config["display"]["sections"] = ["resources", "services", "processes", "sessions", "connections", "hints", "io"]
        self.config["display"]["priority"] = ["hints", *[x for x in motd.SECTION_IDS if x != "hints"]]
        for design in DESIGNS:
            with self.subTest(design=design):
                text = self.render(design, width=40, rows=8)
                self.assertIn("DEMO", text.splitlines()[0])
                self.assertIn("Host demo-host", text.splitlines()[0])
                self.assertIn("Up 4d 06h", text.splitlines()[0])
                self.assertNotIn("SYSTEM", text)
                self.assertNotIn("ATTENTION", text)

    def test_tiny_viewports_name_every_selected_or_hidden_section(self):
        for design in DESIGNS:
            with self.subTest(design=design):
                text = self.render(design, width=40, rows=8)
                self.assertIn("Hidden:", text)
                for section in motd.SECTION_IDS:
                    label = motd.SECTION_TEXT[section][0]
                    hidden_start = text.index("Hidden:")
                    self.assertTrue(label.lower() in text.lower() or section.lower() in text[hidden_start:].lower(),
                                    section + " vanished without a named omission")

    def test_detail_and_section_override_change_real_fixture_content(self):
        self.config["display"]["detail"] = "brief"
        brief = self.render("ledger", rows=100)
        self.assertNotIn("18.7s", brief)
        self.config["display"]["section_detail"] = {"processes": "full"}
        detailed = self.render("ledger", rows=100)
        self.assertIn("18.7s", detailed)
        self.assertGreater(len(detailed.splitlines()), len(brief.splitlines()))
        self.config["display"]["section_detail"] = {}
        self.config["display"]["detail"] = "full"
        full = self.render("ledger", rows=100)
        self.assertIn("Working sets / cumulative CPU", full)

    def test_briefing_promotes_the_first_detail_of_heading_only_sections(self):
        self.config["display"]["sections"] = ["hints", "attention"]
        self.config["display"]["detail"] = "brief"
        text = self.render("briefing", width=80, rows=25)
        self.assertIn(motd.SECTION_TEXT["hints"][0], text)
        self.assertIn("Tasks: Get-Process - Local processes", text)
        self.assertIn(motd.SECTION_TEXT["attention"][0], text)
        self.assertIn("WARN demo disk usage 91%", text)
        self.assertLess(text.index(motd.SECTION_TEXT["hints"][0]), text.index(motd.SECTION_TEXT["attention"][0]))

    def test_density_padding_and_gap_affect_layout_without_clipping(self):
        self.config["display"].update(density="compact", padding=0, section_gap=0, separator_text="none")
        compact = self.render("cards", rows=100)
        self.config["display"].update(density="comfortable", padding=3, section_gap=1)
        comfortable = self.render("cards", rows=100)
        self.assertNotEqual(compact, comfortable)
        self.assertIn("|   MEMORY", comfortable)
        self.assertIn("|MEMORY", compact)
        self.assertGreater(sum(not line.strip() for line in comfortable.splitlines()),
                           sum(not line.strip() for line in compact.splitlines()))

    def test_colour_emphasis_changes_tones_and_plain_overrides_all(self):
        self.config["display"]["color_emphasis"] = "quiet"
        quiet = self.render("cards", colored=True)
        self.assertIn("\x1b[33m", quiet)
        self.assertNotIn("\x1b[36m", quiet)
        self.config["display"]["color_emphasis"] = "vivid"
        vivid = self.render("cards", colored=True)
        self.assertIn("\x1b[1;36m", vivid)
        self.assertIn("\x1b[1;33m", vivid)
        self.assertNotIn("\x1b", self.render("cards"))

    def test_unicode_labels_and_untrusted_calls_remain_data_in_all_designs(self):
        self.config["display"]["title"] = "\u4f60\u597d cafe\u0301 \U0001f600"
        self.config["messages"] = ["Literal ' $(New-Item unexpected.txt) ` ; \" text"]
        self.config["hooks"]["before"] = [{"argv": ["not-a-real-command"], "timeout_seconds": 1, "on_failure": "stop"}]
        for design in DESIGNS:
            with self.subTest(design=design):
                self.render(design, width=80, rows=80, unicode=True)
                self.assertFalse((self.root / "unexpected.txt").exists())

    def test_builtin_print_is_literal_and_respects_preview_suppression(self):
        before = "BEFORE '$env:PATH' $(New-Item unexpected.txt) ` ; %PATH%"
        self.config["hooks"] = {
            "before": [{"argv": ["motd:print", before, ""], "timeout_seconds": 1, "on_failure": "stop"}],
            "after": [{"argv": ["motd:print", "AFTER literal text"], "timeout_seconds": 1, "on_failure": "stop"}],
        }
        self.config["display"]["sections"] = ["system"]
        self.config["display"]["design"] = "ledger"
        self.script.write_text(motd.generate_artifact(self.config), encoding="utf-8")
        base = [POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(self.script),
                "-Plain", "-Ascii", "-Width", "80", "-Rows", "50"]
        live = subprocess.run(base, capture_output=True, text=True, encoding="utf-8", timeout=20, cwd=self.root)
        self.assertEqual(live.returncode, 0, live.stderr)
        self.assertEqual(live.stderr, "")
        self.assertTrue(live.stdout.startswith(before + "\n\n"), live.stdout)
        self.assertTrue(live.stdout.endswith("AFTER literal text\n"), live.stdout)
        self.assertFalse((self.root / "unexpected.txt").exists())
        for extra in (("-Demo",), ("-NoHooks",)):
            with self.subTest(extra=extra):
                suppressed = subprocess.run([*base, *extra], capture_output=True, text=True, encoding="utf-8", timeout=20, cwd=self.root)
                self.assertEqual(suppressed.returncode, 0, suppressed.stderr)
                self.assertNotIn("BEFORE", suppressed.stdout)
                self.assertNotIn("AFTER literal text", suppressed.stdout)
                self.assertFalse((self.root / "unexpected.txt").exists())

    def test_legacy_harness_rejects_a_different_engine_before_executing_input(self):
        probe = subprocess.run([POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
                                "$PSVersionTable.PSVersion.Major"], capture_output=True, text=True, timeout=15)
        self.assertEqual(probe.returncode, 0, probe.stderr)
        actual = int(probe.stdout.strip())
        different = actual % 7 + 1
        self.script.write_text("Set-Content -LiteralPath 'unexpected.txt' -Value 'bad'\n", encoding="ascii")
        report = self.root / "wrong-engine.xml"
        result = subprocess.run([POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-File",
                                 str(ROOT / "tools/test_legacy_powershell.ps1"), "-Artifact", str(self.script),
                                 "-ExpectedMajor", str(different), "-Output", str(report)],
                                capture_output=True, text=True, timeout=15, cwd=self.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "unexpected.txt").exists())
        evidence = ET.parse(report).getroot()
        self.assertEqual(evidence.attrib["status"], "failed")
        self.assertEqual(int(evidence.attrib["actual-version"].split(".")[0]), actual)
        self.assertEqual(int(evidence.attrib["expected-major"]), different)
        self.assertEqual(evidence.findall("artifact"), [])


if __name__ == "__main__":
    unittest.main()
