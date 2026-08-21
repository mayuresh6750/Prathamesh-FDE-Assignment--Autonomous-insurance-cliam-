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

*This log will be updated at the end of every step.*
