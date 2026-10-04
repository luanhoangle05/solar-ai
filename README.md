# Solar Farm AI Control System

A multi-agent system that decides, hour by hour, whether a row of solar panels
should rotate to a new tilt angle. It weighs the predicted energy gain against
the cost of moving, and a deterministic safety agent has the final word.

Team: Luan (data pipeline), Duy (models, optimization, agents, backend), Tung (frontend).

> **This is a prototype simulation.** No hardware is controlled. Energy labels
> are physics-simulated, not measured production, and the movement and safety
> coefficients are assumptions, not calibrated values. Details are in
> [What is real and what is simulated](#what-is-real-and-what-is-simulated).

## How it works

```text
Data Agent -> Modeling Agent -> Optimization Agent -> Manager / Safety Agent -> dashboard
```

| Agent | What it does | Tools it coordinates |
| --- | --- | --- |
| Data | Fetches the hour's weather, validates it, adds sun position | Open-Meteo client, validation, pvlib solar position |
| Modeling | Compares the models, picks the one with the lowest validation RMSE, predicts energy at each candidate angle | XGBoost, LSTM |
| Optimization | Computes movement cost and net benefit for every candidate angle, including staying put | Cost simulation, optimizer |
| Manager / Safety | Runs the safety checks and decides ROTATE, HOLD or STOW | Wind, angle-limit, data-freshness, panel-status and model checks |

The orchestrator is a plain state machine, not an LLM. If a stage fails, the
failure is recorded and the run still goes to the Manager, which holds or stows.

**Where the LLM is used.** After an agent's tools have run, the agent asks an
LLM to explain its recorded tool results in two or three sentences. The LLM
never calculates and never decides: its text is accepted only if every number
in it was produced by a tool, and it is stored in the run log. Without an API
key, or if the call fails, agents fall back to templated text and the decision
is identical.

**Decision rule**, applied in this order:

1. A severe safety violation (for example wind over the limit): STOW.
2. Stale or unreliable data, or any other failed check: HOLD.
3. Best net benefit at or below the threshold: HOLD.
4. Otherwise: ROTATE to the recommended angle.

Net benefit = predicted energy gain - movement cost, in kWh-equivalent for one
20-panel row over one hour.

## Results

Trained on 2023, validated on 2024, tested on 2025 (chronological, no shuffling).
Figures are from [data/evaluation/system_evaluation.json](data/evaluation/system_evaluation.json).

| Model | Validation RMSE (kWh) | Test RMSE (kWh) | Picks the best angle (test hours) |
| --- | --- | --- | --- |
| LSTM (PyTorch) | 0.0093 | 0.0101 | 96.4% |
| Boosting (XGBoost) | 0.0358 | 0.0321 | 75.6% |
| Linear regression | not available | not available | not available |
| Random forest | not available | not available | not available |

The two baseline models are not implemented yet, so they are reported as
unavailable rather than estimated.

Replaying the agents over every hour of 2025 for one row, against a row fixed at 35 degrees:

| | |
| --- | --- |
| Energy, fixed row | 14,327 kWh |
| Energy, agent-controlled row | 14,977 kWh |
| Movement cost | 8.7 kWh-equivalent |
| Net benefit | +641.5 kWh-equivalent (about 4.5%) |
| Decisions | 177 ROTATE, 8,542 HOLD, 24 STOW |
| Unsafe rotations | 0 |

This replay scores the selected model's choices with that model's own
predictions, so the gain is optimistic. It is not evidence of real-world savings.

## Run it

Requires Python 3.11 and Node.js. Commands are for PowerShell from the repository root.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

**One agent run**, written to `data/evaluation/latest_recommendation.json`:

```powershell
# A recorded daytime hour from the dataset (about 4 minutes; drop --skip-lstm to include the LSTM)
.\.venv\Scripts\python.exe -m scripts.run_recommendation --skip-lstm

# The current hour's live forecast for the demo site
.\.venv\Scripts\python.exe -m scripts.run_recommendation --live
```

Useful options: `--angle 60` sets the row's current angle, `--no-llm` turns off
the LLM explanations, `--output` chooses the file.

For LLM explanations, put an Anthropic API key in a `.env` file at the
repository root (the file is git-ignored):

```text
ANTHROPIC_API_KEY=sk-ant-...
```

**The dashboard:**

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. By default it shows the mock fixture. To show a
generated run, create `frontend/.env.local` with a path relative to the
repository root:

```text
SOLAR_FRONTEND_DATA=data/evaluation/latest_recommendation.json
```

The full dataset is not committed; see [docs/full-dataset.md](docs/full-dataset.md).
Without it, the committed seasonal sample is used.

## What is real and what is simulated

| Part | Status |
| --- | --- |
| Weather in the dataset | Real archived forecast weather (Open-Meteo) |
| Energy labels | Physics-simulated with pvlib for a reference row, not measured |
| Model metrics | Computed on held-out data; they measure agreement with that simulation |
| Movement cost and safety limits | Prototype assumptions in `src/common/config.py` |
| Live weather run | Real fetch. The provider gives no forecast issue time, so freshness cannot be established and the Manager always holds |
| Recorded-hour run | A past dataset hour replayed as the forecast, reported as DEGRADED |
| Farm snapshot in a generated run | Simulated: every row shown READY at the control row's angle |
| Control commands | Simulation only; nothing is sent to hardware |
| Row-to-row shading | Not modeled; rows are optimized independently |
| 3D sun, clouds, sun-tracking demo and Sun lab in the dashboard | Illustrative only; they do not come from the model |

## Known gaps

- The Data Agent in `src/agents/data_agent.py` is still a scaffold. Runs use an
  interim live agent in `src/service/live_data_agent.py` built on the pipeline tools.
- Linear regression and random forest are not implemented.
- The LSTM is not used in a live run because it needs look-back weather history.
- There is no decision history yet; the dashboard's history list is empty for generated runs.

## Repository guide

| Path | Contents |
| --- | --- |
| `src/pipeline/` | Weather client, validation, solar position, storage |
| `src/models/` | XGBoost and LSTM models, evaluation, cost simulation, optimizer |
| `src/agents/` | The agents, orchestrator, trace recording and LLM reasoning |
| `src/service/` | Recommendation service and the interim live Data Agent |
| `src/common/` | Shared contracts, schema and configuration |
| `frontend/` | Next.js dashboard |
| `scripts/` | Run, evaluation, tuning and data-building commands |
| `docs/architecture.md` | Architecture, ownership and contract rules |
