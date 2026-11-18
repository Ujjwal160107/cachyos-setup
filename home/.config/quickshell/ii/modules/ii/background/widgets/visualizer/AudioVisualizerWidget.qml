import QtQuick
import qs
import qs.services
import qs.modules.common
import qs.modules.common.functions
import qs.modules.common.widgets
import qs.modules.common.widgets.widgetCanvas
import qs.modules.ii.background.widgets
import Quickshell.Io

// Minimal, transparent, circular now-playing audio visualizer for the
// homescreen. Built entirely from pieces already in this shell: SineCookie
// (the same wobbly-circle primitive the cookie clock uses) driven by the
// same cava pipeline backing the media controls and lock screen widgets.
// No bespoke shape/canvas drawing.
AbstractBackgroundWidget {
    id: root

    configEntryName: "visualizer"
    visibleWhenLocked: false

    implicitWidth: 180
    implicitHeight: 180

    property list<real> visualizerPoints: []
    readonly property real audioLevel: {
        if (root.visualizerPoints.length === 0)
            return 0;
        let sum = 0;
        for (let i = 0; i < root.visualizerPoints.length; ++i)
            sum += root.visualizerPoints[i];
        return sum / root.visualizerPoints.length;
    }
    property real smoothedLevel: 0
    onAudioLevelChanged: root.smoothedLevel = root.audioLevel
    Behavior on smoothedLevel {
        NumberAnimation {
            duration: 220
            easing.type: Easing.OutCubic
        }
    }

    Process {
        id: cavaProc
        running: MprisController.isPlaying && root.visible
        onRunningChanged: {
            if (!cavaProc.running)
                root.visualizerPoints = [];
        }
        command: ["cava", "-p", `${FileUtils.trimFileProtocol(Directories.scriptPath)}/cava/raw_output_config.txt`]
        stdout: SplitParser {
            onRead: data => {
                root.visualizerPoints = data.split(";").map(p => parseFloat(p.trim())).filter(p => !isNaN(p));
            }
        }
    }

    SineCookie {
        anchors.centerIn: parent
        implicitSize: 140
        sides: 8
        amplitude: 3 + Math.min(1, root.smoothedLevel / 700) * 16
        color: ColorUtils.transparentize(Appearance.colors.colPrimary, 0.35)
    }
}
