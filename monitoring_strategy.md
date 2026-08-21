# Production Monitoring & Operations Strategy

Deploying an autonomous LLM-driven adjudication system requires monitoring strategies that go beyond traditional uptime and latency checks. The primary risks in this hybrid architecture are **LLM drift**, **prompt injection**, and **semantic edge cases** that the static rulebook fails to cover.

## 1. Monitoring LLM Drift and Regression
Language models evolve, and even pinned versions can exhibit changing behaviours over time if upstream providers update underlying safety filters or routing.
- **Golden Dataset Evaluations:** Run a nightly CI pipeline that processes a "golden dataset" of 500 historically adjudicated claims (including all known edge cases, like mismatched amounts and complex clinical text). Assert that the deterministic outcomes (`APPROVE`, `REJECT`, `ESCALATE`) and extracted Pydantic fields match exactly 100% of the time. Any drop below 100% indicates model drift or an unannounced upstream change.
- **Extraction Confidence Tracking:** Monitor the frequency of `null` values being extracted for critical fields (like `policy_number`). A sudden spike indicates the LLM has become overly conservative or that document scan quality has degraded.

## 2. Surfacing Edge Cases & Human-in-the-Loop Feedback
The system is designed to gracefully degrade to a human caseworker via the `ESCALATE` outcome.
- **Escalation Ratio:** Track the percentage of claims landing in `APPROVE`, `REJECT`, and `ESCALATE`. If the `ESCALATE` bucket grows beyond the historical baseline (e.g., >25%), it suggests a new type of claim pattern has emerged that the semantic prompt is struggling to categorise confidently.
- **Caseworker Overrides:** The most critical metric is the **Override Rate**. When a caseworker reviews an `ESCALATE` claim, do they agree with the LLM's exception summary? If a caseworker forces a `REJECT` on a claim the system `APPROVE`d, this is a "False Positive" and must be instantly routed to the engineering team. Every override should trigger a ticket to update the golden dataset and adjust the `business_rules.md` or extraction prompts.

## 3. Security and Adversarial Monitoring
Because the system reads unstructured text from unverified users, it is vulnerable to Prompt Injection and Semantic Poisoning (as tested in `CLM-0013` and `CLM-0014`).
- **Prompt Injection Logging:** Monitor the `extraction_notes` field. If the LLM extracts text containing phrases like "ignore instructions", "override", or "bypass", this should trigger a high-priority alert.
- **Length and Complexity Caps:** Monitor the token length of the raw OCR text. Adversarial attacks often hide in deeply nested or abnormally long paragraphs. Claims exceeding historical token lengths (e.g., >3000 tokens) should be automatically escalated to human review, regardless of what the LLM extracts.
