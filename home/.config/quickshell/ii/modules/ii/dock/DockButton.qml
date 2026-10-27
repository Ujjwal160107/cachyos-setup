import qs.modules.common
import qs.modules.common.widgets
import QtQuick
import QtQuick.Layouts

RippleButton {
    Layout.fillHeight: true
    Layout.topMargin: Appearance.sizes.elevationMargin - Appearance.sizes.hyprlandGapsOut
    implicitWidth: implicitHeight - topInset - bottomInset
    buttonRadius: Appearance.rounding.normal

    // Track the dock row's height (dock.height + elevationMargin) rather than a fixed
    // size, so buttons stay centred in the pill at any dock.height instead of
    // overflowing it and pushing the icons and their indicator dots out the bottom.
    background.implicitHeight: (Config.options?.dock.height ?? 70) + Appearance.sizes.elevationMargin - topInset - bottomInset
}
