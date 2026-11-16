"""Installer lifecycle acceptance tests; every file is inside a temporary directory.

The short artifacts deliberately print markers: these tests exercise ownership,
hook placement and shell guards, not the independently tested dashboard renderer.
"""
import importlib.util
import os
from pathlib import Path
import pty
import shlex
import stat
import subprocess
import unittest
import tempfile

_source = Path(__file__).resolve().parents[1] / "motd.py"
_spec = importlib.util.spec_from_file_location("motd_installation_test_subject", _source)
motd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(motd)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="motd-installation-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = str(self.root / "state")
        self.output = self.root / "dashboard.bash"
        self.shell = self.root / "shellrc"
        self.original_shell = "# Existing administrator/user configuration\nexport EXAMPLE=yes\n"
        self.shell.write_text(self.original_shell)
        self.shell.chmod(0o644)
        self.config = motd.preset_config("workshop")
        self.config["name"] = "test-dashboard"

    def artifact(self, version=1):
        return f"#!/bin/bash\nprintf 'MOTD-V{version}\\n'\n"

    def plan(self, version=1, *, config=None, replace=False, output=None, shell=None):
        return motd.installation_plan(config or self.config, self.artifact(version), scope="user",
                                      destination=str(output or self.output), shell_file=str(shell or self.shell),
                                      state_dir=self.state, replace=replace)

    def install(self, version=1, **kwargs):
        return motd.tx_apply(self.plan(version, **kwargs))

    def uninstall(self):
        return motd.tx_apply(motd.uninstall_plan(self.config["name"], self.state))

    def current(self):
        return motd.active_installs(self.state)[self.config["name"]]

    def test_installation_plan_is_read_only(self):
        plan = self.plan()
        self.assertEqual(plan["metadata"]["operation"], "install")
        self.assertFalse(Path(self.state).exists())
        self.assertFalse(self.output.exists())
        self.assertEqual(self.shell.read_text(), self.original_shell)

    def test_install_and_identical_reinstall_are_idempotent(self):
        first = self.install()
        before = (self.output.stat(), self.shell.stat())
        second = self.install()
        self.assertEqual(second["status"], "noop")
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual((self.output.stat().st_ino, self.shell.stat().st_ino),
                         (before[0].st_ino, before[1].st_ino))
        self.assertEqual(self.shell.read_text().count("# >>> motd test-dashboard >>>"), 1)
        self.assertEqual(self.current()["metadata"]["baseline_transaction_id"], first["id"])
        self.uninstall()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.shell.read_text(), self.original_shell)
        self.assertEqual(motd.active_installs(self.state), {})

    def test_upgrade_rollback_redo_then_uninstall_restores_originals(self):
        self.output.write_text("#!/bin/bash\n# preexisting file\n")
        self.output.chmod(0o640)
        original_output = self.output.read_text()
        first = self.install(replace=True)
        new_config = motd.preset_config("home-lab")
        new_config["name"] = self.config["name"]
        new_config["frequency"] = "interactive"
        second = self.install(2, config=new_config)
        inverse = motd.tx_rollback(self.state, second["id"])
        self.assertEqual(self.current()["id"], first["id"])
        self.assertEqual(self.output.read_text(), self.artifact(1))
        motd.tx_rollback(self.state, inverse["id"])
        self.assertEqual(self.current()["id"], second["id"])
        self.assertEqual(self.output.read_text(), self.artifact(2))
        self.assertIn("if : &&", self.shell.read_text())
        self.uninstall()
        self.assertEqual(self.output.read_text(), original_output)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o640)
        self.assertEqual(self.shell.read_text(), self.original_shell)
        self.assertEqual(motd.active_installs(self.state), {})

    def test_uninstall_rollback_restores_active_install(self):
        initial = self.install()
        removed = self.uninstall()
        self.assertEqual(motd.active_installs(self.state), {})
        motd.tx_rollback(self.state, removed["id"])
        self.assertEqual(self.current()["id"], initial["id"])
        self.assertEqual(self.output.read_text(), self.artifact())
        self.assertIn("# >>> motd test-dashboard >>>", self.shell.read_text())
        self.uninstall()
        self.assertEqual(self.shell.read_text(), self.original_shell)
        self.assertFalse(self.output.exists())

    def test_upgrade_can_be_rolled_back_again_after_redo(self):
        first = self.install()
        second = self.install(2)
        undone = motd.tx_rollback(self.state, second["id"])
        motd.tx_rollback(self.state, undone["id"])
        self.assertEqual(self.output.read_text(), self.artifact(2))
        motd.tx_rollback(self.state, second["id"])
        self.assertEqual(self.output.read_text(), self.artifact(1))
        self.assertEqual(self.current()["id"], first["id"])

    def test_uninstall_preserves_outside_hook_edits_and_private_mode(self):
        self.install()
        self.shell.write_text("# Added before\n" + self.shell.read_text() + "# Added after\n")
        self.shell.chmod(0o600)
        self.uninstall()
        self.assertEqual(self.shell.read_text(), "# Added before\n" + self.original_shell + "# Added after\n")
        self.assertEqual(stat.S_IMODE(self.shell.stat().st_mode), 0o600)

    def test_uninstall_preserves_mode_only_shell_change(self):
        self.install()
        self.shell.chmod(0o600)
        self.uninstall()
        self.assertEqual(self.shell.read_text(), self.original_shell)
        self.assertEqual(stat.S_IMODE(self.shell.stat().st_mode), 0o600)

    def test_uninstall_preserves_outside_edits_made_before_upgrade(self):
        self.install()
        self.shell.write_text(self.shell.read_text() + "# User edit before upgrade\n")
        self.shell.chmod(0o600)
        self.install(2)
        self.uninstall()
        self.assertEqual(self.shell.read_text(), self.original_shell + "# User edit before upgrade\n")
        self.assertEqual(stat.S_IMODE(self.shell.stat().st_mode), 0o600)

    def test_uninstall_preserves_second_instance_added_before_upgrade(self):
        self.install()
        other_config = motd.preset_config("home-lab")
        other_config["name"] = "other-dashboard"
        other_output = self.root / "other-dashboard.bash"
        motd.tx_apply(motd.installation_plan(other_config, self.artifact(3), scope="user",
                                           destination=str(other_output), shell_file=str(self.shell),
                                           state_dir=self.state))
        self.install(2)
        self.uninstall()
        self.assertIn("# >>> motd other-dashboard >>>", self.shell.read_text())
        self.assertNotIn("# >>> motd test-dashboard >>>", self.shell.read_text())
        self.assertEqual(other_output.read_text(), self.artifact(3))
        self.assertIn("other-dashboard", motd.active_installs(self.state))

    def test_modified_runtime_blocks_upgrade_and_uninstall(self):
        self.install()
        self.output.write_text("# User-owned customization\n")
        shell_before = self.shell.read_bytes()
        with self.assertRaises(motd.MotdError):
            self.plan(2)
        with self.assertRaises(motd.MotdError):
            motd.uninstall_plan(self.config["name"], self.state)
        self.assertEqual(self.output.read_text(), "# User-owned customization\n")
        self.assertEqual(self.shell.read_bytes(), shell_before)

    def test_modified_managed_block_blocks_upgrade_and_uninstall(self):
        self.install()
        modified = self.shell.read_text().replace("/bin/bash ", "/bin/bash --norc ")
        self.shell.write_text(modified)
        runtime_before = self.output.read_bytes()
        with self.assertRaises(motd.MotdError):
            self.plan(2)
        with self.assertRaises(motd.MotdError):
            motd.uninstall_plan(self.config["name"], self.state)
        self.assertEqual(self.shell.read_text(), modified)
        self.assertEqual(self.output.read_bytes(), runtime_before)

    def test_symlink_runtime_and_shell_file_are_rejected(self):
        unrelated = self.root / "unrelated"
        unrelated.write_text("preserve this\n")
        self.output.symlink_to(unrelated)
        with self.assertRaises(motd.TxError):
            self.plan()
        self.output.unlink()
        self.shell.unlink()
        self.shell.symlink_to(unrelated)
        with self.assertRaises(motd.TxError):
            self.plan()
        self.assertEqual(unrelated.read_text(), "preserve this\n")

    def _run_shell(self, script, *, interactive=False, tty=False, extra_env=None):
        environment = dict(os.environ)
        environment.pop("BASH_ENV", None)
        for key in list(environment):
            if key.startswith("_MOTD_SEEN_"):
                environment.pop(key)
        if extra_env:
            environment.update(extra_env)
        command = ["/bin/bash", "--noprofile", "--norc", "-ic" if interactive else "-c", script]
        if not tty:
            result = subprocess.run(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            return result.stdout.decode()
        master, slave = pty.openpty()
        try:
            result = subprocess.run(command, env=environment, stdout=slave, stderr=subprocess.PIPE, timeout=5)
            os.close(slave)
            slave = None
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            output = bytearray()
            while True:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                output.extend(chunk)
            return output.decode().replace("\r\n", "\n")
        finally:
            os.close(master)
            if slave is not None:
                os.close(slave)

    def test_noninteractive_shells_never_print_dashboard_even_with_tty(self):
        self.config["frequency"] = "interactive"
        self.install()
        script = f"source {shlex.quote(str(self.shell))}; printf 'PAYLOAD\\n'"
        self.assertEqual(self._run_shell(script), "PAYLOAD\n")
        self.assertEqual(self._run_shell(script, tty=True,
                                         extra_env={"SSH_CONNECTION": "192.0.2.1 1234 192.0.2.2 22"}), "PAYLOAD\n")
        self.assertEqual(self._run_shell("printf 'PAYLOAD\\n'", extra_env={"BASH_ENV": str(self.shell)}), "PAYLOAD\n")

    @unittest.skipIf((Path.home() / ".hushlogin").exists(), "real caller hush preference suppresses automatic greeting")
    def test_interactive_hook_runs_once_and_quotes_output_path(self):
        self.config["frequency"] = "interactive"
        quoted_output = self.root / "dashboard ' with spaces.bash"
        self.install(output=quoted_output)
        script = f"source {shlex.quote(str(self.shell))}; source {shlex.quote(str(self.shell))}; printf 'PAYLOAD\\n'"
        self.assertEqual(self._run_shell(script, interactive=True, tty=True), "MOTD-V1\nPAYLOAD\n")

    def test_active_install_repair_after_identical_reinstall(self):
        self.install()
        self.install()
        self.output.unlink()
        motd.tx_apply(motd.repair_installation_plan(self.current()["metadata"]["name"], self.state))
        self.assertEqual(self.output.read_text(), self.artifact())

    def test_active_install_repair_includes_unchanged_hook_after_upgrade(self):
        self.install()
        self.install(2)
        self.shell.unlink()
        motd.tx_apply(motd.repair_installation_plan(self.current()["metadata"]["name"], self.state))
        self.assertTrue(self.shell.exists(), "Latest active install should be repairable without selecting older per-file transactions")
        self.assertIn("# >>> motd test-dashboard >>>", self.shell.read_text())

    def test_active_install_repair_after_rollback_of_rollback(self):
        self.install()
        second = self.install(2)
        undone = motd.tx_rollback(self.state, second["id"])
        motd.tx_rollback(self.state, undone["id"])
        self.assertEqual(self.current()["id"], second["id"])
        self.output.unlink()
        repaired = motd.tx_apply(motd.repair_installation_plan(self.current()["metadata"]["name"], self.state))
        self.assertTrue(self.output.exists(), f"Active install was not repaired: {repaired['metadata']}")
        self.assertEqual(self.output.read_text(), self.artifact(2))


if __name__ == "__main__":
    unittest.main()
