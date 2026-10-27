# Changelog

## 0.1.1

- Include the app's icon as a local Home Assistant brand image, including logo and dark-theme fallbacks.
- Enable HACS brand-asset validation. Local icons require Home Assistant 2026.3 or newer; bridge compatibility remains 2025.6+.
- After updating in HACS, restart Home Assistant and refresh the frontend to load the icon.

## 0.1.0

- Native Home Assistant custom integration, installable as a HACS custom repository.
- One DDP port per existing color light, with multiple independent mappings.
- Default 20 outgoing action starts/s and four concurrent actions; latest frame only.
- Native setup, reconfiguration and performance options; no HA token.
- Restored sync switch, stream/status sensors and optional timing diagnostics.
- English fallback and Italian translations.
- Debug-level frame logging, private diagnostics, UDP cleanup and action-error backoff.
