"""Constants for LedFx HA Bridge."""

DOMAIN = "ledfx_bridge"
NAME = "LedFx HA Bridge"
VERSION = "0.1.0"
CONF_WEB_PORT = "web_port"
CONF_MAX_FPS = "max_fps"
CONF_MAX_INFLIGHT = "max_inflight"
CONF_THRESHOLD = "threshold"
CONF_START_ENABLED = "start_enabled"
DEFAULT_PORT = 4048
DEFAULT_WEB_PORT = 8888
DEFAULT_OPTIONS = {
    CONF_MAX_FPS: 20,
    CONF_MAX_INFLIGHT: 4,
    CONF_THRESHOLD: 1,
    CONF_START_ENABLED: True,
}
COLOR_MODES = {"rgb", "rgbw", "rgbww", "hs", "xy"}
