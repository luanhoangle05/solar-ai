# MOCK DEVELOPMENT DATA — not measured or trained-model output

Every CSV row, energy label, model prediction, agent log, safety outcome,
historical decision and farm state in this directory is synthetic. Weather
values are hand-authored, realistic-looking examples; they have not been
fetched from a provider. `actual_kwh` in the CSV is a **mock label**, not a
measurement and not the output of a physics model. Do not use these six rows
to claim model accuracy or energy improvements.

The CSV keeps exactly the 13 required columns, starting with `timestamp`.
This README supplies its provenance without adding comment lines or changing
the agreed header. Do not copy the CSV elsewhere without this provenance.
Future measured/physics-derived datasets must declare their own provenance;
never relabel these fixtures as measured data.

All JSON files include `metadata.dataset_kind = "MOCK"` and
`metadata.label_source = "mock"`. The interval starts at the timezone-aware
`timestamp` and lasts 60 minutes. Energy applies to one 20-panel row,
`row-001`, not to one panel or the entire farm. Angles are tilt from horizontal.
The mock dates are fixed for reproducibility. `forecast_age_minutes` is the
age **at the fixture run**, not the elapsed time since the fixture date today.

| File | Consumer / purpose |
| --- | --- |
| `sample_weather.csv` | Duy's stable input contract: six hourly mock rows; `actual_kwh` is the target |
| `sample_model_output.json` | Four synthetic model comparisons, selected model, seven candidate angles, and the evaluation vectors backing the illustrative metrics |
| `sample_full_frontend_data.json` | Tung's standalone dashboard fixture, including every row/zone, activity logs, history and errors |
| `agent_state.json` | Example completed shared state; every recorded agent/tool event is illustrative |

MAE, RMSE and R2 are computed from the `evaluation_fixture` vectors in
`sample_model_output.json`. They are **mock-vector metrics**, not evidence
that Linear Regression, Random Forest, boosting or LSTM has been trained.
The stable model key `boosting` uses the example implementation label
`xgboost`; Duy can use LightGBM without renaming the shared key.

The proposed candidate is 45 degrees: baseline 5.8 kWh, predicted 6.09 kWh,
gain 0.29 kWh, movement cost 0.03 kWh-equivalent, net benefit
0.26 kWh-equivalent. The 60-degree candidate produces 6.11 kWh but its larger
movement cost makes its net benefit lower. These are fixture arithmetic,
not a system-level performance evaluation. The script does not run agents
or an optimizer; the 45-degree example is an explicit fixture choice.

The farm view contains 1000 panels in 50 whole rows of 20. Zones have
13/12/13/12 rows (260/240/260/240 panels). Row angles describe the observed
snapshot; `decision.target_angle_deg` describes a proposed action. A ROTATE
recommendation does not claim a motor has moved. Other rows' illustrated
HOLD/STOW states do not inherit row-001's weather recommendation.

`python -m scripts.build_mock_fixtures` regenerates these four fixtures from
the repository root. This deliberately overwrites only those mock files.
