-- Transparency: re-enable blur for terminal + file manager
-- (hyprland/rules.lua disables blur globally with a class=".*" wildcard)
-- kitty's own background_opacity handles its transparency (keeps text crisp);
-- this just lets the compositor blur what's behind the punched-through background.
hl.window_rule({match = {class = "^(kitty)$" }, no_blur = false})

-- Dolphin's transparency comes from Kvantum (translucent_windows in MaterialAdw.kvconfig)
hl.window_rule({match = {class = "^(org.kde.dolphin)$" }, no_blur = false})
