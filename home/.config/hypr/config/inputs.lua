-- Input configuration

hl.config({
    input = {
        -- sensitivity = -0.25,
        accel_profile = "flat",

        -- Mouse wheel: traditional scrolling (natural DISABLED).
        natural_scroll = false,

        touchpad = {
            -- Trackpad: natural scrolling DISABLED (traditional).
            -- Slide fingers UP -> content moves DOWN (page scrolls toward the top).
            natural_scroll = false,
        },
    },
    -- Uncomment the section below to enable software cursors; this can help with cursor display or behavior issues
    -- cursor = {
    --     no_hardware_cursors = 1,
    -- },
})

-- Per-device scroll direction for the built-in trackpad (FTCS0038 / 2808:0106).
-- Bound by device name because the generic input:touchpad block did not take effect.
-- natural_scroll = true  -> Windows/macOS default: content follows your fingers.
-- Flip BOTH lines to false for traditional (wheel-style) scrolling.
hl.device({ name = "ftcs0038:00-2808:0106-touchpad", natural_scroll = true })
hl.device({ name = "ftcs0038:00-2808:0106-mouse",    natural_scroll = true })

hl.gesture({ fingers = 4, direction = "horizontal", action = "workspace" })
hl.gesture({ fingers = 3, direction = "down",       action = "close" })
hl.gesture({ fingers = 3, direction = "up",         action = "fullscreen" })
hl.gesture({ fingers = 3, direction = "left",       action = "float" })
