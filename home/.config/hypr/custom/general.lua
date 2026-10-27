-- Shake the mouse to locate it, like macOS.
-- Provided by the dynamic-cursors hyprpm plugin (VirtCode/hypr-dynamic-cursors).
--
-- The plugin is loaded here, at config-parse time, rather than by `hyprpm reload` from
-- execs.lua: its config keys only exist once it is loaded, so loading it later means every
-- key below is rejected as unknown and Hyprland shows a config-error banner on boot.
-- The keys use underscores (dynamic_cursors), not the hyphen from the plugin's real name.
-- A hardware cursor lives on a fixed-size plane in the GPU's scanout path. A magnified
-- cursor overflows it, and the compositor falls back to an unscaled default image — which
-- looks like the cursor changing back to the old theme mid-shake. Software cursors are
-- composited like any other surface, so they scale to whatever size the plugin asks for.
hl.config({
    cursor = {
        no_hardware_cursors = true
    }
})

local dynamic_cursors_so = "/var/cache/hyprpm/ujjwal/dynamic-cursors/dynamic-cursors.so"

-- pcall, not a bare call: hyprpm plugins stop loading whenever Hyprland's ABI changes on
-- update. If that happens, silently lose shake-to-locate rather than fail the whole config
-- parse at login on keys the unloaded plugin never registered.
if is_file_exists(dynamic_cursors_so) and pcall(hl.plugin.load, dynamic_cursors_so) then
    hl.config({
        plugin = {
            dynamic_cursors = {
                enabled = true,

                -- The plugin's headline feature is tilting/rotating/stretching the cursor
                -- as it moves. macOS does not do that, so it stays off; shake-to-locate is
                -- the only part wanted here.
                mode = "none",

                shake = {
                    enabled = true,

                    -- How much shaking it takes to trigger.
                    threshold = 6,

                    -- Size while magnified: starts at `base`, grows by how hard you shake.
                    -- `limit` caps it — without it (the default 0 means no cap) the cursor
                    -- grows without bound for as long as you keep shaking, which macOS
                    -- never does.
                    base = 4,
                    speed = 4,
                    limit = 5,
                    influence = 0,

                    -- Shrink back this long (ms) after shaking stops.
                    timeout = 1000,

                    -- Don't apply the tilt/rotate effects while magnified either.
                    effects = false,
                    ipc = false
                }
            }
        }
    })
end
