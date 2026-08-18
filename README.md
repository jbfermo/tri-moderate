# TriModerate

Multi-cloud content moderation (Azure AI Content Safety · AWS Rekognition · GCP Vision SafeSearch).

A FastAPI app that sends **one image** to Azure AI Content Safety, AWS
Rekognition, and GCP Vision API, then shows each cloud's moderation verdict
side by side with an overall SAFE / FLAGGED decision in a simple web UI.

Built to demonstrate integrating and configuring AI services across all three
major clouds for a real-world use case: user-generated-content moderation.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in your credentials
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000, upload an image, and hit **Moderate**.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Web UI |
| `POST` | `/moderate/azure` | Moderate with Azure only |
| `POST` | `/moderate/aws` | Moderate with AWS only |
| `POST` | `/moderate/gcp` | Moderate with GCP only |
| `POST` | `/moderate/all` | Moderate with every configured cloud + overall verdict |
| `POST` | `/moderate/explain` | Moderate with every cloud **and** get an LLM-written explanation of the verdict |

All moderation endpoints accept a multipart file field named `file`. Each
returns a normalized result:

```json
{
  "flagged": true,
  "categories": [
    {"category": "Violence", "label": "Weapon Violence", "confidence": 0.97, "flagged": true}
  ]
}
```

- `confidence` is normalized to 0–1 (severity/likelihood scaled).
- `/moderate/all` returns a result for **all three** clouds plus a `summary`:
  `{"verdict": "SAFE" | "FLAGGED" | "ERROR", "flagging_providers": [...]}`.
  Unconfigured providers appear with an `error` field so you always see which
  clouds are missing.
- Images are resized/re-encoded server-side to fit provider input limits
  (Azure 4MB, AWS 5MB, GCP 10MB), so large photos work without manual
  downscaling.

The app works with **only some clouds configured** — unconfigured providers
just report an error and don't break the others.

## Cloud setup (all have free tiers)

### Azure — AI Content Safety
1. Create a free Azure account: https://azure.microsoft.com/free/ (includes ~$200 credit).
2. In the portal, create an **AI Content Safety** resource (pricing tier **F0** — free, 5K images/mo).
3. Copy the **Key 1** and **Endpoint** from the resource's *Keys and Endpoint* page.
4. In `.env`:
   ```
   AZURE_CONTENT_SAFETY_ENDPOINT=https://YOUR-NAME.cognitiveservices.azure.com/
   AZURE_CONTENT_SAFETY_KEY=your-key
   ```

### AWS — Rekognition
1. Create a free AWS account: https://aws.amazon.com/free/ (12 months free tier).
2. In IAM, create a user with **AmazonRekognitionReadOnlyAccess** policy
   attached. Generate an **Access Key** for it (programmatic access).
3. In `.env`:
   ```
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   AWS_REGION=us-east-1
   ```

### GCP — Vision API
1. Create a free Google Cloud account: https://cloud.google.com/free/ ($300 credit).
2. Create a project and enable the **Cloud Vision API**.
3. Create a **service account** with the *Vision API User* role and download
   its JSON key file.
4. In `.env`:
   ```
   GCP_SERVICE_ACCOUNT_JSON=/absolute/path/to/service-account-key.json
   ```

### OpenRouter — LLM explanation (optional but recommended)
1. Create a free account at https://openrouter.ai (includes some free credit;
   the default model below costs nothing).
2. Go to **Keys** → **Create key**, copy it.
3. In `.env`:
   ```
   OPENROUTER_API_KEY=sk-or-v1-your-key
   OPENROUTER_MODEL=openai/gpt-oss-20b:free
   ```
   The default model is free ($0). OpenRouter retires free models and rate-limits
   them over time — if the explanation endpoint errors with a 429/404, pick a
   current free model at https://openrouter.ai/models (or switch
   `OPENROUTER_MODEL` to a cheap paid model such as `openai/gpt-4o-mini`,
   fractions of a cent per request).

> Cost note: each request is one image. Azure F0, AWS 12-month tier, GCP's
> 1,000 units/month free allowance, and OpenRouter's free model make the whole
> demo cost effectively $0. Don't share the `.env` or GCP key file; both are
> gitignored.

## Project layout

```
app/
  main.py                  # FastAPI app, routes, verdict aggregation, static UI
  config.py                # loads .env, reports which clouds are configured
  image_utils.py           # resizes/re-encodes images to fit provider limits
  llm.py                   # prompt template + OpenRouter call for explanations
  providers/
    base.py                # Provider abstraction + normalized moderation schema
    azure_provider.py      # Azure AI Content Safety (Hate/SelfHarm/Sexual/Violence)
    aws_provider.py        # AWS Rekognition moderation labels
    gcp_provider.py        # GCP Vision SafeSearch (adult/violence/racy/...)
  static/index.html        # upload UI + side-by-side verdicts
.env.example               # credential template
test_app.py                # smoke tests (TestClient + mocked providers)
```

## How flags are decided (per provider)

| Cloud | Source | Flag threshold |
|-------|--------|----------------|
| Azure | Content Safety severity 0–6 | severity ≥ 2 (Low) |
| AWS | Rekognition label confidence 0–100 | confidence ≥ 50 |
| GCP | SafeSearch likelihood | ≥ POSSIBLE |

The overall verdict is **FLAGGED** if any provider flags the image.


- **Normalized schema**: three very different moderation APIs (severity levels,
  label confidences, likelihood enums) map into one consistent shape.
- **Threshold policy**: explain how each vendor's native scale is translated to
  a binary flag — a real design decision in any moderation pipeline.
- **Input handling**: images are preprocessed (resized, re-encoded) to satisfy
  each provider's size limits — a genuine production concern when integrating
  vendor APIs.
- **Prompt engineering**: a versioned system prompt + templated user prompt
  (temperature 0.2) turn the structured moderation JSON into a human-readable
  verdict explanation — directly demonstrates the "develop and test prompts"
  duty, plus wiring an LLM gateway (OpenRouter) with a model-configurable
  default.
- **Real use case**: UGC image moderation (e.g. a photo-sharing app deciding to
  auto-block an upload), plus discussion of human-in-the-loop review for
  borderline cases.
- Cloud fundamentals: account setup, IAM/service-account scoping, API keys, and
  region selection on all three platforms.
