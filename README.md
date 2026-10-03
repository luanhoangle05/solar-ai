# Solar Farm AI Control System

Multi-agent hackathon project for weather-aware, cost-aware solar panel optimization.

Team:
- Luan
- Duy
- Tung

Development:
- Python
- Visual Studio Code
- Git / GitHub

## Current phase: architecture and shared contracts (awaiting approval)

This repository contains a Python 3.11 scaffold, typed shared interfaces,
explicitly MOCK development fixtures, and contract validation tests. Agents,
models, pipeline, service, and dashboard are not implemented. No real weather
requests, model training, hardware control, or performance claims are included.

Read [the architecture and ownership guide](docs/architecture.md) before
changing shared fields. Read [mock provenance](data/mock/README.md) before
using any fixture. Contract proposal version: `0.1.0`.

From the repository root in PowerShell, run the tests without activating the
virtual environment or changing your execution policy:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

No third-party packages are needed for this phase. To deliberately regenerate
the four mock files from their documented synthetic source values:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_mock_fixtures
```

### Independent development after approval

| Owner | Contract to start from | Implementation boundary |
| --- | --- | --- |
| Luan | `WeatherRow`, `WeatherTools`, `EnergyPredictor` | Pipeline, Data Agent, Linear Regression, Random Forest |
| Duy | `data/mock/sample_weather.csv` | Advanced models, model comparison, costs, optimization, Modeling/Optimization/Manager agents, recommendation backend |
| Tung | `data/mock/sample_full_frontend_data.json` | Dashboard and all frontend views |

Approve contracts first, then commit/push them to `main`. All three feature
branches must start from that same approved commit. No feature branches are
created during this phase. The local folder is `solar-farm-ai`; the GitHub
repository is named `solar-ai`.
