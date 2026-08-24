# Claims Agent — Architecture & Development Log

> **Purpose:** This document explains the architecture, tech stack, and process flow of the Autonomous Claims Adjudication Agent. It is designed to be a clear, high-level overview of how the pipeline works from start to finish.

---

## 1. Tech Stack
The system was built using the following modern AI and Python tools:
- **Python 3.11**: The core programming language.
- **LangGraph**: Used to orchestrate the pipeline as a Directed Acyclic Graph (DAG), ensuring predictable state flow between tasks.
- **LangChain**: Used as the framework to interact with the LLM API and enforce structured JSON outputs.
- **Groq API (`openai/gpt-oss-120b`)**: The underlying LLM engine. Chosen for its high daily rate limits and excellent adherence to pure `json_mode`.
- **Pydantic**: Used for strict data validation. It defines the exact schema the LLM must return, ensuring downstream code never crashes on unexpected data.
- **TheFuzz**: Used for fuzzy string matching (e.g., matching "Mrs. L. Krishnan" to "Lakshmi Krishnan").
- **pytest**: Used for the automated test suite.

---

## 2. High-Level Architecture
The system operates as a **batch processing pipeline**. It takes a folder of unstructured claim documents (`.txt`), adjudicates each one against a policy database (`.csv`) and business rules, and generates a final adjudication report.

The core of the system is a **LangGraph DAG** containing three primary nodes:
1. **Extraction Node:** Uses the LLM to read the raw text and extract structured data (dates, amounts, names, treatment details).
2. **Validation Node:** The "brain" of the system. It mixes deterministic Python rules (math, dates, policy lookups) with Semantic LLM checks (identifying cosmetic surgery or pre-existing conditions).
3. **Summarization Node:** If a claim requires human review, the LLM generates a concise, 3-sentence summary explaining why.

---

## 3. Low-Level Architecture & Process Flow
Here is the exact step-by-step flow of how a claim moves through the system.

### A. Initialization (`run.py`)
Before processing individual claims, the main script initializes an in-memory **Claim Registry**. This registry tracks every claimant name, service date, and provider across the entire batch to catch duplicate submissions (Rule R6.1).

### B. State Management (`models.py`)
The entire graph shares a single Pydantic object called `AgentState`. As a claim moves from node to node, fields in `AgentState` get filled in (e.g., `raw_text` -> `extracted_claim` -> `validation_result` -> `caseworker_summary`).

### C. Node 1: Extraction (`extraction.py`)
- **Input:** Raw text of the claim.
- **Process:** The LLM is prompted to act as a data extractor. It is provided with a strict JSON schema.
- **Guardrails:** If the LLM fails to extract the document (due to API rate limits or invalid JSON), an `extraction_error` is flagged. The graph then **bypasses validation** and routes the claim directly to human escalation. You cannot adjudicate a claim you cannot read.

### D. Node 2: Validation (`validation.py`)
If extraction succeeds, the structured data enters the validation engine.
1. **R0.1 Adversarial Guard (Pure Python):** The system first scans all extracted text for known prompt-injection phrases (e.g., *"Ignore previous instructions"*). If found, the claim is force-escalated. Since this check uses zero LLM calls, it cannot be manipulated by adversarial text.
2. **Deterministic Rules (Pure Python):**
   - **R1:** Looks up the policy in `policy_master.csv` and checks expiration dates.
   - **R2:** Uses fuzzy string matching to verify the claimant is on the policy.
   - **R3:** Checks if amounts exceed the ₹1,00,000 threshold or the remaining policy balance.
   - **R4:** Checks if the claim was submitted more than 60 days late.
   - **R6:** Checks the in-memory registry for duplicates.
3. **Semantic Rules (LLM):**
   - **R5 / R7:** A secondary, focused LLM call evaluates just the `treatment_description`. It determines if the procedure is cosmetic, dental, sports-related, or indicates a pre-existing condition.
4. **Decision Resolution:**
   - **REJECT** overrides **ESCALATE**. If a claim is fundamentally invalid (e.g., expired policy), it is rejected instantly to save caseworker time.
   - Exception: Rule **R3.3** (claims >= ₹1,00,000) forces an **ESCALATE** regardless of other rules, mandating human review for high-value payouts.
   - If no rules are triggered, the decision is **APPROVE**.

### E. Node 3: Summarization (`summarization.py`)
- If the final decision is **ESCALATE**, this node is triggered.
- It feeds the list of triggered rules and their descriptions back to the LLM to write a clean, readable summary for the caseworker dashboard.

### F. Post-Processing & Output (`run.py`)
- After all claims are processed, a 15-second inter-claim delay (rate-limit guard) ensures the Groq API daily quotas are not exhausted by retry-storms.
- A final pass checks the Claim Registry to retroactively flag the *first* instance of a duplicate claim (since duplicates are only detected when the *second* claim arrives).
- The final results are written to `results/adjudication_output.csv`.

---

## 4. Key Engineering Highlights
- **Adversarial Resilience:** The system successfully neutralizes prompt injection (CLM-0013) and semantic poisoning (CLM-0014) by separating data extraction from logic evaluation.
- **Provider-Agnostic:** Originally built on `gemini-3.6-flash`, the system was migrated to open-source models on the Groq API (`gpt-oss-120b`). We hardened the integration by using explicit JSON schemas in the system prompt rather than relying on brittle Tool-Calling APIs.

---

## 5. Design Justifications & Architecture FAQ

### Q1: Why did we choose this specific Tech Stack?
- **LangGraph over simple Python scripts:** While a simple Python script could call the LLM three times, LangGraph provides a robust, enterprise-grade architecture. It manages **state** natively, allows for cyclic retries if an LLM fails, and cleanly separates concerns (Extraction, Validation, Summarization) into independent, testable nodes.
- **Pydantic:** LLMs are inherently non-deterministic. Pydantic acts as a strict contract that forces the LLM's unstructured output into a deterministic, typed JSON object. If the LLM hallucinates a field name, Pydantic catches it immediately, preventing downstream crashes.
- **Groq API / OSS Models:** High-volume claims processing requires high rate limits and low latency. Groq's LPU architecture provides immense speed, and by enforcing strict `json_mode`, we achieve GPT-4 level data extraction accuracy using much cheaper open-source models.

### Q2: For data extraction, could we use libraries like `unstructured` instead of an LLM?
No, because they serve two completely different purposes:
- **`unstructured` (or OCR tools like PyTesseract):** These are **ingestion** libraries. They take messy formats (PDFs, Word docs, scanned images) and convert them into a raw string of text. 
- **LLMs (with structured output):** These are **semantic extraction** engines. 
If you pass a claim PDF to `unstructured`, you just get a massive string of text. You still need the LLM to read that string, understand the context, and say *"Ah, the ₹78,000 is the claim amount, and the Pyelonephritis is the treatment."* Because our input files are already plain `.txt`, we didn't need ingestion libraries; we just needed the LLM to map the text to our Pydantic schema.

### Q3: To check deterministic rules (Dates, Amounts, Policy lookup), how is it done? Can we use RAG? Which is more effective?
Currently, this is done using **Pure Python** (`if/else` logic, exact string matching, and date math). 

**Could we use RAG?** 
Theoretically, yes. You could embed the `policy_master.csv` into a Vector Database, retrieve the policy using RAG, and ask the LLM: *"Given this retrieved policy and this claim, should it be approved?"*

**Which is more effective?**
**Pure Python is vastly more effective, safer, and cheaper** for this specific task. Here is why:
1. **Math & Logic:** LLMs and RAG struggle with exact arithmetic. In CLM-0009, the policy has ₹45,000 remaining and the claim is for ₹78,000. Python calculates the ₹33,000 shortfall with 100% accuracy in 1 millisecond. RAG relies on probabilistic text generation and will frequently hallucinate the math.
2. **Date Comparisons:** Calculating if a claim was submitted exactly >60 days after the service date (Rule R4.3) is trivial for Python's `datetime` module, but highly error-prone for an LLM.
3. **Cost/Speed:** RAG requires vector embeddings, database lookups, and expensive LLM tokens. Reading a CSV into Python memory and checking an `if` statement is free and instant.

**Conclusion:** We use the LLM *only* for things Python cannot do (reading messy text, judging if a surgery is cosmetic). We use Python for things it does perfectly (math, dates, and database lookups).
