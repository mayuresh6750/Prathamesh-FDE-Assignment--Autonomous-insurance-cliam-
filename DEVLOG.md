# Claims Agent — Development Log

> **Purpose:** This document records every step of building the Autonomous Claims Adjudication Agent.
> For each step it answers: **What did we do? Why did we do it? How did we do it?**
> Updated continuously as development progresses.

---

## Step 0 — Understanding the Problem (Before Writing Any Code)

### What we did
Read all input files thoroughly before touching any code:
- The assignment brief (`Technical_Assignment_Level3_Claims_Agent.docx`)
- The rulebook (`business_rules.md` — 7 rule groups, v4.2)
- The policy database (`policy_master.csv` — 8 policies)
- All 12 claim documents (`CLM-2026-0001.txt` through `CLM-2026-0012.txt`)

### Why we did it
The client explicitly advised: *"Read the rulebook and all 12 claim documents before you write any code."*
This is not standard advice — it was a signal. Several claims are deliberately tricky, and a system built without reading them first would produce wrong decisions on exactly the edge cases that matter most.

### What we found (the key traps)
| Claim | Hidden Complexity |
|---|---|
| CLM-0003 | Figures say ₹1,85,000; words say "Eighty Five Thousand" — deliberate mismatch (R3.4) |
| CLM-0004 | Policy `660418` expired Jun 2025; claim date is Aug 2025 — outside period (R1.2) |
| CLM-0005 | Policy number is `POL-HL-4481?6` — last digit illegible. Must NOT guess (R1.3) |
| CLM-0006 + CLM-0007 | Same patient, same date, same hospital — potential duplicate. Both must ESCALATE (R6.1) |
| CLM-0008 | Rhinoplasty "for dissatisfaction with appearance" = cosmetic (R5.2). But amount is exactly ₹1L — R3.3 fires first, forcing ESCALATE not REJECT |
| CLM-0009 | Policy `448116` has only ₹45,000 remaining; claim is ₹78,000 — shortfall of ₹33,000 (R3.2) |
| CLM-0010 | Service: 12 Aug 2025. Submitted: 6 Jan 2026 = 147 days. >60 days = REJECT (R4.3) |
| CLM-0011 | Valid asthma claim, but same invoice includes spectacles (₹4,200) — mixed items, ESCALATE (R5.3) |
| CLM-0012 | Same expired policy as CLM-0004 (POL-HL-660418); service Jan 2026 — REJECT (R1.2) |

### How we did it
Manual analysis — read each document, applied each rule by hand, recorded expected outcomes.

---

## Step 1 — Project Scaffold & Foundations

### What we did
Created the full project structure, initialized a Git repository, installed all dependencies, and wrote the core Pydantic data models.

**Files created:**
```
claims-agent/
├── data/
│   ├── claims/          ← 12 claim .txt files
│   ├── policy_master.csv
│   └── business_rules.md
├── src/
│   ├── __init__.py
│   └── models.py        ← All Pydantic schemas
├── .gitignore
├── .env.example
├── requirements.txt
└── .env                 ← API key (gitignored, never committed)
```

**Git commit:** `1d43f62` — *"chore: project scaffold, data files, and Pydantic schemas"*

### Why we did it
**Structure before code.** The interviewers specifically look for meaningful commit history and a clean project layout. Starting by defining Pydantic models — before any LLM code — enforces a discipline: the LLM must conform to our data contract, not the other way around.

Pydantic models serve two critical functions:
1. **Schema enforcement for LLM output** — if Gemini returns invalid/missing fields, Pydantic raises an error immediately, which we can catch and route to ESCALATE.
2. **Shared language between pipeline steps** — every node in LangGraph reads and writes the same `AgentState` object.

### How we did it
- **Folder structure:** Created `src/`, `data/claims/`, `tests/`, `results/` using PowerShell `mkdir`.
- **Data:** Copied claims, policy CSV, and rulebook from the original pack into `data/`.
- **Git:** `git init`, configured author name/email, staged all files, first commit.
- **Dependencies:** Resolved version conflict between `langgraph` and `langchain-google-genai` by checking installed versions and aligning to: `langchain==1.2.18`, `langgraph==1.1.10`, `langchain-google-genai==4.2.2`. Also upgraded `pydantic-core` to `2.46.4` to match `pydantic==2.13.4`.
- **Models defined:**
  - `ExtractedClaim` — what Gemini extracts from each document (all fields Optional; null = uncertain, not missing)
  - `PolicyRecord` — one row from `policy_master.csv`, with computed `remaining_balance` and `plan_type` properties
  - `RuleViolation` — a single triggered rule (code + plain English reason)
  - `ValidationResult` — the full output of the rule engine (decision + all triggered rules)
  - `AgentState` — the object that flows through the entire LangGraph pipeline, growing at each step

### Key design decision made here
> Every field in `ExtractedClaim` is `Optional`. The LLM is explicitly instructed to return `None` if a field is uncertain — not to guess. A `None` on a critical field (e.g., `policy_number`) is not an error — it triggers the appropriate rule (R1.3: unknown policy → ESCALATE). This is how we handle CLM-0005's illegible policy number correctly.

### LLM / Model choice
- **Model:** `gemini-3.6-flash` (Google AI Studio)
- **Why Flash?** Fast, cost-effective, strong structured output capability. The extraction and semantic reasoning tasks in this pipeline don't require a "thinking" model — flash-class models handle them well. Saves cost at scale (relevant to the ₹/1000 claims estimate in the README).
- **API Key:** Stored in `.env` file. `.env` is in `.gitignore`. Never committed.

---

---

## Step 2 — Duplicate Registry & LLM Extraction Node

### What we did
Built two files:
1. **`src/registry.py`** — In-memory duplicate claim detector (Rule R6.1). Pure Python, no LLM.
2. **`src/extraction.py`** — Station 1 of the pipeline. Calls `gemini-3.6-flash` to read raw claim text and return a structured `ExtractedClaim` Pydantic object.

**Git commit:** `55e9673` — *"feat: add duplicate registry (R6) and LLM extraction node (Station 1)"*

### Why we did it
- **Registry first:** Duplicate detection must happen *before* validation, and across the full batch — not per-claim in isolation. It had to be pure Python because it's a data-matching problem. No LLM should decide if two claims are duplicates of each other.
- **Extraction before validation:** You can't validate fields you haven't extracted. But the extraction design critically determines validation quality — which is why the prompt is carefully written.

### How we did it — Registry (`registry.py`)

**The core challenge:** CLM-0006 uses the name "Lakshmi Krishnan" (hospital submission) and CLM-0007 uses "Mrs L. Krishnan" (patient re-submission). Simple exact-string matching would miss this entirely.

**Two-stage solution:**
- **Stage 1:** Group by `(last_name, date_of_service, normalised_provider)`. "Krishnan" is extracted as the last name from both forms.
- **Stage 2:** Within each group, run `thefuzz.token_sort_ratio()` to confirm names are similar (threshold: 70/100). This avoids false positives where unrelated people share a last name.
- Honorifics (`Mr`, `Mrs`, `Dr`, etc.) are stripped via regex before any comparison.
- When a duplicate is found, **both** claim IDs are flagged — including the one already registered (retroactive flagging), because R6.1 says *both* must be escalated.

**Test results:**
```
CLM-0006 duplicates: []              ← First seen, no duplicates yet
CLM-0007 duplicates: ['CLM-2026-0006'] ← Correctly detected!
CLM-0006 flagged: True               ← Retroactively marked
Non-duplicate false positive? []      ← No incorrect matches
```

### How we did it — Extraction (`extraction.py`)

**Tool:** `ChatGoogleGenerativeAI` from `langchain-google-genai` with `.with_structured_output(ExtractedClaim)`.

This means LangChain sends the prompt to Gemini and tells it to return JSON that exactly matches our Pydantic schema. If it doesn't, a `ValidationError` is raised — which we catch and convert to an `extraction_error` on the state.

**The prompt was carefully designed with 7 rules:**
1. **Never guess** — return null if uncertain
2. **Policy number must be exact** — if any character is illegible, return null (catches CLM-0005)
3. **Capture both amounts separately** — `amount_in_figures` vs `amount_in_words` vs `amount_in_words_numeric` (catches CLM-0003)
4. **Parse dates to YYYY-MM-DD** — or null if ambiguous
5. **Verbatim treatment text** — including ALL line items (catches CLM-0011's spectacles)
6. **Prompt injection defence** — the document is framed as data to read, not instructions to follow
7. **Extraction notes** — for the model to flag its own uncertainty

**Temperature = 0** — We want deterministic, factual extraction, not creative interpretation.

**Test result on CLM-0003 (hardest extraction case):**
```
amount_in_figures:       185000.0
amount_in_words:         "Rupees Eighty Five Thousand Only"
amount_in_words_numeric: 85000.0
extraction_notes:        "Discrepancy noted between amount_in_figures (185000.0) 
                          and amount_in_words (85000.0). Hospital contacted without response."
```
Gemini correctly captured the mismatch AND cited the intake desk's note.

### Key design decision
> Extraction failure → immediate ESCALATE. If `extraction_error` is set on the state, the pipeline skips validation entirely and routes straight to the caseworker summary node. This is the correct behaviour — you cannot validate a claim you cannot read.

*This log will be updated at the end of every step.*
