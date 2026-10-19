# Redstring

**Connect the dots on every claim.**

Redstring is an AI copilot for motor-insurance claim adjusters. Drop in a claim pack (claim form, repair invoice, photos, police report) and five Gemini-powered agents read every document, check it against the policy wording, look for inconsistencies, and link the claim to every other claim that shares a phone number, bank account, garage, invoice or even an identical photo. The adjuster gets a risk score, evidence for every flag, the exact policy clauses involved, and a recommended next step, in under a minute.

> Rules check claims one at a time. Fraud works in networks.

**Live demo:** https://redstring-511910.web.app (click *Enter demo as adjuster*)

**Benchmark** (motor claims, held-out set of 32 synthetic claims, [details](docs/benchmark.md)): 95% precision, 100% recall, 1 of 14 clean claims falsely flagged, ~18 s median triage, ≈$0.036 (₹3.0) of Gemini per claim.

---

## What it does

| Agent | What it does | How |
|---|---|---|
| **Reader** | Extracts claimant, vehicle, incident, invoice line items and photo observations from PDFs and images | Gemini multimodal, structured JSON output, documents passed straight from Cloud Storage |
| **Policy** | Checks cover, exclusions, deductible and missing documents; cites clause numbers verbatim | Deterministic schedule checks + Gemini over the full policy wording (long context) |
| **Forensics** | Invoice dated before the incident, arithmetic errors, claim above invoice, photo vs. narrative mismatch, signs of old damage | Deterministic rules + Gemini vision review |
| **Linker** | Finds every claim sharing a phone, email, bank account, vehicle, garage, invoice number or identical photo; detects rings and garages with confirmed-fraud history | Firestore `array-contains-any` over normalised entity keys + SHA-256 photo hashes |
| **Verdict** | Reproducible 0–100 risk score from the flags, an action (fast-track / request info / refer to SIU), and a plain-English explanation | Weighted flag severities + Gemini summary |

The adjuster stays in control: confirm or dismiss any flag (the score updates instantly), record a decision, chat with the claim, and draft a request-for-information email or an SIU referral memo. Every action goes to an audit trail.

The **Red String** view shows the whole network: claims connected by shared identifiers, with confirmed-fraud claims highlighted.

## Lines of business

The same five agents run for every line; each line has its own extraction schema, deterministic rules, policy wording and entity types for the Linker.

| Line | Claim pack | What it checks | Linked through |
|---|---|---|---|
| **Motor** | Claim form, repair invoice, damage photos, police report | Invoice dates and arithmetic, photo vs. narrative, plate and vehicle mismatches, old damage, policy period and IDV | Phone, email, bank account, vehicle, garage, invoice, identical photo |
| **Health** | Claim form, final hospital bill, discharge summary, prescriptions, pharmacy bill, lab reports | 30-day and 24-month waiting periods, room-rent limit, patient not insured, bill dated before admission, bill arithmetic, treatment that does not fit the diagnosis (e.g. ICU charges with no ICU stay) | Phone, email, bank account, hospital, doctor, hospital bill number |
| **Property** | Claim form, contractor invoice, damage photos, police or fire report | Burglary without a police report, loss address vs. insured property, invoice for a different site, invoice dated before the incident, gradual damage presented as sudden | Phone, email, bank account, contractor, property address, invoice, identical photo |

Health and property have demo scenarios and sample packs but no formal benchmark yet.

## Views

- **Claims adjuster:** the live queue (filter by line), claim pages, chat and correspondence drafting.
- **SIU investigator:** a case board that groups referred claims into possible rings (shared people, accounts or documents, or a provider with confirmed fraud) with the amount at stake.
- **Claims manager:** an overview of recommendations by line, the risk score distribution, providers with the most risk, triage time and AI cost per claim from measured token usage.
- **Closed claims:** every historical claim with its outcome, SIU findings, documents and links, searchable and filterable by line, outcome and provider.

The *View as* switcher changes what each persona sees first; it is a demo convenience, not access control.

## Google Cloud and Firebase

| Service | Used for |
|---|---|
| **Gemini on Vertex AI** (`gemini-3.5-flash`) | All five agents: multimodal document reading, policy reasoning, forensic review, explanations, chat and correspondence drafting |
| **Gemini image generation** (`gemini-3.1-flash-image`) | Generating the synthetic damage photos for the demo data |
| **Cloud Run** | The FastAPI backend (`redstring-api`) running the agent pipeline; always-warm instance, background processing |
| **Firebase Hosting** | Serves the React app and routes `/api/**` to Cloud Run |
| **Firebase Authentication** | One-click anonymous demo login; ID tokens verified by the API on every request |
| **Cloud Firestore** | Claims, live per-agent progress (streamed to the UI with `onSnapshot`), flags, links, chat history, audit trail, policies |
| **Cloud Storage for Firebase** | Uploaded claim documents, read by Gemini directly via `gs://` URIs |

## Architecture

```mermaid
flowchart LR
    U(["Adjuster / evaluator<br/>browser"])

    subgraph FB["Firebase"]
        H["Firebase Hosting<br/>React app + /api/** rewrite"]
        A["Firebase Authentication<br/>one-click demo login"]
        S[("Cloud Storage for Firebase<br/>claim documents and photos")]
    end

    subgraph CR["Cloud Run: redstring-api (FastAPI)"]
        API["REST API<br/>verifies Firebase ID token"]
        subgraph P["Background agent pipeline"]
            R["1 · Reader<br/>extract fields"]
            PO["2 · Policy<br/>cover and clauses"]
            FO["3 · Forensics<br/>inconsistencies"]
            L["4 · Linker<br/>related claims"]
            V["5 · Verdict<br/>score + explanation"]
        end
    end

    G{{"Gemini on Vertex AI<br/>gemini-3.5-flash<br/>fallback gemini-2.5-flash"}}
    F[("Cloud Firestore<br/>claims · live agent status · flags<br/>entity link keys · chat · audit")]

    U -->|sign in| A
    U -->|load app| H
    U -->|upload documents| S
    H -->|"/api/** (submit claim, chat, review)"| API
    API -->|start in background| R
    R --> PO & FO & L
    PO & FO & L --> V
    P -.->|"prompts + gs:// URIs"| G
    G -.->|reads documents directly| S
    L <-->|shared-entity lookup| F
    P -->|stage status + results| F
    F ==>|"onSnapshot: live progress"| U

    classDef google fill:#fdeeee,stroke:#e5484d,color:#111318
    classDef dark fill:#161920,stroke:#161920,color:#ffffff
    classDef agent fill:#f4f5f7,stroke:#dde0e5,color:#111318
    class H,A,S,F google
    class G,API dark
    class R,PO,FO,L,V agent
```

Source: [`docs/architecture.mmd`](docs/architecture.mmd) · PNG: [`docs/architecture.png`](docs/architecture.png)

More: [submission description](docs/submission.md) · [benchmark](docs/benchmark.md) · [demo video script](docs/video-script.md)

## Repository layout

```
backend/            FastAPI app for Cloud Run
  app/agents/       reader, policy, forensics, linker, verdict (motor)
  app/lines/        health and property: schemas, rules, prompts, shared engine
  app/rules.py      deterministic checks and risk scoring
  app/policies/     policy wordings (motor, health, home; fictional insurer)
  scripts/          synthetic data generators, seeding, benchmark, end-to-end tests
  tests/
frontend/           React + Vite + Tailwind adjuster console
  public/samples/   one-click sample claim packs
firebase.json       Hosting rewrites, Firestore/Storage rules
scripts/            GCP setup and deploy
```

## Run it yourself

```bash
# one-time
./scripts/setup_gcp.sh                       # APIs, Firestore, IAM
cd backend && uv sync
uv run python scripts/seed.py --images       # generate damage photos (once)
uv run python scripts/seed.py --reset        # seed the motor demo world + run agents
uv run python scripts/lines_seed.py --images # generate property photos (once)
uv run python scripts/lines_seed.py --seed   # seed health and property (staged), run agents
uv run python scripts/lines_seed.py --release  # make the staged health/property data visible

# local dev
uv run uvicorn app.main:app --port 8080      # backend (uses ADC)
cd ../frontend && npm install && npm run dev # frontend, proxies /api to :8080

# deploy
./scripts/deploy.sh

# checks
uv run python scripts/e2e.py --submit live-ring   # live end-to-end test as an anonymous user
uv run python scripts/benchmark.py --seed 11      # held-out benchmark -> docs/benchmark.md
uv run python scripts/seed.py --restore           # reset demo claims and remove self-test claims (evaluators' claims are kept)
```

Demo claims are read-only for evaluators (no re-runs), and each evaluator's queue and Red String view show the demo world plus only their own submissions.

## Demo data

All claimants, policies, garages, hospitals, contractors, phone numbers and bank accounts are **fictional**, generated by `backend/scripts/scenarios.py` (motor) and `backend/scripts/lines_data.py` (health and property). The insurer is "Redstring Demo General Insurance", which does not exist.

| Line | Open demo claims | Closed history | Hidden ring |
|---|---|---|---|
| Motor | 9 (3 clean, 3 single red flags, 3 ring members) | 59, 3 confirmed fraud | Speedfix Motor Works garage |
| Health | 5 (2 clean, 2 single red flags, 1 ring member) | 14, 2 confirmed fraud | Sanjeevani Multispeciality Hospital and its doctor |
| Property | 5 (2 clean, 2 single red flags, 1 ring member) | 12, 2 confirmed fraud | QuickFix Home Restorations contractor |

The *New claim* page offers 5 sample packs; one per line joins its ring live, so evaluators can watch the Linker connect a fresh claim to past fraud.
