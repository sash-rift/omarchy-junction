"""Tests for picker ordering and desktop-only tmux activation."""

import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("window_rooms_backend", Path(__file__).resolve().parents[1] / "backend.py")
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)


def window(address, app, workspace, focus, pid=10):
    return {"address": address, "class": app, "title": f"{app} title", "mapped": True,
            "hidden": False, "workspace": {"id": workspace, "name": str(workspace)},
            "focusHistoryID": focus, "pid": pid}


class BackendTests(unittest.TestCase):
    def test_rows_keep_duplicate_app_windows_and_use_workspace_labels(self):
        windows = [window("0x1", "browser", 1, 0), window("0x2", "browser", 2, 1),
                   window("0x3", "terminal", 1, 2)]
        with patch.object(backend, "visible_windows", return_value=windows), \
             patch.object(backend, "hypr", return_value=windows[2]), \
             patch.object(backend, "session_list", return_value=[("Work", 12)]), \
             patch.object(backend, "configuration", return_value={"workspaceLabels": {"2": "Build"}}):
            result = backend.rows()
        self.assertEqual([row["kind"] for row in result], ["recent", "room", "window", "current"])
        self.assertEqual(len([row for row in result if "Browser" in row["name"]]), 2)
        self.assertIn("2 Build", result[2]["detail"])

    def test_desktop_client_skips_remote_tmux_client(self):
        terminal = window("0x5", "foot", 1, 0, pid=500)
        clients = subprocess.CompletedProcess([], 0, "/dev/pts/4\t200\n/dev/pts/5\t300\n", "")
        with patch.object(backend, "tmux", return_value=clients), \
             patch.object(backend, "hypr", return_value=terminal), \
             patch.object(backend, "visible_windows", return_value=[terminal]), \
             patch.object(backend, "belongs_to", side_effect=lambda client, parent: client == 300):
            self.assertEqual(backend.desktop_client(), ("/dev/pts/5", "0x5"))

    def test_room_switches_existing_desktop_client(self):
        calls = []
        def fake_run(*args):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, "", "")
        with patch.object(backend, "session_list", return_value=[("Work", 1)]), \
             patch.object(backend, "desktop_client", return_value=("/dev/pts/5", "0x5")), \
             patch.object(backend, "visible_windows", return_value=[window("0x5", "foot", 1, 0)]), \
             patch.object(backend, "tmux", side_effect=fake_run), \
             patch.object(backend, "run", side_effect=fake_run):
            self.assertEqual(backend.activate("room", "Work"), 0)
        self.assertEqual(calls[0], ("switch-client", "-c", "/dev/pts/5", "-t", "Work"))
        self.assertEqual(calls[1][0:2], ("hyprctl", "dispatch"))

    def test_room_without_desktop_client_uses_omarchy_terminal(self):
        calls = []
        def fake_run(*args):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, "", "")
        with patch.object(backend, "session_list", return_value=[("Work", 1)]), \
             patch.object(backend, "desktop_client", return_value=None), \
             patch.object(backend, "configuration", return_value={}), \
             patch.object(backend, "run", side_effect=fake_run):
            self.assertEqual(backend.activate("room", "Work"), 0)
        self.assertEqual(calls, [("omarchy-launch-terminal", "tmux", "attach-session", "-t", "Work")])

    def test_stale_or_invalid_targets_do_not_dispatch(self):
        with patch.object(backend, "visible_windows", return_value=[]), \
             patch.object(backend, "session_list", return_value=[]), \
             patch.object(backend, "run") as command:
            self.assertEqual(backend.activate("window", "0x123"), 1)
            self.assertEqual(backend.activate("window", "bad"), 2)
            self.assertEqual(backend.activate("room", "gone"), 1)
            command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
