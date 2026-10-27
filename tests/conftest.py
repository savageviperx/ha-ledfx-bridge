"""Fixtures for the real Home Assistant test harness."""

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations, socket_enabled):
    """Local UDP is intentional; no live bulbs or external networks are used."""
