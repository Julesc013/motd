"""CLI and wizard regressions, confined to explicit temporary paths.

These tests never replace HOME or install onto real startup/system files.
The PTY smoke only previews, saves, builds, and cancels.
"""
from contextlib import redirect_stderr, redirect_stdout
import errno
import fcntl
import struct
import termios
import importlib.util
import io
import json
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "motd.py"
_spec = importlib.util.spec_from_file_location("motd_cli_test_subject", SOURCE)
motd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(motd)


class CliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="motd-cli-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = str(self.root / "state")
        self.output = self.root / "dashboard.bash"
        self.shell = self.root / "shellrc"
        self.shell.write_text("# Existing test-only startup text\n", encoding="utf-8")
        self.original_shell = self.shell.read_bytes()
        self.recipe = self.root / "recipe.toml"
        self.config = motd.preset_config("home-lab")
        self.config["name"] = "cli-test"
        self.config["display"]["title"] = "CUSTOM CLI CONFIGURATION"
        self.config["messages"] = ["Keep this configured notice across upgrades."]
        self.recipe.write_text(motd.dump_config(self.config), encoding="utf-8")

    def cli(self, *arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = motd.main([*map(str, arguments), "--state-dir", self.state])
        return status, stdout.getvalue(), stderr.getvalue()

    def destinations(self, output=None):
        return ["--scope", "user", "--destination", str(output or self.output),
                "--shell-file", str(self.shell)]

    def install_recipe(self):
        status, _, _ = self.cli("install", "--config", self.recipe,
                                *self.destinations(), "--yes")
        self.assertEqual(status, 0)

    def snapshot(self):
        return {str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mode,
                                                   path.stat().st_mtime_ns)
                for path in self.root.rglob("*") if path.is_file()}

    def test_build_and_recover_recipe_round_trip(self):
        saved = self.root / "saved.toml"
        recovered = self.root / "recovered.toml"
        status, _, _ = self.cli("build", "--config", self.recipe, "--output", self.output,
                                "--save-config", saved)
        self.assertEqual(status, 0)
        expected = motd.validate_config(self.config)
        self.assertEqual(motd.extract_config(self.output.read_text()), expected)
        self.assertEqual(motd.load_config(saved), expected)
        status, _, _ = self.cli("config", "--artifact", self.output, "--output", recovered)
        self.assertEqual(status, 0)
        self.assertEqual(motd.load_config(recovered), expected)
        self.assertEqual(self.shell.read_bytes(), self.original_shell)

    def test_plan_is_read_only_before_and_after_installation(self):
        before = self.snapshot()
        status, text, _ = self.cli("plan", "--config", self.recipe,
                                   *self.destinations(), "--json")
        self.assertEqual(status, 0)
        self.assertGreater(json.loads(text)["change_count"], 0)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(Path(self.state).exists())
        self.install_recipe()
        before = self.snapshot()
        status, text, _ = self.cli("plan", "--config", self.recipe,
                                   *self.destinations(), "--json")
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(text)["change_count"], 0)
        self.assertEqual(self.snapshot(), before)

    def test_missing_artifacts_fail_without_creating_outputs_or_state(self):
        missing = self.root / "missing.bash"
        recovered = self.root / "recovered.toml"
        commands = [
            ["install", "--artifact", missing, "--target", "shell", "--trust-artifact",
             "--yes", *self.destinations()],
            ["plan", "--artifact", missing, "--target", "shell", *self.destinations()],
            ["build", "--artifact", missing, "--target", "shell", "--output", self.output],
            ["preview", "--artifact", missing, "--target", "issue"],
            ["inspect", "--artifact", missing],
            ["config", "--artifact", missing, "--output", recovered],
        ]
        before = self.snapshot()
        for command in commands:
            with self.subTest(command=command[0]), self.assertRaises(motd.MotdError):
                self.cli(*command)
            self.assertEqual(self.snapshot(), before)
            self.assertFalse(Path(self.state).exists())

    def test_opaque_import_requires_trust_and_has_no_inferred_recipe(self):
        source = self.root / "opaque.bash"
        executed = self.root / "must-not-exist"
        source.write_text("#!/bin/bash\nprintf executed > " + shlex.quote(str(executed)) + "\n")
        arguments = ["install", "--artifact", source, "--target", "shell", "--name", "opaque",
                     *self.destinations(), "--yes"]
        with self.assertRaises(motd.MotdError):
            self.cli(*arguments)
        self.assertFalse(Path(self.state).exists())
        status, _, _ = self.cli(*arguments, "--trust-artifact")
        self.assertEqual(status, 0)
        self.assertEqual(self.output.read_bytes(), source.read_bytes())
        self.assertFalse(executed.exists(), "Installing an import executed it")
        active = motd.active_installs(self.state)["opaque"]
        self.assertEqual(active["metadata"]["artifact_origin"], "opaque-import")
        self.assertNotIn("config_toml", active["metadata"])
        before = self.snapshot()
        for command in ("reconfigure", "upgrade"):
            with self.subTest(command=command), self.assertRaises(motd.MotdError):
                self.cli(command, "--name", "opaque", *self.destinations(), "--yes")
        with self.assertRaises(motd.MotdError):
            self.cli("config", "--artifact", source, "--output", self.root / "invented.toml")
        self.assertEqual(self.snapshot(), before)

    def test_generated_artifact_install_also_requires_explicit_trust(self):
        source = self.root / "generated.bash"
        source.write_text(motd.generate_artifact(self.config), encoding="utf-8")
        arguments = ["install", "--artifact", source, *self.destinations(), "--yes"]
        with self.assertRaises(motd.MotdError):
            self.cli(*arguments)
        self.assertFalse(Path(self.state).exists())
        status, _, _ = self.cli(*arguments, "--trust-artifact")
        self.assertEqual(status, 0)
        self.assertEqual(self.output.read_bytes(), source.read_bytes())

    def test_opaque_plan_does_not_execute_or_require_install_trust(self):
        source = self.root / "opaque.bash"
        executed = self.root / "must-not-exist"
        source.write_text("#!/bin/bash\ntouch " + shlex.quote(str(executed)) + "\n")
        before = self.snapshot()
        status, text, _ = self.cli("plan", "--artifact", source, "--target", "shell",
                                   "--name", "opaque", *self.destinations(), "--json")
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(text)["metadata"]["artifact_origin"], "opaque-import")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(Path(self.state).exists())

    def test_upgrade_reuses_the_installed_recipe(self):
        self.install_recipe()
        status, _, _ = self.cli("upgrade", "--name", "cli-test", *self.destinations(), "--yes")
        self.assertEqual(status, 0)
        self.assertEqual(motd.extract_config(self.output.read_text()), motd.validate_config(self.config))
        self.assertEqual(self.shell.read_text().count("# >>> motd cli-test >>>"), 1)

    def test_saved_recipe_commands_apply_audience_overrides(self):
        self.install_recipe()
        for command, audience in (("upgrade", "ssh"), ("reconfigure", "local")):
            with self.subTest(command=command):
                status, _, _ = self.cli(command, "--name", "cli-test", "--audience", audience,
                                        *self.destinations(), "--yes")
                self.assertEqual(status, 0)
                self.assertEqual(motd.extract_config(self.output.read_text())["audience"], audience)
                self.assertIn("SSH_CONNECTION", self.shell.read_text())

    def test_saved_recipe_commands_reject_target_and_destination_changes(self):
        self.install_recipe()
        before = self.snapshot()
        elsewhere = self.root / "elsewhere.bash"
        for command in ("upgrade", "reconfigure"):
            with self.subTest(command=command, override="target"), self.assertRaises(motd.MotdError):
                self.cli(command, "--name", "cli-test", "--target", "issue",
                         *self.destinations(), "--yes")
            with self.subTest(command=command, override="destination"), self.assertRaises(motd.MotdError):
                self.cli(command, "--name", "cli-test", *self.destinations(elsewhere), "--yes")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(elsewhere.exists())

    def test_static_import_preserves_already_serialized_issue_bytes(self):
        source = self.root / "serialized.issue"
        content = b"Prepared issue: \\\\n and \\s\n"
        source.write_bytes(content)
        destination = self.root / "installed.issue"
        status, _, _ = self.cli("install", "--artifact", source, "--target", "issue",
                                "--name", "notice", "--scope", "user", "--destination", destination,
                                "--yes")
        self.assertEqual(status, 0)
        self.assertEqual(destination.read_bytes(), content)
        self.assertEqual(self.shell.read_bytes(), self.original_shell)

    def test_cli_recovery_reaches_an_orphan_transaction(self):
        plan = motd.tx_plan([{"path": str(self.output), "content": "unused\n", "mode": 0o600}],
                            self.state, {"operation": "test-interruption"})
        staged = motd.tx_stage(plan)
        Path(staged["record_path"]).unlink()  # Simulate a missing initial durable journal.
        status, _, _ = self.cli("recover", "--transaction", staged["id"], "--yes")
        self.assertEqual(status, 0)
        self.assertFalse(self.output.exists())
        self.assertEqual(motd.tx_history(self.state)[0]["status"], "abandoned")

    @unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "PTY smoke requires POSIX and Bash")
    def test_wizard_preview_save_build_cancel_smoke(self):
        self.wizard_smoke('line')

    @unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "PTY smoke requires POSIX and Bash")
    def test_screen_wizard_preview_save_build_cancel_smoke(self):
        self.wizard_smoke('screen')

    def wizard_smoke(self, mode):
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 38, 100, 0, 0))
        process = subprocess.Popen([sys.executable, str(SOURCE), "wizard", "--ui", mode, "--state-dir", self.state],
                                   cwd=self.root, stdin=slave, stdout=slave, stderr=slave,
                                   start_new_session=True)
        os.close(slave)
        transcript = bytearray()
        cursor = 0
        deadline = time.monotonic() + 30

        def read_available():
            ready, _, _ = select.select([master], [], [], 0.1)
            if not ready:
                return False
            try:
                chunk = os.read(master, 65536)
            except OSError as exc:
                if exc.errno == errno.EIO:
                    return False
                raise
            transcript.extend(chunk)
            self.assertLess(len(transcript), 1_000_000, "Wizard produced unexpectedly large output")
            return bool(chunk)

        def respond(prompt, answer):
            nonlocal cursor
            while time.monotonic() < deadline:
                text = transcript.decode("utf-8", errors="replace")
                found = text.find(prompt, cursor)
                if found >= 0:
                    cursor = found + len(prompt)
                    os.write(master, (answer + "\n").encode())
                    return
                if not read_available() and process.poll() is not None:
                    self.fail(f"Wizard exited before {prompt!r}: {text[-4000:]}")
            self.fail(f"Wizard timed out waiting for {prompt!r}: {transcript[-4000:]!r}")

        recipe = self.root / "wizard.toml"
        output = self.root / "wizard.bash"
        try:
            for prompt, answer in [
                ("Choice [1]:", "1"),  # Create.
                ("Choice [1]:", "1"),  # User scope, isolated state directory.
                ("Choice [1]:", "1"),  # Workshop preset.
                *([("Choice [1]:", "")] if mode == 'screen' else []),
                ("Page choice:", "1"),  # Destination: edit name.
                ("Name:" if mode == 'screen' else "Name [", "wizard-test"),
                ("Page choice:", "n"),  # Appearance.
                ("Page choice:", "1"),
                ("Heading:" if mode == 'screen' else "Heading [", "Wizard smoke"),
                ("Page choice:", "3"),  # Theme.
                ("Choice [1]:", "2"),  # Green.
                *([("Choice [2]:", "")] if mode == 'screen' else []),
                ("Page choice:", "4"),
                ("Maximum columns:" if mode == 'screen' else "Maximum columns [", "80"),
                ("Page choice:", "n"),  # Characters and colour.
                ("Page choice:", "n"),  # Sections (1/2).
                ("Page choice:", "n"),  # Sections (2/2).
                ("Page choice:", "n"),  # Content.
                ("Page choice:", "n"),  # Hooks.
                ("Page choice:", "n"),  # Review.
                ("Choice [1]:", "1"),  # Synthetic preview.
                *([("Preview:", "")] if mode == 'screen' else []),
                ("Choice [1]:", "3"),  # Save recipe.
                ("Recipe path:" if mode == 'screen' else "Recipe path [", str(recipe)),
                *([("Press Enter to return to the wizard:", "")] if mode == 'screen' else []),
                ("Choice [1]:", "4"),  # Build portable output.
                ("Output path:" if mode == 'screen' else "Output path [", str(output)),
                *([("Press Enter to return to the wizard:", "")] if mode == 'screen' else []),
                ("Choice [1]:", "7"),  # Cancel; do not install.
            ]:
                respond(prompt, answer)
            while process.poll() is None and time.monotonic() < deadline:
                read_available()
            self.assertIsNotNone(process.poll(), "Wizard failed to exit within its deadline")
            while read_available():
                pass
            text = transcript.decode("utf-8", errors="replace")
            self.assertEqual(process.returncode, 0, text[-4000:])
            if mode == 'screen':
                self.assertIn('PREVIEW 100x28 | demo | calls off', text)
                self.assertIn('\x1b[2J\x1b[H', text)
            else:
                self.assertIn("Synthetic demonstration", text)
            self.assertNotIn("# MOTD-BODY-BEGIN", text, "Saving a recipe dumped the executable to the terminal")
            self.assertEqual(motd.load_config(recipe)["name"], "wizard-test")
            self.assertEqual(motd.load_config(recipe)["display"]["theme"], "green")
            self.assertEqual(motd.extract_config(output.read_text()), motd.load_config(recipe))
            self.assertEqual(self.shell.read_bytes(), self.original_shell)
            self.assertFalse(self.output.exists())
            self.assertFalse(motd.active_installs(self.state), "Wizard smoke unexpectedly installed a hook")
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
            os.close(master)


if __name__ == "__main__":
    unittest.main()
