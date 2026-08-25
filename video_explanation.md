# Client Demonstration Video Script

**Target Audience:** The client's CTO.
**Max Length:** 3 minutes.
**Goal:** Present the business value, defend the escalation boundaries, and define the path to production.

---

## 1. Introduction & Business Value (0:00 - 0:45)
* **Visual:** Show the `adjudication_output.csv` on the screen or the Mermaid architecture diagram in the `README.md`.
* **What to say (Speak to the CTO):** 
> "Hello, I'm here to present the Autonomous Claims Agent. For the business, this system clears your operational bottleneck. It uses a LangGraph pipeline to instantly approve clean claims and instantly reject fundamentally invalid ones (like expired policies). But most importantly, it stops your caseworkers from doing data entry. Now, they only look at the difficult claims, and they are handed a clean 3-sentence summary of exactly why it needs their human review."

## 2. The Escalation Boundary (0:45 - 2:00)
* **Visual:** Show the terminal running `python src/run.py` or show the code for `validation.py` (specifically the R0.1 guard or R3.3 high-value rule).
* **What to say (What it deliberately does *not* decide):** 
> "A system that approves everything is dangerous. I designed this to deliberately *refuse* to make decisions in three areas. First, **Ambiguity**: if a policy number is illegible, it refuses to guess and escalates it. Second, **High Financial Risk**: anything over ₹1 Lakh is force-escalated for human sign-off, even if the rules pass. Third, **Adversarial Attacks**: I built a deterministic, pure-Python guard that scans for prompt injections. If a user writes 'approve this immediately' on their claim, the system catches it instantly without relying on the LLM, and force-escalates it."

## 3. Path to Production (2:00 - 3:00)
* **Visual:** Show the automated test suite running (`pytest tests/test_claims.py -v`) to show it passing 100%.
* **What to say (What you want to see before going live):** 
> "While the test suite proves the rules fire correctly, before routing live patient claims through this, I would want to see two things. First, **Shadow Mode Testing**: I want to run this pipeline alongside your current caseworkers for 30 days without automating the final payout, comparing the AI's decisions to human decisions to measure the exact false-positive rate. Second, **API Integration**: Currently it reads `.txt` files; I'd want to wire the extraction node directly into your hospital billing portal's API to eliminate OCR errors entirely."
