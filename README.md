# Junction for Omarchy

**Every window. Every room. One jump.**

Built by **Nox, Chief Shipper at [RiftLab.ai](https://riftlab.ai/)**.

![Junction preview with sample data](preview.png?rev=riftlab-ai)

The preview uses sample window and session names. The live plugin follows your Omarchy theme.

Search open Hyprland windows and tmux sessions in one theme-aware Omarchy shell overlay. Type any part of an app, title, workspace, or session name; use the arrow keys and Enter, or click a row.

The picker shows your most recently focused other window first, then tmux sessions by activity, then the remaining windows. It labels each window with its workspace. A session selection switches an existing **desktop** tmux client and focuses its terminal; if there is no desktop tmux client, Omarchy opens its configured terminal and attaches to that session. SSH/phone clients are left alone.

## Requirements

- Omarchy with its Quickshell plugin host and Hyprland
- Python 3 and tmux (both included in Omarchy's standard setup)

No daemon, API key, or extra Python package is needed.

## Install

Install Junction from this repository:

```sh
omarchy plugin add https://github.com/sash-rift/omarchy-junction.git --enable
```

Bind a shortcut in `~/.config/hypr/bindings.lua`, choosing a chord free on your system:

```lua
o.bind("SUPER + ALT + Y", "Junction", "omarchy-shell shell toggle io.github.sash-rift.junction")
```

Reload Hyprland with `hyprctl reload`, then press the shortcut. You can also launch the picker directly with:

```sh
omarchy-shell shell summon io.github.sash-rift.junction
```

`omarchy plugin remove io.github.sash-rift.junction` uninstalls the plugin. Remove the shortcut line if you added one.

## Customize

The stock configuration uses Hyprland's workspace names, tmux's default socket, and Omarchy's configured terminal. No config file is needed. To override workspace names or use another tmux socket, copy `config.example.json` to `~/.config/omarchy/junction.json` and edit it. This file sits outside the plugin folder so plugin updates preserve it.

`workspaceLabels` maps workspace IDs to labels. `tmuxSocket` accepts a tmux socket name (passed with `-L`) or an absolute socket path (passed with `-S`). Leave it empty for tmux's default server.

Windows in hidden or special workspaces are omitted. Each Hyprland window appears separately, including multiple windows from one app; browser tabs within one window are not separate entries. Sessions on other tmux sockets are omitted unless configured.

## Development

```sh
omarchy plugin validate .
/usr/lib/qt6/bin/qmllint -I /usr/share/omarchy/shell Junction.qml
python3 -m unittest discover -s tests -v
```

The backend uses direct argument arrays for commands. It checks a selected window against currently open Hyprland windows and a selected room against currently running tmux sessions before activation.

The Junction mark is in `assets/junction-mark.svg`. The marketplace preview source is `assets/preview.svg`; `preview.png` is its rendered copy. The brand colors in these assets are for the listing only. The overlay reads Omarchy's live menu colors.
