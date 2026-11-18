import QtQuick
import Qt5Compat.GraphicalEffects

/**
 * Liquid glass drawn by the shell itself, for surfaces the compositor's glass
 * plugin can't reach (the lock screen). The glass takes the shape of whatever
 * is placed inside it (its alpha: a rounded rectangle, the clock's digits...)
 * and refracts `backdrop`, an item behind it that the caller draws. Optics in
 * ../shaders/liquidglass.frag, the same as the plugin's.
 */
Item {
    id: root
    required property Item backdrop
    default property alias shapeData: shape.data // opaque wherever the glass is

    property real bezel: 14
    property real refraction: 18
    property real bodyLens: 0.03
    property real frost: 0.8
    property real rim: 0.75
    property real brightness: 0.8
    property real adaptiveDim: 0.8   // dark mode: bright backdrops pulled down
    property real adaptiveBoost: 0   // light mode: dark backdrops lifted (milky)
    property color tint: Qt.rgba(0.04, 0.04, 0.05, 0.25)
    property real dispersion: 0.35
    property real shadow: 0.28
    // The rim's light: 0 all round, 1 along the top, 2 from the top left; the
    // dark line inside it (0.88 suits dark mode, 0.43 light); how much it takes
    // the colour of what is just outside it. Plain values: the login screen
    // uses this file without the shell's Config.
    property int highlightDirection: 1
    property real darkEdge: 0.88
    property real nearReflection: 0.5
    // Track both axes separately so diagonal movement cannot cancel an update.
    property point mapPosition: Qt.point(0, 0)
    property real mapScale: 1

    readonly property real pad: Math.ceil(Math.max(root.bezel * 2 + 4, root.refraction + 8))

    Item { // The shape, in a box padded for the rim, the refraction and the shadow
        id: shapeBox
        x: -root.pad
        y: -root.pad
        width: root.width + root.pad * 2
        height: root.height + root.pad * 2
        visible: false

        Item {
            id: shape
            x: root.pad
            y: root.pad
            width: root.width
            height: root.height
        }
    }

    ShaderEffectSource {
        id: maskTexture
        sourceItem: shapeBox
        hideSource: true
        visible: false
    }

    GaussianBlur { // The glass's height: its shape, blurred over the bezel
        id: fieldBlur
        x: shapeBox.x
        y: shapeBox.y
        width: shapeBox.width
        height: shapeBox.height
        source: maskTexture
        radius: root.bezel
        samples: Math.min(Math.ceil(root.bezel) * 2 + 1, 41)
        visible: false
    }

    ShaderEffectSource {
        id: fieldTexture
        sourceItem: fieldBlur
        hideSource: true
        visible: false
    }

    ShaderEffectSource { // What is behind, exactly where the box sits over it
        id: behindTexture
        sourceItem: root.backdrop
        visible: false
        sourceRect: {
            root.mapPosition;
            root.mapScale;
            root.x;
            root.y;
            return root.mapToItem(root.backdrop, -root.pad, -root.pad, root.width + root.pad * 2, root.height + root.pad * 2);
        }
    }

    ShaderEffect {
        x: shapeBox.x
        y: shapeBox.y
        width: shapeBox.width
        height: shapeBox.height

        property var mask: maskTexture
        property var field: fieldTexture
        property var behind: behindTexture
        property size itemSize: Qt.size(width, height)
        property real bezel: root.bezel
        property real refraction: root.refraction
        property real bodyLens: root.bodyLens
        property real frost: root.frost
        property real rim: root.rim
        property real brightness: root.brightness
        property real adaptiveDim: root.adaptiveDim
        property real adaptiveBoost: root.adaptiveBoost
        property vector4d tint: Qt.vector4d(root.tint.r, root.tint.g, root.tint.b, root.tint.a)
        property real dispersion: root.dispersion
        property real shadow: root.shadow
        property real highlightDirection: root.highlightDirection
        property real darkEdge: root.darkEdge
        property real nearReflection: root.nearReflection

        fragmentShader: Qt.resolvedUrl("../shaders/liquidglass.frag.qsb")
    }
}
