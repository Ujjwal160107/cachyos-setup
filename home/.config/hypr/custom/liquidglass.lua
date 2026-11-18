-- Nothing Liquid glass, adapted from shlok-shinde/dots-hyprland c1c73060.
-- Build the pinned plugin against the installed Hyprland before enabling it.
-- Running the 0.56 build (hyprglass 8d1c06d): the 0.57-only press glow / rim options are left out.
local plugin = HOME .. "/.local/lib/nothing-liquid/hyprglass.so"
if is_file_exists(plugin) then
    hl.plugin.load(plugin)
end

local function shellSettings()
    local path = (os.getenv("XDG_STATE_HOME") or (HOME .. "/.local/state"))
        .. "/quickshell/user/generated/liquidglass.lua"
    if not is_file_exists(path) then return {} end
    local ok, settings = pcall(dofile, path)
    return (ok and type(settings) == "table") and settings or {}
end

if hl.plugin.hyprglass then
    local hg = hl.plugin.hyprglass
    local shell = shellSettings()
    hg.config({
        default_theme = shell.default_theme or "dark",
        default_preset = "tahoe_window", -- windows; layers set their own preset below
        enabled = shell.enabled ~= false,
        layers = { enabled = shell.enabled ~= false },
        tinted = shell.tinted or 0,
        edge_highlight = shell.edge_highlight or 1,
        lens = shell.lens or 1,
    })
    -- The bar spans the screen's top edge, so the rim only shows along its bottom border, as a
    -- thin white line under the bar on every workspace. Same glass, no rim.
    hg.preset("tahoe_clear_norim", { inherits = "tahoe_clear", bevel_strength = 0 })
    -- The dock's rim reads as a blurred white outline, so it goes rimless too.
    for _, ns in ipairs({ "quickshell:bar", "quickshell:verticalBar", "quickshell:dock" }) do
        hg.layer(ns, { mask_threshold = 0.04, preset = "tahoe_clear_norim" })
    end
    hg.layer("quickshell:session", { mask_threshold = 0.04, preset = "tahoe_clear" })
    for _, ns in ipairs({
        "quickshell:overview", "quickshell:cheatsheet", "quickshell:wallpaperSelector",
        "quickshell:sidebarLeft", "quickshell:sidebarRight",
        "quickshell:notificationPopup", "quickshell:onScreenDisplay",
        "quickshell:mediaControls", "quickshell:osk", "quickshell:popup", "quickshell:trayMenu",
    }) do
        hg.layer(ns, { mask_threshold = 0.04, preset = "tahoe" })
    end
end

-- Do not refract or blur the wallpaper as a full-screen glass panel.
hl.layer_rule({ match = { namespace = "quickshell:background" }, blur = false })
hl.config({
    decoration = {
        shadow = {
            enabled = true,
            range = 46,
            offset = { 0, 14 },
            render_power = 3,
            color = "rgba(00000073)",
            color_inactive = "rgba(00000040)",
        },
    },
})
