"""Controller-only tests using fake workers, with no simulation or seed trials."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from experiments.v4_recovery import run as recovery


class RecoveryControl(unittest.TestCase):
    def test_report_retains_old_failure_without_blocking_authorized_recovery(self):
        from experiments.v4_paper.build_report import campaign_complete, campaign_halted
        states = {"v4_formal":{"queue_status":"halted","completed":70},
                  "v4_external":{"queue_status":"completed","completed":27},
                  "v4_recovery":{"queue_status":"running","completed":0}}
        self.assertFalse(campaign_complete(states))
        self.assertFalse(campaign_halted(states))
        states["v4_recovery"].update(queue_status="completed",completed=23)
        self.assertTrue(campaign_complete(states))
        states["v4_recovery"].update(queue_status="halted",completed=22)
        self.assertFalse(campaign_complete(states))
        self.assertTrue(campaign_halted(states))
        states["v4_recovery"].update(completed=15)
        states["v4_recovery2"] = {"queue_status":"running","completed":0}
        self.assertFalse(campaign_complete(states))
        self.assertFalse(campaign_halted(states))
        states["v4_recovery2"].update(queue_status="completed",completed=8)
        self.assertTrue(campaign_complete(states))

    def test_failure_stops_dispatch_and_retains_attempt(self):
        self.check_queue(fail=True)

    def test_success_continues_remaining_cells_once(self):
        self.check_queue(fail=False)

    def check_queue(self, fail):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = folder / "manifest.json"
            manifest.write_text("{}")
            jobs = [{"key":recovery.RETRY},{"key":"unstarted/a"},{"key":"unstarted/b"}]
            started = []

            class FakeProcess:
                def __init__(self, cmd, **kwargs):
                    self.key = cmd[-1]
                    self.pid = len(started)+1
                    started.append(self.key)
                    if not fail:
                        recovery.core.write(folder / "runs" / self.key / "result.json", {})
                def poll(self):
                    return 3221225477 if fail else 0

            with patch.object(recovery,"HERE",folder), patch.object(recovery,"MANIFEST",manifest), \
                 patch.object(recovery,"INDEX",folder / "index.json"), \
                 patch.object(recovery,"validate",return_value={"jobs":jobs}), \
                 patch.object(recovery.subprocess,"Popen",FakeProcess), patch.object(recovery.time,"sleep"):
                if fail:
                    with self.assertRaises(SystemExit): recovery.queue()
                else: recovery.queue()
                data = recovery.core.read(folder / "index.json")
                self.assertEqual(started,[recovery.RETRY] if fail else [j["key"] for j in jobs])
                self.assertEqual(data["queue_status"],"halted" if fail else "completed")
                self.assertEqual(data["unstarted_windows"],2 if fail else 0)
                self.assertEqual(data["jobs"][recovery.RETRY]["attempt_number"],2)
                with self.assertRaises(AssertionError): recovery.queue()

    def test_only_output_destination_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old, new = root / "original", root / "recovery"
            new.mkdir()
            manifest = new / "manifest.json"
            manifest.write_text("{}")
            old_log = old / "runs" / recovery.RETRY / "worker.log"
            old_log.parent.mkdir(parents=True)
            old_log.write_text("original failure")
            writer = recovery.core.write

            def frozen_worker(key):
                recovery.core.write(old / "runs" / key / "result.json",{"metric":123})

            m = {"jobs":[{"key":recovery.RETRY}],"retry_keys":[recovery.RETRY],"authorization":"test"}
            with patch.object(recovery,"HERE",new), patch.object(recovery,"MANIFEST",manifest), \
                 patch.object(recovery.core,"HERE",old), patch.object(recovery,"validate",return_value=m), \
                 patch.object(recovery.core,"run_one",frozen_worker):
                recovery.one(recovery.RETRY)
                result = recovery.core.read(new / "runs" / recovery.RETRY / "result.json")
                self.assertEqual(result["metric"],123)
                self.assertEqual(result["attempt_number"],2)
                self.assertFalse((old_log.parent / "result.json").exists())
                self.assertEqual(old_log.read_text(),"original failure")
                self.assertIs(recovery.core.write,writer)
                with self.assertRaises(AssertionError): recovery.one(recovery.RETRY)


if __name__ == "__main__": unittest.main()
