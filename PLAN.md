# PLAN.md — Multi-Cloud Content Moderation

A FastAPI app that sends one image to Azure AI Content Safety, AWS Rekognition,
and GCP Vision API, then shows each cloud's moderation verdict side-by-side with
an overall SAFE/FLAGGED decision in a simple web UI.

Goal: demonstrate "integrating and configuring basic AI services" across all
three clouds for the AI Engineer application, with a real product use case
(user-generated-content moderation).

## Progress checkpoint

Last updated: session 6 (LLM model fix + retry)

| Step | Status |
|------|--------|
| Session 5: LLM layer → OpenRouter | done |
| Session 6: default model → openai/gpt-oss-20b:free (gemma 4 31b was retired/throttled) | done |
| Session 6: retry-with-backoff for 429 rate limits in llm.py | done |
| Verify | done — 15/15 tests pass; live /moderate/explain returns real LLM summary |

## Session 6 notes

- `meta-llama/llama-3.3-70b-instruct:free` was retired by OpenRouter (404).
  Tested the live free-model list; `google/gemma-4-31b-it:free` existed but was
  persistently 429 rate-limited. `openai/gpt-oss-20b:free` responds, so it's
  now the default (`.env`, config.py, .env.example, README).
- Free OpenRouter models are intermittently rate-limited (shared provider pool,
  `retry_after` ~30s). Added a 3-attempt retry (10s sleep) for 429s in
  `summarize_verdict()`; confirmed the live endpoint succeeded through a
  transient 429.
- README notes: free models get retired/throttled; fallback is
  `openai/gpt-4o-mini` (paid, fractions of a cent).

## Session 3 notes

- **GCP wasn't appearing** because `.env` had a Windows path
  (`C:\Users\jesel\Downloads\...`) on this Linux machine — config checks
  `os.path.isfile()` and marked GCP unconfigured, so `/moderate/all` dropped it.
  Fix for user: transfer the key JSON to this machine and set a Linux path.
- Added `app/image_utils.py`: `prepare_image()` resizes to max 1024px, converts
  to RGB, re-encodes JPEG (quality ladder down to 40) to stay under 3.5MB —
  Azure's real limit is 4MB, AWS 5MB, GCP 10MB.
- `/moderate/all` now always iterates all three providers, so unconfigured ones
  show a clear error panel instead of silently disappearing.
- `aggregate()` returns verdict `ERROR` if every provider failed, instead of a
  misleading `SAFE`.

## Session 2 notes

- Old label-recognition code (azure-ai-vision-imageanalysis, `/analyze/*`) was
  replaced outright per user decision.
- Azure switched from Computer Vision to **AI Content Safety** (separate
  resource, F0 free tier, 5K images/mo). New env vars:
  `AZURE_CONTENT_SAFETY_KEY` / `AZURE_CONTENT_SAFETY_ENDPOINT`.
- Normalized moderation schema: `{flagged, categories: [{category, label,
  confidence 0–1, flagged}]}`. Flag thresholds: Azure severity ≥ 2, AWS
  confidence ≥ 50, GCP likelihood ≥ POSSIBLE.
- `/moderate/all` adds `summary: {verdict: SAFE|FLAGGED, flagging_providers}`.

## How to resume next session

1. Read `PLAN.md` (this file) to see where things stopped.
2. Credentials live in `.env` (gitignored). If `.env` is missing, copy
   `.env.example`.
3. Run with: `uvicorn app.main:app --reload`
4. Update this table at the end of each session.

## API

- `GET /` — web UI
- `POST /moderate/{provider}` — moderate with one cloud (azure | aws | gcp)
- `POST /moderate/all` — run all three, plus overall SAFE/FLAGGED verdict

## TODO next session

1. Test the full flow end-to-end in the browser: upload a real image → all three
   provider panels + verdict + LLM Summary card.
2. If the free model gets throttled again, either wait and retry (the endpoint
   now auto-retries 429s) or set OPENROUTER_MODEL=openai/gpt-4o-mini.
3. If desired: latency tracking, cost-per-call, cross-provider agreement score,
   or Docker container.

## Interview talking points

- Normalized schema over three very different moderation APIs.
- Threshold policy design (severity/likelihood/confidence → binary flag).
- Real use case: UGC image moderation + human-in-the-loop for borderline cases.
- Cloud fundamentals: account setup, IAM/service-account scoping, API keys,
  region selection.