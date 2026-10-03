# CLAUDE.md — solar-ai · Duy's scope (modeling, optimization, agents, backend)

## Project

Solar Farm AI Control System: weather-aware, cost-aware panel angle control for one
20-panel row per decision (farm: 1000 panels, 50 rows, 4 zones of 13/12/13/12 rows).
Team: **Luan** (data pipeline + baseline models), **Duy** (me), **Tung** (frontend).
Windows / PowerShell, VS Code, Python 3.11. Deadline: GitHub link + demo video by
**Sun Oct 4, 12:00 PM**.

Flow: Data Agent → Modeling Agent → Optimization Agent → Manager/Safety Agent →
recommendation backend → frontend. The orchestrator is a state machine, not an LLM agent.
Models and calculators are **tools**; agents coordinate tools. Never one agent per panel.

**Source of truth — read before any change:** `docs/architecture.md`, `data/mock/README.md`,
`src/common/schema.py`, `src/common/tool_contracts.py`, `src/common/agent_contracts.py`,
`src/common/config.py`, `tests/test_contracts.py`. If this file and those disagree, those win.

## Planning gate — before writing any code

At the start of a new task, do a **read-only analysis first**: no file edits, no installs,
no training, no external API calls, no commits. Then report:
1. my role, 2. input contract, 3. output contract, 4. modules I'll touch,
5. team boundaries, 6. execution flow (simple diagram), 7. dependencies and how mocks unblock me.
For every technology not already fixed by the repo, give 2–3 options with pros/cons, one
recommendation, and whether it adds a dependency. **Wait for my approval before implementing.**

## My ownership — only edit these

- `src/models/advanced/` — `boosting.py` (XGBoost; key stays `boosting`), `lstm.py`
- `src/models/evaluation.py`, `src/models/cost_simulation.py`, `src/models/optimizer.py`
- `src/agents/modeling_agent.py`, `src/agents/optimization_agent.py`, `src/agents/manager_agent.py`
- `src/service/recommendation_service.py`
- Example-data generator: `scripts/generate_example_data.py` → `data/example/` (new, additive)
- Tests: `tests/models/`, `tests/agents/`, and my part of `tests/integration/`

**Do not edit:** `src/pipeline/`, `src/models/baseline/`, `src/agents/data_agent.py` (Luan);
`src/frontend/` and the web app (Tung); `src/common/`, `data/mock/`, `scripts/build_mock_fixtures.py`
(shared). I may **read** their public interfaces. If a shared contract is insufficient:
STOP and report the exact problem, the proposed field, and who is affected.
Branch: `feature/duy-modeling-agents`, from the approved `main` commit. Never merge to `main`.

## Contracts

**Input (Luan → Duy):** rows matching `WeatherRow` / `WEATHER_COLUMNS` (13 columns:
`timestamp, temperature_c, cloud_cover_pct, precipitation_mm, wind_speed_kmh, wind_gust_kmh,
ghi_wm2, dni_wm2, dhi_wm2, sun_elevation_deg, sun_azimuth_deg, panel_angle_deg, actual_kwh`).
`actual_kwh` = energy for one 20-panel row over one hour; it is the **label only**, never an
inference feature. Inference uses `WeatherFeatures`.

**Output (Duy → Tung):** a `FrontendData` object that passes `validate_frontend_data`, shaped like
`data/mock/sample_full_frontend_data.json`. Shared state: my agents return only their own
sections (`modeling`, `optimization`, `safety`, `decision`) plus traces. Never overwrite Luan's
`data` / `weather`. Never ask Tung to change his UI to fit my output.

Frontend stack (Tung's, for reference only): Next.js + React + TypeScript + Tailwind +
shadcn/ui + Recharts + Zod (+ React Three Fiber later). Tung's Zod schema mirrors
`schema.py`, so **any field drift in my output breaks his app**.

## Example data (develop on this, swap for real data later)

The 6-row mock CSV is too small to train on. Generate a larger synthetic **example** dataset:
- Exact `WEATHER_COLUMNS` header; every row passes `validate_weather_row`.
- Fixed random seed, reproducible; hourly timestamps (UTC, timezone-aware) over months.
- **Vary `panel_angle_deg` across rows** so models can learn how angle changes energy;
  otherwise candidate-angle predictions are meaningless.
- Physically plausible: energy rises with irradiance on the tilted panel, falls with cloud,
  zero at night, small temperature loss, plus noise. Document the formula in `data/example/README.md`.
- Label it honestly: outputs built on it use `dataset_kind = "MOCK"` and `label_source = "mock"`
  (the current contract has no "example" value; adding one is a contract change — propose, don't edit).
- Everything that reads data goes through one loader, so switching to Luan's real output is a
  path/config change, not a code change.

## Hard rules

- **No invented numbers or results.** Metrics, savings and decisions are computed, never hardcoded.
  Unavailable results are `null` / `UNAVAILABLE`, never zero. No confidence score invented from R².
- **Model selection is a rule, not an LLM:** lowest validation RMSE among available models,
  ties → documented order. Record the reason.
- **Time-aware evaluation:** chronological train/validation/test; no random splits; no fitting
  transforms on future data; same target, units and test windows for all four models.
  LSTM sequences never reach past the prediction cutoff.
- **Optimize net benefit, not raw kWh.** Include the stay (current) angle as a candidate with zero
  movement cost. Ties → least movement, then lowest angle. All coefficients come from
  `SimulationConfig` (labeled PROTOTYPE SIMULATION ASSUMPTIONS); none hardcoded in functions.
- **Units:** kWh-equivalent per row per hour. No dollar figures until the team agrees a conversion.
- **Safety is deterministic and first:** severe violation → STOW; stale/unreliable data or failed
  check → HOLD; net benefit ≤ threshold → HOLD; else ROTATE. No LLM can override a failed check.
  `send_control_command` is simulation-only.
- **The LLM never calculates.** If an LLM is used, it only explains or summarizes tool results.
- **No new dependencies without team approval**; once approved, add them to `requirements.txt`.
- Unimplemented paths raise `NotImplementedError`; never fake success.

## Commands (PowerShell, repo root)

```powershell
py -3.11 -m venv .venv                                         # once; .venv is git-ignored
.\.venv\Scripts\python.exe -m unittest discover -s tests -v    # all tests (unittest, not pytest)
```
Run the full suite before every commit. Commit after every working step.

## Implementation order (vertical path first; don't block on LSTM)

1. Example-data generator + single data loader
2. XGBoost model + evaluation (MAE, RMSE, R²)
3. Candidate-angle prediction → cost simulation → optimizer
4. Optimization Agent → Modeling Agent
5. Safety tools → Manager Agent
6. Recommendation backend producing valid `FrontendData`
7. LSTM (or a documented limitation if data doesn't support it)
8. Four-model comparison (Luan's models via the shared `EnergyPredictor` interface)
9. System evaluation: baseline vs optimized energy, gain, movement cost, net benefit,
   ROTATE/HOLD/STOW counts, unnecessary moves avoided, safety violations
10. Integration test against mock contracts

## Tests I own (fast, no teammate code required)

Boosting smoke · LSTM sequence building (no leakage) · LSTM smoke · metric math · model
selection · candidate generation (includes stay angle) · kWh per angle · movement cost ·
net benefit · optimizer picks max net benefit · HOLD when gain ≤ threshold · STOW on severe
violation · HOLD on stale data · Modeling/Optimization/Manager agent tool coordination ·
`FrontendData` validates · shared agent state validates.

## Decisions awaiting the team (raise at the planning gate)

- LSTM framework: PyTorch vs Keras/TensorFlow vs a small scikit-learn fallback.
- ML dependencies shared with Luan (numpy, pandas, scikit-learn, xgboost) and exact versions.
- How Tung receives my output: written JSON file vs a FastAPI endpoint.
- Where the LLM reasons (if at all) and which provider; judges expect visible agent reasoning.
- Example-data physics: simple stdlib formula vs pvlib (new dependency).
- Row-to-row shading is not modeled yet; rows are optimized independently.

## Final report when my scope is done

Files inspected / created / modified; models implemented; comparison and selection behavior;
each agent's behavior; cost model and assumptions; optimization algorithm; evaluation metrics;
final Duy → Tung output; tests added and results; blockers; integration instructions.
