# LedFx HA Bridge

Make existing Home Assistant color lights react to LedFx audio effects. This custom integration receives a **single RGB pixel over DDP** and forwards its color and intensity to a selected `light` entity inside Home Assistant.

LedFx still runs on your computer and captures the music there. The bridge runs in Home Assistant, starts with it. It works alongside `hass-ledfx`; that integration is not required.

[Italiano](README.it.md) · [Changelog](CHANGELOG.md)

## Installation with HACS

Requires Home Assistant **2025.6 or newer**, HACS, LedFx with DDP output, and a color-capable light already working in HA.

1. In HACS, open **⋮ → Custom repositories**.
2. Add `https://github.com/savageviperx/ha-ledfx-bridge`, category **Integration**.
3. Download **LedFx HA Bridge**, then restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → LedFx HA Bridge**.
5. Select your existing color light, a name and a UDP port. Defaults are **4048** for the first light and the next unused port for additional lights.

[Open repository in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=savageviperx&repository=ha-ledfx-bridge&category=integration)

This is a HACS **custom repository**. Publication on GitHub does not automatically add it to HACS's default catalog.

### Manual installation

Copy `custom_components/ledfx_bridge` into your HA configuration directory under `custom_components/`, restart HA, then add the integration as above. Remove it through **Devices & services** first when uninstalling; afterwards remove its files or uninstall through HACS.

## LedFx output

Create a DDP device in LedFx for each configured light:

| LedFx setting | Value |
| --- | --- |
| Device type | DDP |
| IP address | **Home Assistant's LAN IP**, not the bulb's or PC's IP |
| Port | The mapping's UDP port, starting at **4048** |
| Pixel count | **1** |
| Destination ID | **1** |
| Refresh rate | 30 FPS or higher |
| Preview only | Off |

Assign an audio-reactive effect to the LedFx output/virtual and select the correct audio input. On Windows this is often the system playback device's WASAPI loopback.

The optional **LedFx PC IPv4 address** restricts packets to that source IP and adds an **Open device web interface** link. **LedFx web interface port** defaults to **8888**; it is not the DDP port. Leave the PC IP empty to accept frames from any reachable IPv4 sender on your LAN.

For more lights, add another integration entry and another LedFx DDP device with a different UDP port, such as 4049. One HA light entity can only be mapped once. A light group is one mapping, but its integration may fan actions out to several physical bulbs.

### Network access

The PC must be able to reach HA on the configured **UDP** port. Different Wi-Fi names are fine if the router routes traffic between the networks and client/guest isolation allows it. Port 8123 is HA's web/API port; the bridge does not receive colors there. UDP 4048 is unrelated to LedFx's TCP web port 8888.

With HA Container, use host networking or explicitly publish every chosen UDP port, for example `4048:4048/udp`. The integration cannot change Docker or router settings. DDP is an unauthenticated LAN protocol; keep it on trusted networks. The optional source IP filter is a convenience, not authentication.

## Controls and settings

Each mapping creates a virtual device with:

- **Music synchronization** switch: pause/resume forwarding. It restores its last state after restart. Already started actions may still complete when paused.
- **Receiving LedFx** binary sensor: on if a valid frame arrived within the last five seconds, even when forwarding is paused.
- **Status** sensor: disabled, waiting, streaming, pausing after an error, or target light unavailable.
- **Outgoing update rate** and **Light action latency** diagnostic sensors: disabled by default; enable them from the entity list if needed.

Use **Configure** on the integration entry to change the send rate, concurrent actions and color threshold. Use its **⋮ → Reconfigure** menu to change the target light, PC IP or ports.

English is the fallback language. Italian translations follow your HA user's language setting.

## Timing and limits

Default behavior matches the desktop bridge:

- Up to **20 light-action starts per second** per mapping (at least 50 ms between starts).
- Up to **4 actions in flight**. A 160 ms response does not serialize every update.
- Only the most recent waiting frame is kept; there is no growing backlog.
- Identical colors are skipped. The default RGB threshold is 1; black turns the light off.
- An action error triggers exponential retry delays from 2 to 60 seconds. Missing/unavailable targets pause forwarding and recover when available again.
- Frames expire after five seconds. Expiry leaves the last light color in place and sends no blackout command.

Configure supports 1–60 starts/s and 1–8 in-flight actions. **20 starts/s is a scheduling ceiling, not a guarantee of 20 physical bulb updates/s.** Tuya cloud transport and other integrations can throttle, serialize or delay commands. Concurrent calls can complete out of order; use concurrency 1 if ordered completion matters more than speed. A service call completing only confirms HA's action returned, not when the bulb physically changed. The target integration controls its own queues and network behavior.

This bridge does not supply LedFx audio capture, effects, or direct Tuya protocol support. Use the light's existing integration. Avoid a second automation or desktop bridge controlling the same light simultaneously.

## Debugging

Normal operation does not log every color. In **Settings → Devices & services → LedFx HA Bridge → ⋮**, enable **debug logging**, reproduce the issue briefly, then disable it to download the log. Per-frame messages appear only at debug level. HA's integration menu also offers **Download diagnostics**, containing bounded counters/settings without names, IPs, entity IDs or tokens.

If there is no reaction, first inspect **Receiving LedFx**. If off, check the DDP destination, single-pixel settings, source filter, UDP networking and LedFx effect. If on, check the sync switch, status sensor and the target light's own integration. An occupied UDP port causes setup to retry; stop the other receiver or choose another port.

For very long sessions, leave the optional rapidly changing diagnostics disabled or exclude those sensors from Recorder. HA status is refreshed at 1 Hz, independently of the music frame rate.

## Development and validation

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

Tests use Home Assistant's actual custom-integration harness, local UDP and simulated light actions. They cover config flows, options/reconfigure reload, entities, diagnostics, cleanup, overload and ~20 starts/s with simulated 160 ms actions. No live Tuya hardware is required by the tests. See [VALIDATION.md](VALIDATION.md) for the tested runtime and limits.

## Protocol and references

- [LedFx DDP device documentation](https://docs.ledfx.app/en/latest/devices/ddp.html)
- [Home Assistant integration development](https://developers.home-assistant.io/docs/creating_integration_manifest/)
- [HACS custom repositories](https://www.hacs.xyz/docs/faq/custom_repositories/)

MIT licensed. An independent community project; not affiliated with Home Assistant, LedFx, or Tuya.
