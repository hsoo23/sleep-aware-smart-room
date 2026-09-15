# Continuous Integration

GitHub Actions runs `.github/workflows/ci.yml` on every pull request, on pushes to
`main`, and on manual dispatch.

## What CI checks

| Job | Command | Scope |
|---|---|---|
| Ruff | `ruff check src tests` | Lint rules `E`, `F`, `W`, `I`, `B`, `UP` (pinned in `pyproject.toml`) |
| pytest (3.10–3.13) | `python -m compileall -q src tests` then `python -m pytest -v` | Unit and mock-integration tests |

CI validates Python 3.10, 3.11, 3.12, and 3.13. The package metadata keeps
`requires-python = ">=3.10"` without an upper bound; newer versions are expected
to work but are not validated until added to the matrix.
The runner installs only `pip install -e '.[dev]'`; OpenCV, MediaPipe, PyAutoGUI,
Flask, and RPi.GPIO are **not** installed. `tests/test_hardware_free_imports.py`
fails if importing the core package pulls in any of those modules.

Run the same checks locally:

```bash
python -m pip install -e '.[dev]'
ruff check src tests
python -m compileall -q src tests
python -m pytest -v
```

## CI is not hardware validation

A green CI run only shows that the hardware-independent decision logic, data
contracts, and fake-adapter pipeline behave as specified. It does **not** verify
the camera, MediaPipe Face Mesh accuracy, Raspberry Pi GPIO, relay, buzzer,
Chrome/YouTube media control, network latency, or email reports. Hardware
behavior must still be demonstrated with [BASELINE_RUNBOOK.md](BASELINE_RUNBOOK.md)
and recorded with the Git commit used.

## Test naming

Test files and functions name the module and the behavior they verify, so a
failing job identifies the broken contract without opening the code:

| File | Module | Behavior |
|---|---|---|
| `test_detection_ear_edge_cases.py` | `detection.ear` | EAR geometry and invalid landmark input |
| `test_detection_temporal_state.py` | `detection.state` | Time-based `EYES_CLOSED` / `DROWSY` / recovery transitions |
| `test_control_policy_transitions.py` | `control.policy` | Idempotent, intention-specific action transitions |
| `test_pipeline_closed_loop_integration.py` | `pipeline.runner` | Detect → actuate → re-observe → restore with fake adapters |
| `test_config_settings.py` | `config` | Defaults, environment overrides, invalid values, `.env.example` coverage |
| `test_hardware_free_imports.py` | package | Core imports without hardware-only dependencies |

New modules should add tests in the same PR using `test_<module>_<behavior>` names.

## Lint policy for `legacy/`

`legacy/` preserves the originally submitted prototype verbatim as the behavioral
reference. It is excluded from Ruff (`extend-exclude` with `force-exclude`), is
never auto-fixed or reformatted, and is not imported by tests. Behavior migrated
out of `legacy/` must be linted and tested in `src/` instead.

`ruff format` is not enforced yet so that open module PRs do not receive
formatting-only conflicts; it can be enabled once those PRs are merged.
