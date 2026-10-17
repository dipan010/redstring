# Submission: Redstring (Team HandOff)

**Track:** BFSI: Intelligent Risk, Fraud & Financial Experiences

| | |
|---|---|
| Deployed prototype | https://redstring-511910.web.app (click *Enter demo as adjuster*) |
| GitHub repository | https://github.com/dipan010/redstring |
| Demo video | _add link_ |

## Brief description

Redstring is an AI copilot for motor-insurance claim adjusters that connects the dots on every claim. An adjuster drops in a claim pack (claim form, repair invoice, damage photos, police report) and five Gemini-powered agents take over: **Reader** extracts every field from the PDFs and photos; **Policy** checks cover, exclusions, deductible and missing documents against the policy wording and quotes the clause; **Forensics** looks for inconsistencies such as an invoice dated before the accident, totals that don't add up, or photos that show front damage for a claimed rear-end collision; **Linker** connects the claim to every other claim that shares a phone, bank account, garage, invoice number or identical photo, exposing fraud rings; and **Verdict** produces a reproducible 0–100 risk score, a recommended action (fast-track, request information, or refer to the Special Investigation Unit) and a plain-English explanation. The adjuster stays in control: confirm or dismiss any flag, chat with the claim, draft emails and SIU memos, and see the whole network in the Red String graph view. On a held-out set of 32 synthetic claims it reached 100% precision and 94% recall at about ₹2.8 of AI cost and ~19 seconds per claim.

**How we use Google Cloud and Firebase**

- **Gemini (Vertex AI):** all five agents run on `gemini-3.5-flash` with structured JSON output: multimodal reading of PDFs and photos passed straight from Cloud Storage as `gs://` URIs, long-context reasoning over the policy wording, forensic review of photos against the narrative, explanations, claim chat and correspondence drafting. Calls that are slow or rate-limited fall back to `gemini-2.5-flash`. The demo's damage photos were generated with `gemini-3.1-flash-image`.
- **Cloud Run:** hosts the FastAPI backend that orchestrates the agent pipeline. A claim request returns immediately and the agents run in the background (Policy, Forensics and Linker in parallel), on an always-warm instance with Firebase ID-token verification and per-user rate limits.
- **Firestore:** the system of record and the live channel. Each agent writes its status as it finishes, and the React app streams it with `onSnapshot` to show live progress. Firestore also stores extracted fields, flags with evidence, normalised entity keys that the Linker queries with `array-contains-any`, linked claims, chat history, policies and an audit trail of every adjuster action.
- **Firebase:** **Hosting** serves the React app and routes `/api/**` to Cloud Run; **Authentication** provides one-click anonymous demo login (plus Google sign-in); **Cloud Storage for Firebase** holds uploaded documents under per-user security rules.
