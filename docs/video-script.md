# Demo video script (target 3:30, hard limit 4:00)

Record at 1440×900 in a clean browser window, signed out. Before recording, run
`cd backend && uv run python scripts/seed.py --restore` so the demo state is fresh.

| Time | Screen | Voice-over |
|---|---|---|
| 0:00–0:20 | Login page | "Insurance fraud is organised. The same garages, bank accounts and photos show up across claims filed by different people, but adjusters review claims one at a time. Redstring connects the dots on every claim." |
| 0:20–0:35 | Click **Enter demo as adjuster** → Queue | "This is the adjuster's queue, sorted by risk. Five Gemini agents have already triaged these claims: three clean ones are fast-tracked, the risky ones go to the Special Investigation Unit." |
| 0:35–1:20 | Open **RS-1005** (Ishaan Gupta) | "Here's a rear-end collision claim. The Reader agent extracted every field from the PDFs and photo. Forensics noticed the photo shows front-end damage, not rear. The Policy agent quotes clause 4.5: damage not caused by the reported incident isn't covered. And the claimed amount is higher than the invoice. Every flag shows its evidence." Scroll to the policy section briefly. |
| 1:20–1:45 | Chat panel: click **Why is this claim flagged?** | "Adjusters can ask the claim questions; answers cite the flags and clauses." Then click **SIU referral memo**: "and draft correspondence in one click." |
| 1:45–2:05 | Open **RS-1009** → linked claims → **Red String** tab | "This one looks routine on its own. But the Linker found its bank account on two other claims by different people, an invoice number already used, and a garage with three confirmed fraud cases. That's a ring." Hover a few nodes. |
| 2:05–2:50 | **New claim** → click **Fresh claim from Speedfix Motor Works** | "Let's submit a brand-new claim live. The documents upload to Cloud Storage, Cloud Run starts the agents, and progress streams back from Firestore." Wait on the stage tracker. "In about twenty seconds: Reader, then Policy, Forensics and Linker in parallel, then Verdict: a high risk score and a referral to the SIU. The Linker connected it to the same ring, through a shared phone, bank account and a reused photo." |
| 2:50–3:05 | Click a flag's ✓ and another's ✕ | "The adjuster stays in control: confirm or dismiss any flag and the score updates. Everything goes to an audit trail." |
| 3:05–3:30 | Deck: architecture slide, then benchmark slide | "Under the hood: React on Firebase Hosting, Firebase Auth, Cloud Run for the agents, Firestore for state and live updates, Cloud Storage for documents, and Gemini on Vertex AI. On a held-out benchmark of 32 synthetic claims: 95% precision, 100% recall, about 18 seconds and ₹3.0 per claim. Redstring: connect the dots on every claim." |

Tips: keep the cursor still while talking; cut the wait during agent processing to about 5 seconds if needed;
export at 1080p.
