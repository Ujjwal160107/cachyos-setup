pragma ComponentBehavior: Bound

import QtQuick
import qs
import qs.modules.common
import qs.modules.common.widgets
import qs.modules.common.widgets.widgetCanvas

import qs.modules.ii.background.widgets
import qs.modules.ii.background.widgets.clock
import qs.modules.ii.background.widgets.weather
import qs.modules.ii.background.widgets.media
import qs.modules.ii.background.widgets.resources
import qs.modules.ii.background.widgets.visualizer
import qs.modules.ii.background.widgets.calendar
import qs.modules.ii.background.widgets.worldclock

Item {
    id: root

    required property var screen
    required property var wallpaperItem
    required property bool wallpaperSafetyTriggered

    Repeater {
        model: [
            { key: "visualizer" },
            { key: "calendar" },
            { key: "weather" },
            { key: "clock", alwaysOnLock: true },
            { key: "media" },
            { key: "resources" },
            { key: "worldClock" },
        ]

        delegate: FadeLoader {
            id: loaderDelegate
            required property var modelData

            property bool enableLoading: true

            shown: {
                const entry = Config.options.background.widgets[loaderDelegate.modelData.key];
                if (!entry || !entry.enable)
                    return false;
                return loaderDelegate.enableLoading;
            }

            sourceComponent: {
                switch (loaderDelegate.modelData.key) {
                    case "visualizer":  return visualizerComp
                    case "calendar":    return calendarComp
                    case "weather":     return weatherComp
                    case "clock":       return clockComp
                    case "media":       return mediaComp
                    case "resources":   return resourcesComp
                    case "worldClock":  return worldClockComp
                }
                return null
            }

            onLoaded: {
                if (loaderDelegate.modelData.key === "media" && loaderDelegate.item && loaderDelegate.item.requestReset) {
                    loaderDelegate.item.requestReset.connect(() => {
                        loaderDelegate.enableLoading = false
                        mediaResetTimer.restart()
                    })
                }
            }

            Timer {
                id: mediaResetTimer
                interval: 500
                onTriggered: loaderDelegate.enableLoading = true
            }
        }
    }

    Component {
        id: visualizerComp
        AudioVisualizerWidget {
            screenWidth: root.screen.width
            screenHeight: root.screen.height
            scaledScreenWidth: root.screen.width
            scaledScreenHeight: root.screen.height
            wallpaperScale: 1
            wallpaperItem: root.wallpaperItem
        }
    }
    Component {
        id: calendarComp
        CalendarWidget {
            screenWidth: root.screen.width
            screenHeight: root.screen.height
            scaledScreenWidth: root.screen.width
            scaledScreenHeight: root.screen.height
            wallpaperScale: 1
            wallpaperItem: root.wallpaperItem
        }
    }
    Component {
        id: weatherComp
        WeatherWidget {
            screenWidth: root.screen.width
            screenHeight: root.screen.height
            scaledScreenWidth: root.screen.width
            scaledScreenHeight: root.screen.height
            wallpaperScale: 1
            wallpaperItem: root.wallpaperItem
        }
    }
    Component {
        id: clockComp
        ClockWidget {
            screenWidth: root.screen.width
            screenHeight: root.screen.height
            scaledScreenWidth: root.screen.width
            scaledScreenHeight: root.screen.height
            wallpaperScale: 1
            wallpaperSafetyTriggered: root.wallpaperSafetyTriggered
            wallpaperItem: root.wallpaperItem
        }
    }
    Component {
        id: mediaComp
        MediaWidget {
            screenWidth: root.screen.width
            screenHeight: root.screen.height
            scaledScreenWidth: root.screen.width
            scaledScreenHeight: root.screen.height
            wallpaperScale: 1
            wallpaperItem: root.wallpaperItem
        }
    }
    Component {
        id: resourcesComp
        ResourcesWidget {
            screenWidth: root.screen.width
            screenHeight: root.screen.height
            scaledScreenWidth: root.screen.width
            scaledScreenHeight: root.screen.height
            wallpaperScale: 1
            wallpaperItem: root.wallpaperItem
        }
    }
    Component {
        id: worldClockComp
        WorldClockWidget {
            screenWidth: root.screen.width
            screenHeight: root.screen.height
            scaledScreenWidth: root.screen.width
            scaledScreenHeight: root.screen.height
            wallpaperScale: 1
            wallpaperItem: root.wallpaperItem
        }
    }
}
