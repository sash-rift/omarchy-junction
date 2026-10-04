import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import QtQuick
import qs.Commons
import qs.Ui

Item {
  id: root

  property var shell: null
  property var manifest: null
  property bool opened: false
  property bool loading: false
  property string filterText: ""
  property int selectedIndex: 0
  property var allRows: []
  readonly property string pluginId: "io.github.sash-rift.window-rooms"
  readonly property string backendPath: Quickshell.env("HOME") + "/.config/omarchy/plugins/" + pluginId + "/backend.py"

  property color background: Color.menu.background
  property color foreground: Color.menu.text
  property color selectedBackground: Color.menu.selectedBackground
  property color selectedText: Color.menu.selectedText
  property color scrim: Color.menu.scrim
  property var borderSpec: Border.surfaceSpec("menu", "border", Color.menu.border, Math.max(1, Style.space(2)))
  property string fontFamily: Style.font.menuFamily
  property int padding: Style.spacing.panelPadding

  function open(payloadJson) {
    opened = true
    filterText = ""
    selectedIndex = 0
    allRows = []
    loading = true
    visibleRows.clear()
    if (!listProc.running) listProc.running = true
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  function close() { opened = false }

  function dismiss() {
    opened = false
    if (shell && typeof shell.hide === "function") shell.hide(pluginId)
  }

  function toggle() { if (opened) dismiss(); else open("{}") }

  function loadRows(raw) {
    loading = false
    try {
      var parsed = JSON.parse(raw)
      allRows = Array.isArray(parsed) ? parsed : []
    } catch (error) {
      allRows = []
      console.warn("Window Rooms: could not parse backend output:", error)
    }
    rebuild()
  }

  function rebuild() {
    var words = filterText.toLowerCase().trim().split(/\s+/).filter(function(word) { return word.length > 0 })
    visibleRows.clear()
    for (var i = 0; i < allRows.length; ++i) {
      var row = allRows[i]
      var haystack = String(row.search || (row.name + " " + row.detail)).toLowerCase()
      if (words.every(function(word) { return haystack.indexOf(word) >= 0 })) {
        visibleRows.append({ rowName: String(row.name), rowDetail: String(row.detail),
                             rowKind: String(row.kind), rowTarget: String(row.target) })
      }
    }
    selectedIndex = Math.max(0, Math.min(selectedIndex, visibleRows.count - 1))
    Qt.callLater(function() {
      if (visibleRows.count) results.positionViewAtIndex(selectedIndex, ListView.Contain)
    })
  }

  function activate(index) {
    if (index < 0 || index >= visibleRows.count) return
    var row = visibleRows.get(index)
    var kind = row.rowKind === "room" ? "room" : "window"
    dismiss()
    Quickshell.execDetached(["python3", backendPath, "activate", kind, row.rowTarget])
  }

  ListModel { id: visibleRows }

  Process {
    id: listProc
    command: ["python3", root.backendPath, "list"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.loadRows(text)
    }
    onExited: if (root.loading) root.loadRows("[]")
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "window-rooms"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    exclusionMode: ExclusionMode.Ignore

    Rectangle { anchors.fill: parent; color: root.scrim }
    MouseArea { anchors.fill: parent; onClicked: root.dismiss() }

    BorderSurface {
      id: card
      width: Math.min(640, panel.width - Style.gapsOut * 2)
      height: Math.min(540, panel.height - Style.gapsOut * 2)
      anchors.centerIn: parent
      radius: Style.cornerRadius
      color: root.background
      borderSpec: root.borderSpec
      padding: root.padding

      MouseArea { anchors.fill: parent; onClicked: {} }

      Item {
        id: keyCatcher
        anchors.fill: parent
        focus: true
        Keys.priority: Keys.BeforeItem
        Keys.onPressed: function(event) {
          if (event.key === Qt.Key_Escape) {
            if (root.filterText) { root.filterText = ""; root.rebuild() }
            else root.dismiss()
            event.accepted = true
          } else if (Util.editsFilter(event, root.filterText)) {
            root.filterText = Util.editedFilter(event, root.filterText)
            root.selectedIndex = 0
            root.rebuild()
            event.accepted = true
          } else if (event.key === Qt.Key_Up || event.key === Qt.Key_Down) {
            if (visibleRows.count) {
              root.selectedIndex = (root.selectedIndex + (event.key === Qt.Key_Up ? -1 : 1) + visibleRows.count) % visibleRows.count
              results.positionViewAtIndex(root.selectedIndex, ListView.Contain)
            }
            event.accepted = true
          } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.activate(root.selectedIndex)
            event.accepted = true
          } else if (event.text && event.text.length === 1 && event.text.charCodeAt(0) >= 32) {
            root.filterText += event.text
            root.selectedIndex = 0
            root.rebuild()
            event.accepted = true
          }
        }
      }

      Column {
        anchors.fill: parent
        anchors.topMargin: card.contentTopInset
        anchors.rightMargin: card.contentRightInset
        anchors.bottomMargin: card.contentBottomInset
        anchors.leftMargin: card.contentLeftInset
        spacing: Style.spacing.md

        Text {
          width: parent.width
          text: root.filterText || "Search windows and tmux rooms…"
          color: root.foreground
          opacity: root.filterText ? 1 : 0.6
          font.family: root.fontFamily
          font.pixelSize: Style.font.heading
          elide: Text.ElideRight
        }

        Rectangle { width: parent.width; height: 1; color: Color.menu.border }

        ListView {
          id: results
          width: parent.width
          height: parent.height - Style.font.heading - Style.spacing.md * 2 - 1
          model: visibleRows
          clip: true
          spacing: Style.space(3)
          boundsBehavior: Flickable.StopAtBounds

          delegate: Rectangle {
            required property int index
            required property string rowName
            required property string rowDetail
            required property string rowKind
            width: results.width
            height: Math.max(Style.space(56), Style.font.body + Style.font.caption + Style.spacing.md * 2)
            radius: Style.cornerRadius
            color: index === root.selectedIndex ? root.selectedBackground : "transparent"

            Row {
              anchors.fill: parent
              anchors.margins: Style.spacing.md
              spacing: Style.spacing.md
              Text {
                width: Style.space(28)
                anchors.verticalCenter: parent.verticalCenter
                text: rowKind === "room" ? "󰆍" : "󰍹"
                font.family: root.fontFamily
                font.pixelSize: Style.font.heading
                color: index === root.selectedIndex ? root.selectedText : root.foreground
              }
              Column {
                width: parent.width - Style.space(28) - Style.spacing.md
                anchors.verticalCenter: parent.verticalCenter
                Text {
                  width: parent.width
                  text: rowName
                  textFormat: Text.PlainText
                  elide: Text.ElideRight
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  color: index === root.selectedIndex ? root.selectedText : root.foreground
                }
                Text {
                  width: parent.width
                  text: rowDetail
                  textFormat: Text.PlainText
                  elide: Text.ElideRight
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  opacity: 0.7
                  color: index === root.selectedIndex ? root.selectedText : root.foreground
                }
              }
            }
            MouseArea {
              anchors.fill: parent
              hoverEnabled: true
              onEntered: root.selectedIndex = index
              onClicked: root.activate(index)
            }
          }
        }

        Text {
          visible: !root.loading && visibleRows.count === 0
          anchors.horizontalCenter: parent.horizontalCenter
          text: root.filterText ? "No matches" : "No open windows or tmux sessions"
          color: root.foreground
          opacity: 0.6
          font.family: root.fontFamily
        }
      }
    }
  }
}
