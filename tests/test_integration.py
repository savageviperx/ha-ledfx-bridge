"""Real HA config flows, entities, light actions, reload and diagnostics."""

import asyncio
import json
import socket
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER, ConfigEntryState
from homeassistant.core import State, callback
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_restore_cache

from custom_components.ledfx_bridge.const import DOMAIN
from custom_components.ledfx_bridge.diagnostics import async_get_config_entry_diagnostics

from .test_engine import packet


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def data(**updates):
    return {
        "name": "Test music bulb",
        "entity_id": "light.test_bulb",
        "port": free_port(),
        "host": "",
        "web_port": 8888,
    } | updates


@pytest.fixture
def light(hass):
    hass.states.async_set("light.test_bulb", "on", {"supported_color_modes": ["rgb"]})


@pytest.mark.asyncio
async def test_user_flow_and_validation(hass, light):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    bad = data(host="http://192.0.2.10")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], bad)
    assert result["errors"] == {"host": "invalid_ip"}
    with patch("custom_components.ledfx_bridge.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], data())
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_duplicate_port_and_entity(hass, light):
    existing = MockConfigEntry(domain=DOMAIN, data=data(), unique_id="light.test_bulb")
    existing.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], dict(existing.data))
    assert result["errors"] == {"port": "port_in_use", "entity_id": "light_in_use"}


@pytest.mark.parametrize(
    "state,modes,error",
    [
        ("unavailable", ["rgb"], "light_unavailable"),
        ("on", ["color_temp"], "color_unsupported"),
    ],
)
@pytest.mark.asyncio
async def test_unsupported_light(hass, state, modes, error):
    hass.states.async_set("light.test_bulb", state, {"supported_color_modes": modes})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data())
    assert result["errors"] == {"entity_id": error}


@pytest.mark.asyncio
async def test_setup_action_switch_diagnostics_and_unload(hass, light):
    calls = []

    @callback
    def record(call):
        calls.append((call.service, call.data))

    entry = MockConfigEntry(domain=DOMAIN, title="Music bulb", data=data())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    # Override the light actions after its component has registered the real
    # handlers. This exercises our use of HA's actual action registry.
    hass.services.async_register("light", "turn_on", record)
    hass.services.async_register("light", "turn_off", record)
    engine = entry.runtime_data
    engine.receive(packet((80, 40, 0)), "127.0.0.1")
    await asyncio.sleep(0.03)
    assert calls[0] == (
        "turn_on",
        {"entity_id": "light.test_bulb", "rgb_color": [255, 128, 0], "brightness": 80},
    )
    switch = next(s for s in hass.states.async_all("switch"))
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": switch.entity_id}, blocking=True
    )
    engine.receive(packet((100, 0, 0)), "127.0.0.1")
    await asyncio.sleep(0.08)
    assert len(calls) == 1
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    serialized = json.dumps(diagnostics)
    assert "light.test_bulb" not in serialized
    assert "127.0.0.1" not in serialized
    assert diagnostics["statistics"]["sent"] == 1
    port = entry.data["port"]
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not engine.running and not engine._pending
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("0.0.0.0", port))


@pytest.mark.asyncio
async def test_options_and_reconfigure_reload(hass, light):
    entry = MockConfigEntry(domain=DOMAIN, title="Music bulb", data=data())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    original = entry.runtime_data
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "max_fps": 12,
            "max_inflight": 2,
            "threshold": 3,
            "start_enabled": True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert not original.running
    assert entry.runtime_data.settings.max_fps == 12
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    new_data = data(name="Renamed bulb", host="192.0.2.10")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], new_data)
    assert result["type"] is FlowResultType.ABORT
    await hass.async_block_till_done()
    assert entry.title == "Renamed bulb"
    assert entry.runtime_data.settings.port == new_data["port"]
    assert entry.runtime_data.settings.source_ip == "192.0.2.10"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_unavailable_target_recovers_without_reloading(hass, light):
    calls = []
    entry = MockConfigEntry(domain=DOMAIN, title="Music bulb", data=data())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.services.async_register("light", "turn_on", callback(lambda call: calls.append(call)))
    hass.states.async_set("light.test_bulb", "unavailable", {"supported_color_modes": ["rgb"]})
    engine = entry.runtime_data
    engine.receive(packet((20, 30, 0)), "127.0.0.1")
    await asyncio.sleep(0.03)
    assert engine.status == "target_unavailable" and not calls
    hass.states.async_set("light.test_bulb", "on", {"supported_color_modes": ["rgb"]})
    engine.receive(packet((40, 30, 0)), "127.0.0.1")
    await asyncio.sleep(0.03)
    assert len(calls) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_restored_off_switch_prevents_automatic_sends(hass, light):
    mock_restore_cache(hass, [State("switch.music_bulb_music_synchronization", "off")])
    entry = MockConfigEntry(domain=DOMAIN, title="Music bulb", data=data())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert not entry.runtime_data.enabled
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_busy_udp_port_retries_setup(hass, light):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("0.0.0.0", 0))
        entry = MockConfigEntry(
            domain=DOMAIN, title="Music bulb", data=data(port=sock.getsockname()[1])
        )
        entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


def test_hacs_metadata_and_translation_keys():
    root = Path(__file__).parents[1]
    integration = root / "custom_components" / DOMAIN
    manifest = json.loads((integration / "manifest.json").read_text())
    assert manifest["domain"] == DOMAIN
    assert manifest["version"] == "0.1.1"
    english = json.loads((integration / "translations/en.json").read_text())
    italian = json.loads((integration / "translations/it.json").read_text())

    def keys(value):
        if isinstance(value, dict):
            return {k: keys(v) for k, v in value.items()}
        return None

    assert keys(english) == keys(italian)
    assert english == json.loads((integration / "strings.json").read_text())
