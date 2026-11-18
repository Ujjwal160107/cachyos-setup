pragma Singleton
pragma ComponentBehavior: Bound

import qs.modules.common
import qs.modules.common.functions
import QtQuick
import Quickshell
import Quickshell.Io

/**
 * Hands the Liquid Glass settings (on/off, Clear / Tinted, edge highlights,
 * click glow, rim light) and the light or dark mode to the compositor's glass plugin: right away
 * through hyprctl, and for every later Hyprland start or config reload through
 * a small Lua file that hypr/hyprland/liquidglass.lua reads.
 */
Singleton {
    id: root

    readonly property var settings: Config.options.appearance.liquidGlass
    readonly property bool enabled: settings.enable
    readonly property real tinted: settings.mode === "tinted" ? Math.max(0, Math.min(1, settings.tintAmount)) : 0
    readonly property real edgeHighlight: Math.max(0, settings.edgeHighlight)
    readonly property real lens: Math.max(0, settings.refraction)
    readonly property int pressGlow: ({ "off": 0, "subtle": 1, "bright": 2 })[settings.pressGlow] ?? 1
    readonly property real pressSpill: settings.glowSpread ? 0.5 : 0
    readonly property int highlightDirection: ({ "none": 0, "top": 1, "diagonal": 2 })[settings.highlights] ?? 1
    readonly property real darkEdge: settings.darkEdge ? 1 : 0
    readonly property real nearReflection: settings.nearReflection ? 0.5 : 0
    // The glass follows the colour scheme: smoked in dark mode, milky in light
    readonly property string theme: Appearance.m3colors.darkmode ? "dark" : "light"
    readonly property string statePath: FileUtils.trimFileProtocol(`${Directories.state}/user/generated/liquidglass.lua`)

    // Called once at startup (shell.qml), which also brings the singleton up.
    function load() {
        applyTimer.restart();
    }

    onEnabledChanged: applyTimer.restart()
    onTintedChanged: applyTimer.restart()
    onEdgeHighlightChanged: applyTimer.restart()
    onLensChanged: applyTimer.restart()
    onPressGlowChanged: applyTimer.restart()
    onPressSpillChanged: applyTimer.restart()
    onHighlightDirectionChanged: applyTimer.restart()
    onDarkEdgeChanged: applyTimer.restart()
    onNearReflectionChanged: applyTimer.restart()
    onThemeChanged: applyTimer.restart()

    Timer { // a slider drag sends one update, not dozens
        id: applyTimer
        interval: 120
        onTriggered: root.apply()
    }

    function apply() {
        const on = root.enabled ? "true" : "false";
        // press_glow, press_spill, highlight_direction, dark_edge and near_reflection need the
        // Hyprland 0.57 build of hyprglass; the 0.56 build (8d1c06d) rejects them.
        const fields = `enabled = ${on}, layers = { enabled = ${on} }, tinted = ${root.tinted.toFixed(3)}, edge_highlight = ${root.edgeHighlight.toFixed(3)}, lens = ${root.lens.toFixed(3)}, default_theme = "${root.theme}"`;
        stateFile.setText(`-- written by the shell (Settings > Liquid glass); read by hypr/hyprland/liquidglass.lua\nreturn { ${fields} }\n`);
        Quickshell.execDetached(["hyprctl", "eval", `if hl.plugin.hyprglass then hl.plugin.hyprglass.config({ ${fields} }) end`]);
    }

    FileView {
        id: stateFile
        path: root.statePath
        printErrors: false // it does not exist until the first apply()
    }
}
