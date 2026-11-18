import QtQuick
import QtQuick.Layouts
import qs.services
import qs.modules.common
import qs.modules.common.widgets
import qs.modules.common.functions

ContentSection {
    icon: "water_drop"
    title: Translation.tr("Liquid glass")

    ConfigSwitch {
        buttonIcon: "blur_on"
        text: Translation.tr("Liquid glass")
        checked: Config.options.appearance.liquidGlass.enable
        onCheckedChanged: {
            Config.options.appearance.liquidGlass.enable = checked;
        }
        StyledToolTip {
            text: Translation.tr("Glass windows, bar, dock and panels, drawn by the compositor")
        }
    }

    ContentSubsection {
        visible: Config.options.appearance.liquidGlass.enable
        title: Translation.tr("Look")

        ConfigSelectionArray {
            currentValue: Config.options.appearance.liquidGlass.mode
            onSelected: newValue => {
                Config.options.appearance.liquidGlass.mode = newValue;
            }
            options: [
                {
                    displayName: Translation.tr("Clear"),
                    icon: "lens_blur",
                    value: "clear"
                },
                {
                    displayName: Translation.tr("Tinted"),
                    icon: "contrast",
                    value: "tinted"
                }
            ]
        }
    }

    ConfigSlider {
        visible: Config.options.appearance.liquidGlass.enable && Config.options.appearance.liquidGlass.mode === "tinted"
        text: Translation.tr("Tint")
        buttonIcon: "opacity"
        from: 0.1
        to: 1
        value: Config.options.appearance.liquidGlass.tintAmount
        onValueChanged: {
            Config.options.appearance.liquidGlass.tintAmount = value;
        }
    }

    ConfigSlider {
        visible: Config.options.appearance.liquidGlass.enable
        text: Translation.tr("Edge highlights")
        buttonIcon: "highlight"
        from: 0
        to: 2
        stopIndicatorValues: [1]
        value: Config.options.appearance.liquidGlass.edgeHighlight
        onValueChanged: {
            Config.options.appearance.liquidGlass.edgeHighlight = value;
        }
    }

    ConfigSlider {
        visible: Config.options.appearance.liquidGlass.enable
        text: Translation.tr("Refraction")
        buttonIcon: "lens"
        from: 0
        to: 2
        stopIndicatorValues: [1]
        value: Config.options.appearance.liquidGlass.refraction
        onValueChanged: {
            Config.options.appearance.liquidGlass.refraction = value;
        }
    }

    ContentSubsection {
        visible: Config.options.appearance.liquidGlass.enable
        title: Translation.tr("Click glow")
        tooltip: Translation.tr("Light where glass is clicked or touched. Subtle is Apple's current look, Bright its first one")

        ConfigSelectionArray {
            currentValue: Config.options.appearance.liquidGlass.pressGlow
            onSelected: newValue => {
                Config.options.appearance.liquidGlass.pressGlow = newValue;
            }
            options: [
                {
                    displayName: Translation.tr("Off"),
                    icon: "block",
                    value: "off"
                },
                {
                    displayName: Translation.tr("Subtle"),
                    icon: "touch_app",
                    value: "subtle"
                },
                {
                    displayName: Translation.tr("Bright"),
                    icon: "flare",
                    value: "bright"
                }
            ]
        }
    }

    ContentSubsection {
        visible: Config.options.appearance.liquidGlass.enable
        title: Translation.tr("Highlights")
        tooltip: Translation.tr("Where the rim of the glass catches light")

        ConfigSelectionArray {
            currentValue: Config.options.appearance.liquidGlass.highlights
            onSelected: newValue => {
                Config.options.appearance.liquidGlass.highlights = newValue;
            }
            options: [
                {
                    displayName: Translation.tr("All round"),
                    icon: "crop_square",
                    value: "none"
                },
                {
                    displayName: Translation.tr("Top"),
                    icon: "border_top",
                    value: "top"
                },
                {
                    displayName: Translation.tr("Diagonal"),
                    icon: "north_west",
                    value: "diagonal"
                }
            ]
        }
    }

    ConfigRow {
        visible: Config.options.appearance.liquidGlass.enable
        uniform: true
        ConfigSwitch {
            enabled: Config.options.appearance.liquidGlass.pressGlow !== "off"
            buttonIcon: "blur_circular"
            text: Translation.tr("Glow spreads")
            checked: Config.options.appearance.liquidGlass.glowSpread
            onCheckedChanged: {
                Config.options.appearance.liquidGlass.glowSpread = checked;
            }
            StyledToolTip {
                text: Translation.tr("The click glow also lights nearby glass: other windows, the bar, the dock")
            }
        }
        ConfigSwitch {
            buttonIcon: "line_style"
            text: Translation.tr("Dark edge")
            checked: Config.options.appearance.liquidGlass.darkEdge
            onCheckedChanged: {
                Config.options.appearance.liquidGlass.darkEdge = checked;
            }
            StyledToolTip {
                text: Translation.tr("A thin dark line inside the rim, so glass stands out over bright content")
            }
        }
        ConfigSwitch {
            buttonIcon: "palette"
            text: Translation.tr("Nearby colour")
            checked: Config.options.appearance.liquidGlass.nearReflection
            onCheckedChanged: {
                Config.options.appearance.liquidGlass.nearReflection = checked;
            }
            StyledToolTip {
                text: Translation.tr("Rims pick up the colour of what is near them, not only of what is behind")
            }
        }
    }

    ConfigRow {
        visible: Config.options.appearance.liquidGlass.enable
        uniform: true
        ConfigSwitch {
            buttonIcon: "toolbar"
            text: Translation.tr("Capsule bar")
            checked: Config.options.appearance.liquidGlass.capsuleBar
            onCheckedChanged: {
                Config.options.appearance.liquidGlass.capsuleBar = checked;
            }
            StyledToolTip {
                text: Translation.tr("Each bar group is its own glass capsule. Off: one glass bar with a single border")
            }
        }
        ConfigSwitch {
            buttonIcon: "view_agenda"
            text: Translation.tr("Modular sidebar")
            checked: Config.options.appearance.liquidGlass.modularSidebar
            onCheckedChanged: {
                Config.options.appearance.liquidGlass.modularSidebar = checked;
            }
            StyledToolTip {
                text: Translation.tr("Each card of the right sidebar is its own glass, like Control Center")
            }
        }
    }

    ContentSubsection {
        id: accentPicker
        title: Translation.tr("Accent colour")
        tooltip: Translation.tr("The active workspace and the bar's glyph. None: the theme's own colours")
        readonly property string current: Config.options.appearance.liquidGlass.accentColor
        readonly property var swatches: [
            { name: Translation.tr("Nothing red"), color: "#D71921" },
            { name: Translation.tr("Orange"), color: "#FF6A13" },
            { name: Translation.tr("Yellow"), color: "#F5C400" },
            { name: Translation.tr("Green"), color: "#2DBE6C" },
            { name: Translation.tr("Teal"), color: "#13B5B1" },
            { name: Translation.tr("Blue"), color: "#2F7CF6" },
            { name: Translation.tr("Purple"), color: "#9B5CF6" },
            { name: Translation.tr("Pink"), color: "#F0508C" },
            { name: Translation.tr("White"), color: "#F2F2F2" }
        ]

        RowLayout {
            spacing: 8
            Repeater {
                model: accentPicker.swatches
                delegate: RippleButton {
                    id: swatch
                    required property var modelData
                    implicitWidth: 32
                    implicitHeight: 32
                    buttonRadius: 16
                    readonly property bool chosen: accentPicker.current.toLowerCase() === modelData.color.toLowerCase()
                    colBackground: modelData.color
                    colBackgroundHover: modelData.color
                    colRipple: ColorUtils.mix(modelData.color, "#ffffff", 0.7)
                    onClicked: Config.options.appearance.liquidGlass.accentColor = modelData.color
                    contentItem: MaterialSymbol {
                        anchors.centerIn: parent
                        horizontalAlignment: Text.AlignHCenter
                        text: swatch.chosen ? "check" : ""
                        iconSize: 18
                        color: ColorUtils.mix(swatch.modelData.color, "#000000", 0.75)
                    }
                    StyledToolTip {
                        text: swatch.modelData.name
                    }
                }
            }
            RippleButton {
                id: noAccent
                implicitHeight: 32
                buttonRadius: 16
                toggled: accentPicker.current === ""
                colBackground: Appearance.colors.colLayer2
                onClicked: Config.options.appearance.liquidGlass.accentColor = ""
                contentItem: StyledText {
                    horizontalAlignment: Text.AlignHCenter
                    leftPadding: 10
                    rightPadding: 10
                    text: Translation.tr("None")
                    color: noAccent.toggled ? Appearance.colors.colOnPrimary : Appearance.colors.colOnLayer2
                }
            }
        }

        MaterialTextField {
            Layout.fillWidth: true
            placeholderText: Translation.tr("Custom colour, e.g. #D71921")
            text: accentPicker.current
            onEditingFinished: {
                const t = text.trim();
                if (t === "")
                    Config.options.appearance.liquidGlass.accentColor = "";
                else if (/^#?[0-9a-fA-F]{6}$/.test(t))
                    Config.options.appearance.liquidGlass.accentColor = t.startsWith("#") ? t.toUpperCase() : "#" + t.toUpperCase();
            }
        }
    }
}
