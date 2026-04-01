# LoanFlow — SET challenge

Robot Framework + Python test suite for the LoanFlow Application API.

Click here for
[Part 1 — Test Analysis & Strategy](https://github.com/elenakuzne/loanflow-test/blob/4dc7d4f4a1333bf46ed69333b2694e4529cad038/Part%201%20%E2%80%94%20Test%20Analysis%20%26%20Strategy.pdf)

## Structure

```
tests/
  application_outcomes.robot   # data-driven: all decision paths (approve/reject/pending/error)
  application_api.robot        # structural tests: validation, idempotency, resilience, retrieval
resources/
  api.resource                 # shared HTTP keywords and setup
  variables.py                 # spec constraints and thresholds (min/max amounts, duplicate window)
libraries/
  LoanFlowLibrary.py           # Python keywords: manages both mock servers, builds payloads, checks notifications
src/
  loanflow_mock/
    app.py                     # Application API mock — validates input, calls Risk Engine, stores applications
    state.py                   # in-memory storage and notification log
  risk_engine_mock/
    app.py                     # Risk Engine mock — scores by income-to-loan ratio, configurable delay
.github/workflows/
  robot-tests.yml              # CI pipeline
```

## How the mocks work

```
Robot tests → HTTP → Application API mock
                           ↓ HTTP POST /score
                      Risk Engine mock
```

The Application API mock makes a real HTTP call to the Risk Engine mock — the same way the real services communicate. This means timeout and unavailability are tested as genuine network conditions, not code flags.

The Risk Engine mock scores applications based on income-to-loan ratio:

| Ratio | Score | Outcome |
| --- | --- | --- |
| ≥ 4.0 | 82 | approved |
| ≥ 2.0 | 55 | pending |
| < 2.0 | 18 | rejected |

To simulate a timeout, tests call `Configure Risk Engine Delay    6` (6 s exceeds the 5 s timeout).
To simulate unavailability, tests call `Stop Risk Engine` — the Application API gets a connection error and returns `503`.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
python -m robot -d results tests
```

Reports are written to `results\`: `log.html`, `report.html`, `output.xml`.

## Key assumptions

The artifacts had a few gaps. My choices:

- Risk Engine `timeout` → application created with `status: error`
- Risk Engine `unavailable` → `503` returned, no application created
- Duplicate submission within 60 s → returns existing record with `200`
