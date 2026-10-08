# Assignment verification — October 7, 2026

- Fresh Python 3.11 environment installed with only `fastapi uvicorn httpx pytest`.
- `python -m pytest -q`: 149 passed. One upstream Starlette TestClient deprecation
  warning; no additional dependency was installed.
- `node --check frontend/app.js`: passed.
- `git diff --check`: passed.
- Full API flows covered in rehearsal and the genuine live-provider code path
  with `httpx.MockTransport`: intake, strict DNA, one victim persona, refusal,
  bounded training, scoring, persistence and cached replay.
- Frozen complete live-model demo: seven provider responses during priming,
  zero additional provider calls during replay in the transport-controlled test.
- gstack `/browse`: desktop DNA panel, practice conversation, report and
  injection refusal exercised through the actual local server.
- Mobile layout at 390×844: document width equals viewport width, no horizontal
  overflow. Both screens visually inspected; no console errors in clean reloads.
- Legacy sample DNA/report files migrated to the canonical context contracts;
  generated OpenAPI and schema examples checked against runtime models.
- Live Featherless account credentials and Shitaj's 100-message labeled CSV were
  unavailable. No real provider call, independently measured accuracy or
  scientifically validated immunity probability is claimed.

Run the app with `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`.
Default rehearsal is explicit and interactive. See README for live configuration
and `python -m backend.demo --prime` / `--replay` before demo freeze.
