import QtQuick
import qs.modules.common

// Nothing Liquid's shell-side glass for panes drawn on the wallpaper layer.
LiquidGlassEffect {
    id: root
    readonly property bool light: !Appearance.m3colors.darkmode
    readonly property var settings: Config.options.appearance.liquidGlass
    property real radius: Appearance.rounding.verylarge

    brightness: root.light ? 1.03 : 0.8
    adaptiveDim: root.light ? 0 : 0.8
    adaptiveBoost: root.light ? 0.85 : 0
    tint: root.light ? Qt.rgba(0.98, 0.98, 0.99, 0.45) : Qt.rgba(0.04, 0.04, 0.05, 0.25)
    shadow: root.light ? 0.2 : 0.28
    refraction: 18 * root.settings.refraction
    bodyLens: 0.03 * root.settings.refraction
    rim: 0.75 * root.settings.edgeHighlight
    frost: root.settings.mode === "tinted" ? 0.8 + root.settings.tintAmount : 0.8
    highlightDirection: ({ "none": 0, "top": 1, "diagonal": 2 })[root.settings.highlights] ?? 1
    darkEdge: root.settings.darkEdge ? (root.light ? 0.43 : 0.88) : 0
    nearReflection: root.settings.nearReflection ? 0.5 : 0

    Rectangle {
        anchors.fill: parent
        radius: root.radius
        color: "white"
    }
}
