# InoculAI

InoculAI is a synthetic-only, defensive cybersecurity workspace for detecting
scams and prompt injection, understanding scam campaigns, and training people
to resist social-engineering tactics.

## About

The application runs through one FastAPI server and provides:

- **SENTINEL**, a conservative scam and prompt-injection classifier.
- Scam DNA extraction, tactic chains, inert indicators of compromise, and
  campaign grouping.
- A bounded fictional victim conversation for safe inbound-message rehearsal.
- **TRAIN ME**, an opt-in simulator that teaches independent verification and
  produces an immunity report based only on observed tactics.
- Scripted rehearsal mode for offline demos and live Featherless mode with
  strict JSON validation, caching, review states, and safety guards.

InoculAI never contacts real scammers, sends messages, opens links, performs
transactions, or handles real credentials. All demos and conversations are
fictional and synthetic.

## Built With

- Python 3.11+
- FastAPI and Uvicorn
- Pydantic contracts
- SQLite for local persistence and model-result caching
- HTTPX for Featherless API calls
- Pytest for automated tests
- Plain HTML, CSS, and JavaScript for the local frontend

## Getting Started

Create an environment, install dependencies, run the tests, and start the
server:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. The API documentation is available at
<http://127.0.0.1:8000/docs>.

The default mode is `rehearsal`; it needs no credentials and makes no model
calls. To use live Featherless inference, stop the server, configure the
following variables, and start it again:

```powershell
$env:INOCULAI_MODE = 'live'
$env:FEATHERLESS_BASE_URL = 'https://api.featherless.ai/v1'
$env:FEATHERLESS_MODEL = 'YOUR_FEATHERLESS_MODEL_ID'
$env:FEATHERLESS_API_KEY = 'YOUR_FEATHERLESS_API_KEY'
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Set `SENTINEL_CACHE_ONLY=1` to prevent uncached model calls. Use
`INOCULAI_DATA_PATH` and `SENTINEL_CACHE_PATH` to select alternate local data
and classifier-cache files.

To run the small scanner demo:

```powershell
python sentinel.py --prime-demo
python sentinel.py --demo
python eval_harness.py docs/fixtures/eval_smoke.csv --cache-only
```

## License

No license has been declared for this repository yet. Until a license file is
added, the project should be treated as all rights reserved.
