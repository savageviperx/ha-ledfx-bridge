# Validation

Initial implementation tested on Linux in two real Home Assistant environments:

| Python | Home Assistant | pytest-homeassistant-custom-component | Result |
| --- | --- | --- | --- |
| 3.13.16 | 2025.6.3 | 0.13.254 | 25 tests passed |
| 3.14.8 | 2026.10.4 | 0.13.375 | 25 tests passed |

`ruff check .`, `ruff format --check .` and the 25-test pytest suite pass.
The GitHub test workflow repeats both environments using pinned requirements.

Tests exercise Home Assistant's actual config flow, options flow, reconfigure
flow, entity registration, restored switch state, action registry, setup retry
and unload machinery. They use local UDP sockets and simulated light actions.
Two independent channels each start 21–25 actions over a 1.2-second stream with
160 ms simulated action durations, at least 49 ms between starts, and no more
than four active actions per channel. Saturation keeps only the latest frame.

Additional coverage: DDP malformed/timestamped frames, source filtering,
duplicate ports/entities, unavailable and non-RGB targets, unavailable-target
recovery, pause/resume without stale replay, black/off conversion, color
threshold, error backoff, frame expiry, private diagnostics and UDP release.

No test has been performed against the user's live Home Assistant instance,
router or Tuya bulb. A passing test confirms software scheduling, not the
physical bulb refresh rate or cloud transport capacity. HACS/hassfest workflows
are included for independent repository validation on GitHub.
