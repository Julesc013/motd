"""Transaction acceptance checks. All target files live in temporary directories.

Normal use imports ../motd.py. MOTD_TEST_MODULE can select the standalone
transaction fragment while the one-file application is being assembled.
"""
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

_source = Path(os.environ.get("MOTD_TEST_MODULE", Path(__file__).resolve().parents[1] / "motd.py"))
_spec = importlib.util.spec_from_file_location("motd_transaction_test_subject", _source)
motd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(motd)


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="motd-transactions-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = str(self.root / "private" / "state")

    def file(self, name, data=b"original\n", mode=0o640):
        path = self.root / name
        path.write_bytes(data)
        path.chmod(mode)
        return str(path)

    def change(self, path, content="generated\n", mode=0o755):
        return {"path": path, "content": content, "mode": mode}

    def install(self, changes, metadata=None):
        return motd.tx_apply(motd.tx_plan(changes, self.state, metadata))

    def assert_code(self, code, callable_, *args, **kwargs):
        with self.assertRaises(motd.TxError) as caught:
            callable_(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_plan_is_read_only_and_stage_does_not_touch_targets(self):
        path = self.file("target")
        identity = Path(path).stat()
        plan = motd.tx_plan([self.change(path)], self.state)
        self.assertFalse(Path(self.state).exists())
        self.assertEqual(Path(path).read_bytes(), b"original\n")
        staged = motd.tx_stage(plan)
        self.assertEqual(staged["status"], "staged")
        self.assertEqual(Path(path).stat().st_ino, identity.st_ino)
        self.assertEqual(Path(path).read_bytes(), b"original\n")
        self.assertTrue(Path(staged["record_path"]).is_file())

    def test_create_replace_remove_and_exact_binary_rollback(self):
        binary = b"\x00\xffold\r\n"
        existing = self.file("existing", binary, 0o601)
        removed = self.file("removed", b"keep me", 0o644)
        created = str(self.root / "created")
        record = self.install([self.change(existing), self.change(removed, None), self.change(created)])
        self.assertEqual(record["status"], "applied")
        self.assertEqual(Path(existing).read_text(), "generated\n")
        self.assertEqual(stat.S_IMODE(Path(existing).stat().st_mode), 0o755)
        self.assertFalse(Path(removed).exists())
        inverse = motd.tx_rollback(self.state, record["id"])
        self.assertEqual(inverse["status"], "applied")
        self.assertEqual([change["path"] for change in inverse["changes"]], [created, removed, existing])
        self.assertEqual(Path(existing).read_bytes(), binary)
        self.assertEqual(stat.S_IMODE(Path(existing).stat().st_mode), 0o601)
        self.assertEqual(Path(removed).read_bytes(), b"keep me")
        self.assertFalse(Path(created).exists())
        self.assertEqual(motd.tx_history(self.state)[0]["rolled_back_by"], inverse["id"])

    @unittest.skipUnless(os.geteuid() == 0, "numeric ownership restoration requires root")
    def test_existing_numeric_ownership_is_preserved_and_restored(self):
        path = self.file("owned", mode=0o640)
        os.chown(path, 12345, 12346)
        record = self.install([self.change(path)])
        self.assertEqual((Path(path).stat().st_uid, Path(path).stat().st_gid), (12345, 12346))
        motd.tx_rollback(self.state, record["id"])
        self.assertEqual((Path(path).stat().st_uid, Path(path).stat().st_gid), (12345, 12346))

    def test_public_owner_field_preserves_requested_current_identity_and_validates(self):
        path = str(self.root / "owned-new")
        change = self.change(path)
        change["owner"] = [os.geteuid(), os.getegid()]
        plan = motd.tx_plan([change], self.state)
        after = plan["changes"][0]["after"]
        self.assertEqual((after["uid"], after["gid"]), (os.geteuid(), os.getegid()))
        motd.tx_apply(plan)
        self.assertEqual((Path(path).stat().st_uid, Path(path).stat().st_gid), (os.geteuid(), os.getegid()))
        for invalid in ([True, 0], [-1, 0], ["0", 0], [0], [0, 0, 0], [2**32 - 1, 0]):
            with self.subTest(owner=invalid):
                bad = self.change(path)
                bad["owner"] = invalid
                self.assert_code("invalid_owner", motd.tx_plan, [bad], self.state)
    def test_identical_writes_and_missing_deletes_are_noops(self):
        path = self.file("same", b"same", 0o644)
        before = Path(path).stat()
        plan = motd.tx_plan([self.change(path, "same", 0o644), self.change(str(self.root / "absent"), None)], self.state)
        self.assertEqual(plan["change_count"], 0)
        record = motd.tx_apply(plan)
        self.assertEqual(record["status"], "noop")
        self.assertEqual((Path(path).stat().st_ino, Path(path).stat().st_mtime_ns), (before.st_ino, before.st_mtime_ns))
        self.assertEqual(motd.tx_apply(plan)["id"], record["id"])

    def test_plan_rechecks_content_and_mode_drift(self):
        path = self.file("target")
        plan = motd.tx_plan([self.change(path)], self.state)
        Path(path).write_text("user edited")
        self.assert_code("drift", motd.tx_stage, plan)
        self.assertEqual(Path(path).read_text(), "user edited")
        plan = motd.tx_plan([self.change(path)], self.state)
        Path(path).chmod(0o600)
        self.assert_code("drift", motd.tx_apply, plan)

    def test_apply_rechecks_after_separate_stage(self):
        path = self.file("target")
        staged = motd.tx_stage(motd.tx_plan([self.change(path)], self.state))
        Path(path).write_text("edited after preview")
        error = self.assert_code("drift", motd.tx_apply, staged)
        self.assertEqual(error.record["id"], staged["id"])
        self.assertEqual(Path(path).read_text(), "edited after preview")

    def test_rollback_refuses_drift_before_changing_any_file(self):
        first, second = self.file("first"), self.file("second")
        record = self.install([self.change(first), self.change(second)])
        Path(second).write_text("user custom")
        self.assert_code("drift", motd.tx_rollback, self.state, record["id"])
        self.assertEqual(Path(first).read_text(), "generated\n")
        self.assertEqual(Path(second).read_text(), "user custom")

    def test_rollback_refuses_superseded_ownership(self):
        path = self.file("target")
        first = self.install([self.change(path, "version one")])
        self.install([self.change(path, "version two")])
        self.assert_code("superseded", motd.tx_rollback, self.state, first["id"])
        self.assertEqual(Path(path).read_text(), "version two")

    def test_repeated_rollback_after_redo_uses_effective_inverse(self):
        path = self.file("target")
        first = self.install([self.change(path, "version one")])
        second = self.install([self.change(path, "version two")])
        inverse = motd.tx_rollback(self.state, second["id"])
        self.assertEqual(Path(path).read_text(), "version one")
        motd.tx_rollback(self.state, inverse["id"])
        self.assertEqual(Path(path).read_text(), "version two")
        history = {r["id"]: r for r in motd.tx_history(self.state)}
        self.assertNotIn("rolled_back_by", history[second["id"]])
        again = motd.tx_rollback(self.state, second["id"])
        self.assertNotEqual(again["id"], inverse["id"])
        self.assertEqual(Path(path).read_text(), "version one")
        # Rolling back an already undone source remains idempotent.
        self.assertEqual(motd.tx_rollback(self.state, second["id"])["id"], again["id"])
        motd.tx_rollback(self.state, first["id"])
        self.assertEqual(Path(path).read_bytes(), b"original\n")

    def test_undo_restores_previous_owner_for_missing_file_repair(self):
        path = self.file("target")
        first = self.install([self.change(path, "version one")])
        second = self.install([self.change(path, "version two")])
        motd.tx_rollback(self.state, second["id"])
        Path(path).unlink()
        repaired = motd.tx_repair(self.state, first["id"])
        self.assertEqual(repaired["status"], "applied")
        self.assertEqual(Path(path).read_text(), "version one")

    def test_normal_failure_compensates_prior_writes(self):
        first, second = self.file("first"), self.file("second")
        plan = motd.tx_plan([self.change(first), self.change(second)], self.state)
        original_replace = motd._tx_replace
        fired = False

        def fail_second(path, *args, **kwargs):
            nonlocal fired
            if path == second and not fired:
                fired = True
                raise OSError("simulated full disk")
            return original_replace(path, *args, **kwargs)

        with mock.patch.object(motd, "_tx_replace", side_effect=fail_second):
            error = self.assert_code("apply_failed", motd.tx_apply, plan)
        self.assertEqual(error.record["status"], "failed_rolled_back")
        self.assertEqual(Path(first).read_bytes(), b"original\n")
        self.assertEqual(Path(second).read_bytes(), b"original\n")

    def test_interruption_after_rename_is_recoverable_from_durable_intent(self):
        path = self.file("target")
        original_replace = motd._tx_replace

        def interrupt_after_replace(candidate, *args, **kwargs):
            result = original_replace(candidate, *args, **kwargs)
            if candidate == path:
                raise KeyboardInterrupt()
            return result

        plan = motd.tx_plan([self.change(path)], self.state)
        with mock.patch.object(motd, "_tx_replace", side_effect=interrupt_after_replace):
            error = self.assert_code("interrupted", motd.tx_apply, plan)
        self.assertTrue(motd.tx_error(error)["recoverable"])
        self.assertEqual(Path(path).read_text(), "generated\n")
        self.assertIn("recovery_required", {f["state"] for f in motd.tx_audit(self.state)})
        recovered = motd.tx_recover(self.state, plan["id"])
        self.assertEqual(recovered["status"], "recovered")
        self.assertEqual(Path(path).read_bytes(), b"original\n")

    def test_recovery_preserves_external_edit_and_blocks_new_apply(self):
        path = self.file("target")
        original_replace = motd._tx_replace

        def stop_after(candidate, *args, **kwargs):
            result = original_replace(candidate, *args, **kwargs)
            if candidate == path:
                raise KeyboardInterrupt()
            return result

        plan = motd.tx_plan([self.change(path)], self.state)
        with mock.patch.object(motd, "_tx_replace", side_effect=stop_after):
            self.assert_code("interrupted", motd.tx_apply, plan)
        Path(path).write_text("subsequent user edit")
        recovered = motd.tx_recover(self.state, plan["id"])
        self.assertEqual(recovered["status"], "needs_recovery")
        self.assertEqual(Path(path).read_text(), "subsequent user edit")
        next_plan = motd.tx_plan([self.change(str(self.root / "next"))], self.state)
        self.assert_code("recovery_required", motd.tx_apply, next_plan)
        Path(path).write_bytes(b"original\n")
        Path(path).chmod(0o640)
        self.assertEqual(motd.tx_recover(self.state, plan["id"])["status"], "recovered")

    def test_recovery_does_not_touch_unattempted_targets(self):
        first, second = self.file("first"), self.file("second")
        original_replace = motd._tx_replace

        def interrupt(candidate, *args, **kwargs):
            result = original_replace(candidate, *args, **kwargs)
            if candidate == first:
                raise KeyboardInterrupt()
            return result

        plan = motd.tx_plan([self.change(first), self.change(second)], self.state)
        with mock.patch.object(motd, "_tx_replace", side_effect=interrupt):
            self.assert_code("interrupted", motd.tx_apply, plan)
        Path(second).write_text("generated\n")
        Path(second).chmod(0o755)
        motd.tx_recover(self.state, plan["id"])
        self.assertEqual(Path(first).read_bytes(), b"original\n")
        self.assertEqual(Path(second).read_text(), "generated\n")

    def test_partial_staging_can_be_cancelled_without_target_mutation(self):
        path = self.file("target")
        original_write = motd._tx_private_write

        def fail_blob(candidate, *args, **kwargs):
            if candidate.endswith("0000.after"):
                raise OSError("staging disk failure")
            return original_write(candidate, *args, **kwargs)

        plan = motd.tx_plan([self.change(path)], self.state)
        with mock.patch.object(motd, "_tx_private_write", side_effect=fail_blob):
            error = self.assert_code("stage_failed", motd.tx_stage, plan)
        self.assertEqual(error.record["id"], plan["id"])
        self.assertEqual(Path(path).read_bytes(), b"original\n")
        cancelled = motd.tx_recover(self.state, plan["id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(motd.tx_audit(self.state), [])

    def test_process_exit_after_replace_uses_persisted_recovery_intent(self):
        path = self.file("target")
        runner = '''import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("subject", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
original = m._tx_replace
def crash(path, *args, **kwargs):
    value = original(path, *args, **kwargs)
    if path == sys.argv[2]:
        os._exit(77)
    return value
m._tx_replace = crash
plan = m.tx_plan([{"path": sys.argv[2], "content": "generated\\n", "mode": 0o755}], sys.argv[3])
m.tx_apply(plan)
'''
        result = subprocess.run([sys.executable, "-c", runner, str(_source), path, self.state],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        self.assertEqual(result.returncode, 77, result.stderr.decode())
        records = motd.tx_history(self.state)
        self.assertEqual(records[-1]["status"], "applying")
        self.assertEqual(Path(path).read_text(), "generated\n")
        self.assertEqual(motd.tx_recover(self.state, records[-1]["id"])["status"], "recovered")
        self.assertEqual(Path(path).read_bytes(), b"original\n")

    def test_orphan_stage_abandonment_never_infers_target_paths(self):
        path = self.file("target")
        plan = motd.tx_plan([self.change(path)], self.state)
        staged = motd.tx_stage(plan)
        Path(staged["record_path"]).unlink()
        self.assertIn("invalid_record", {item["state"] for item in motd.tx_audit(self.state)})
        abandoned = motd.tx_recover(self.state, staged["id"])
        self.assertEqual(abandoned["status"], "abandoned")
        self.assertEqual(Path(path).read_bytes(), b"original\n")
        self.assertTrue((Path(staged["directory"]) / "0000.before").is_file())

    def test_repair_restores_missing_only_and_preserves_modified(self):
        missing, edited = str(self.root / "missing"), str(self.root / "edited")
        record = self.install([self.change(missing), self.change(edited)])
        Path(missing).unlink()
        Path(edited).write_text("keep customization")
        repair = motd.tx_repair(self.state, record["id"])
        self.assertEqual(Path(missing).read_text(), "generated\n")
        self.assertEqual(Path(edited).read_text(), "keep customization")
        self.assertEqual(repair["metadata"]["preserved"], [{"path": edited, "reason": "modified"}])
        findings = {f["path"]: f["state"] for f in motd.tx_audit(self.state)}
        self.assertEqual(findings[missing], "ok")
        self.assertEqual(findings[edited], "modified")

    def test_repair_does_not_resurrect_newer_intentional_deletion(self):
        path = str(self.root / "target")
        original = self.install([self.change(path)])
        self.install([self.change(path, None)])
        repaired = motd.tx_repair(self.state, original["id"])
        self.assertEqual(repaired["status"], "noop")
        self.assertFalse(Path(path).exists())
        self.assertEqual(repaired["metadata"]["preserved"][0]["reason"], "superseded")

    def test_rollback_original_after_repair_preserves_original_preimage(self):
        path = self.file("target", b"before install", 0o640)
        record = self.install([self.change(path)])
        Path(path).unlink()
        motd.tx_repair(self.state, record["id"])
        motd.tx_rollback(self.state, record["id"])
        self.assertEqual(Path(path).read_bytes(), b"before install")
        self.assertEqual(stat.S_IMODE(Path(path).stat().st_mode), 0o640)

    def test_rejects_symlinks_nonregular_hardlinks_and_symlink_parents(self):
        original = self.file("original")
        link = self.root / "symlink"
        link.symlink_to(original)
        self.assert_code("unsafe_target", motd.tx_plan, [self.change(str(link))], self.state)
        hardlink = self.root / "hardlink"
        os.link(original, hardlink)
        self.assert_code("unsafe_target", motd.tx_plan, [self.change(str(hardlink))], self.state)
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        self.assert_code("unsafe_target", motd.tx_plan, [self.change(str(fifo))], self.state)
        directory = self.root / "folder"
        directory.mkdir()
        parent_link = self.root / "parent-link"
        parent_link.symlink_to(directory, target_is_directory=True)
        self.assert_code("unsafe_path", motd.tx_plan, [self.change(str(parent_link / "target"))], self.state)

    def test_rejects_traversal_duplicate_targets_state_overlap_and_root_state(self):
        target = str(self.root / "target")
        self.assert_code("invalid_path", motd.tx_plan, [self.change(str(self.root) + "/../target")], self.state)
        self.assert_code("duplicate_target", motd.tx_plan, [self.change(target), self.change(target)], self.state)
        self.assert_code("unsafe_target", motd.tx_plan, [self.change(self.state + "/file")], self.state)
        self.assert_code("unsafe_state", motd.tx_plan, [self.change(target)], "/")
        self.assert_code("missing_parent", motd.tx_plan, [self.change(str(self.root / "absent" / "file"))], self.state)

    def test_private_state_and_complete_recovery_archives(self):
        text = "# config\nlabel = 'hello'\n" + ("# preserved\n" * 25000)
        record = self.install([self.change(str(self.root / "target"))],
                              {"config_toml": text, "artifact_text": "#!/bin/bash\necho hello\n", "artifact_suffix": ".bash"})
        self.assertEqual(Path(record["archives"]["config_toml"]["path"]).read_text(), text)
        self.assertTrue(record["archives"]["artifact_text"]["path"].endswith("output.bash"))
        self.assertEqual(motd.tx_history(self.state)[0]["metadata"]["config_toml"], text)
        for parent, dirs, files in os.walk(self.state):
            self.assertEqual(stat.S_IMODE(os.stat(parent).st_mode), 0o700)
            for filename in files:
                self.assertEqual(stat.S_IMODE(os.stat(os.path.join(parent, filename)).st_mode), 0o600)

    def test_lock_rejects_concurrent_mutation(self):
        plan = motd.tx_plan([self.change(str(self.root / "target"))], self.state)
        with motd._tx_locked(self.state, create=True):
            self.assert_code("busy", motd.tx_apply, plan)
        self.assertFalse((self.root / "target").exists())

    def test_corrupted_backup_is_rejected_before_apply(self):
        path = self.file("target")
        staged = motd.tx_stage(motd.tx_plan([self.change(path)], self.state))
        (Path(staged["directory"]) / "0000.before").write_text("altered backup")
        self.assert_code("corrupt_backup", motd.tx_apply, staged)
        self.assertEqual(Path(path).read_bytes(), b"original\n")

    def test_unmarked_or_unprotected_state_is_not_adopted(self):
        state = self.root / "state-other"
        state.mkdir(mode=0o700)
        (state / "unrelated.txt").write_text("do not touch")
        self.assert_code("unsafe_state", motd.tx_plan, [], str(state))
        (state / "unrelated.txt").unlink()
        state.chmod(0o755)
        self.assert_code("unsafe_state", motd.tx_plan, [], str(state))


if __name__ == "__main__":
    unittest.main()
