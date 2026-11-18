import QtQuick
import qs.modules.common

Rectangle {
    id: root
    required property var widget
    property bool shadowed: Config.options.background.widgets.shadow
    property bool glass: true

    radius: Appearance.rounding?.verylarge ?? 30
    color: glass && Appearance.liquidGlass ? "transparent" : Appearance.colors.colPrimaryContainer

    StyledRectangularShadow {
        target: root
        z: -2
        visible: root.shadowed && !Appearance.liquidGlass
    }

    Loader {
        anchors.fill: parent
        active: root.glass && Appearance.liquidGlass
        sourceComponent: WallpaperGlass {
            backdrop: root.widget.wallpaperItem
            radius: root.radius
            mapPosition: Qt.point(root.widget.x + root.x - root.widget.wallpaperItem.x,
                root.widget.y + root.y - root.widget.wallpaperItem.y)
            mapScale: root.widget.scale
        }
    }
}
