#!/usr/bin/env python3
"""Window Rooms: Hyprland/tmux discovery and activation for the shell overlay."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


CONFIG = Path.home() / ".config/omarchy/window-rooms.json"
ADDRESS = re.compile(r"0x[0-9a-fA-F]+\Z")


def run(*argv):
    try:
        return subprocess.run(argv, text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return subprocess.CompletedProcess(argv, 127, "", "not installed")


def configuration():
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def tmux(*args):
    socket = configuration().get("tmuxSocket", "")
    if isinstance(socket, str) and socket:
        option = "-S" if socket.startswith("/") else "-L"
        return run("tmux", option, socket, *args)
    return run("tmux", *args)


def hypr(name):
    response = run("hyprctl", "-j", name)
    try:
        return json.loads(response.stdout) if response.returncode == 0 else ([] if name == "clients" else {})
    except ValueError:
        return [] if name == "clients" else {}


def tidy(value, maximum=100):
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value[: maximum - 1] + "…" if len(value) > maximum else value


def application_name(window):
    window_class = str(window.get("class") or "")
    common = {
        "com.mitchellh.ghostty": "Ghostty",
        "org.codeberg.dnkl.foot": "Foot",
        "google-chrome": "Chrome",
        "firefox": "Firefox",
        "kitty": "Kitty",
        "Alacritty": "Alacritty",
    }
    if window_class in common:
        return common[window_class]
    if window_class.startswith("chrome-"):
        return tidy(window_class[7:].split("__", 1)[0].replace("-", " ").title(), 35)
    return tidy(window_class.rsplit(".", 1)[-1].replace("_", " ").replace("-", " ").title(), 35) or "Window"


def workspace_label(window, labels):
    workspace = window.get("workspace") or {}
    number = workspace.get("id", 0)
    name = labels.get(str(number)) or workspace.get("name", "")
    if not name or str(name) == str(number):
        return f"Workspace {number}"
    return f"{number} {tidy(name, 35)}"


def session_list():
    response = tmux("list-sessions", "-F", "#{session_name}\t#{session_activity}")
    if response.returncode:
        return []
    sessions = []
    for line in response.stdout.splitlines():
        try:
            name, activity = line.rsplit("\t", 1)
            sessions.append((name, int(activity)))
        except ValueError:
            continue
    return sorted(sessions, key=lambda pair: -pair[1])


def visible_windows():
    windows = hypr("clients")
    if not isinstance(windows, list):
        return []
    return [w for w in windows if isinstance(w, dict) and w.get("mapped")
            and not w.get("hidden") and (w.get("workspace") or {}).get("id", 0) > 0
            and ADDRESS.fullmatch(str(w.get("address", "")))]


def rows():
    config = configuration()
    labels = config.get("workspaceLabels", {})
    if not isinstance(labels, dict):
        labels = {}
    windows = visible_windows()
    active = hypr("activewindow")
    if not isinstance(active, dict):
        active = {}
    active_address = active.get("address")
    active_workspace = (active.get("workspace") or {}).get("id")
    remaining = [w for w in windows if w.get("address") != active_address]
    remaining.sort(key=lambda w: (
        (w.get("workspace") or {}).get("id") != active_workspace,
        max(w.get("focusHistoryID", 9999), 0),
    ))
    ordered = []
    if remaining:
        ordered.append((remaining.pop(0), "recent"))
    ordered.extend((name, "room") for name, _ in session_list())
    ordered.extend((window, "window") for window in remaining)
    ordered.extend((w, "current") for w in windows if w.get("address") == active_address)
    result = []
    for item, kind in ordered:
        if kind == "room":
            result.append({"kind": kind, "target": item, "name": tidy(item),
                           "detail": "tmux session", "search": f"room tmux {item}"})
        else:
            app = application_name(item)
            title = tidy(item.get("title"))
            place = workspace_label(item, labels)
            detail = f"{place} · {kind} window" if kind != "window" else place
            result.append({"kind": kind, "target": item["address"],
                           "name": app if not title or title == app else f"{app} · {title}",
                           "detail": detail, "search": f"{app} {title} {place} {kind}"})
    return result


def parent_pid(pid):
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return 0


def belongs_to(client_pid, window_pid):
    for _ in range(20):
        if client_pid == window_pid:
            return True
        client_pid = parent_pid(client_pid)
        if client_pid <= 1:
            return False
    return False


def desktop_client():
    response = tmux("list-clients", "-F", "#{client_tty}\t#{client_pid}")
    if response.returncode:
        return None
    clients = []
    for line in response.stdout.splitlines():
        try:
            tty, pid = line.rsplit("\t", 1)
            clients.append((tty, int(pid)))
        except ValueError:
            continue
    active = hypr("activewindow")
    active_address = active.get("address") if isinstance(active, dict) else None
    windows = sorted(visible_windows(), key=lambda w: (
        w.get("address") != active_address,
        max(w.get("focusHistoryID", 9999), 0),
    ))
    for window in windows:
        pid = window.get("pid")
        if not isinstance(pid, int) or pid <= 1:
            continue
        for tty, client_pid in clients:
            if belongs_to(client_pid, pid):
                return tty, window["address"]
    return None


def activate(kind, target):
    if kind == "window":
        if not ADDRESS.fullmatch(target):
            return 2
        if target not in {w["address"] for w in visible_windows()}:
            return 1
        return run("hyprctl", "dispatch", f'hl.dsp.focus({{ window = "address:{target}" }})').returncode
    if kind != "room":
        return 2
    if target not in {name for name, _ in session_list()}:
        return 1
    client = desktop_client()
    if client:
        tty, address = client
        switched = tmux("switch-client", "-c", tty, "-t", target)
        if switched.returncode:
            return switched.returncode
        return activate("window", address)
    socket = configuration().get("tmuxSocket", "")
    prefix = ("-S", socket) if isinstance(socket, str) and socket.startswith("/") else (
        ("-L", socket) if isinstance(socket, str) and socket else ())
    return run("omarchy-launch-terminal", "tmux", *prefix, "attach-session", "-t", target).returncode


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list")
    pick = sub.add_parser("activate")
    pick.add_argument("kind", choices=("window", "room"))
    pick.add_argument("target")
    args = parser.parse_args()
    if args.action == "list":
        print(json.dumps(rows(), ensure_ascii=False))
        return 0
    return activate(args.kind, args.target)


if __name__ == "__main__":
    sys.exit(main())
