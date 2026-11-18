hl.bind("CTRL+SUPER+ALT+Slash", hl.dsp.exec_cmd("xdg-open ~/.config/hypr/custom/keybinds.lua"), {description = "Edit user keybinds"} )

-- Default Super+D toggles maximize; replaced with Discord
hl.unbind("SUPER + D")
hl.bind("SUPER + D", hl.dsp.exec_cmd("discord"), { description = "App: Discord" })
hl.bind("SUPER + Z", hl.dsp.exec_cmd("zen-browser"), { description = "App: Zen browser" })

-- Default Print copies the full screen; replaced with a Snip & Sketch style flow:
-- freeze the screen, pick a region, annotate in satty (Enter copies, Ctrl+S saves)
hl.unbind("Print")
hl.bind("Print", hl.dsp.exec_cmd("pidof slurp || hyprshot --freeze --mode region --raw --silent | satty --filename -"),
    { description = "Utilities: Snip & annotate (satty)" })
