# Client Demonstration Video Guide (Silent Version)

**Target Audience:** The client's CTO.
**Max Length:** 3 minutes.
**Format:** Since there is no voiceover, you must rely on **visual movement** and **on-screen text** (e.g., typing in a text editor or showing pre-written markdown slides) to communicate your points.

---

## 1. Setup (Before you hit Record)
Open your IDE (VS Code) and arrange your screen so you can easily switch between:
1. A text file named `PRESENTATION.md` (where you will show your talking points).
2. The terminal (where you will run the script).
3. The `results/adjudication_output.csv` file.
4. The `README.md` (showing the Mermaid diagram).

---

## 2. The Video Flow (Step-by-Step)

### Part 1: Business Value & Architecture (0:00 - 0:45)
1. **Show text on screen (`PRESENTATION.md`):**
   > **Goal:** Automate clear-cut claims, reject invalid ones, and escalate complex cases with clean summaries to save caseworker time.
2. **Action:** Switch to `README.md` and highlight/scroll past the Mermaid Architecture diagram. Pause for 5 seconds so the viewer can read the LangGraph flow (Extraction -> Validation -> Summarization).

### Part 2: The Escalation Boundary (0:45 - 2:00)
1. **Show text on screen:**
   > **Escalation Boundaries:** The system deliberately *refuses* to guess. It flags Ambiguity, High-Value payouts (>₹1L), and Adversarial Attacks.
2. **Action (The Run):** Open the terminal and type `python src/run.py`. Hit enter.
3. **Action (Highlight Logs):** While it runs, use your mouse to highlight key lines in the terminal output:
   - Highlight: `[INFO] Waiting 15s before next claim (rate-limit guard)` (Shows you handled API quotas).
   - Highlight: `[WARNING] validation: [R0.1] Injection attempt detected` (Shows adversarial defense on CLM-0013).
4. **Action (The Output):** Open `results/adjudication_output.csv`. 
   - Highlight row CLM-2026-0004 (Show it was outright `REJECTED` for an expired policy).
   - Highlight row CLM-2026-0011 (Show it was `ESCALATED` and highlight the clean English caseworker summary generated at the end of the row).

### Part 3: Reliability & Path to Production (2:00 - 3:00)
1. **Show text on screen:**
   > **Testing & Path to Production:** All edge cases and adversarial attacks are mathematically verified via Pytest. 
2. **Action (The Tests):** In the terminal, type `pytest tests/test_claims.py -v`. Hit enter. Let the viewer watch all 13 tests pass green.
3. **Show text on screen (Final Slide):**
   > **Next Steps before going live:**
   > 1. **Shadow Mode:** Run alongside human caseworkers for 30 days to measure false-positive rates before automating payouts.
   > 2. **API Integration:** Connect the extraction node directly to the hospital billing API to eliminate OCR text-file errors.
4. **Action:** Stop recording.

---

### Tips for Silent Videos:
- **Move the mouse deliberately:** Use your cursor to point at things (like the 100% passing tests or the R0.1 warning) since you can't tell the viewer where to look.
- **Pacing:** Leave text on the screen for about 5-8 seconds before moving on. If you can read it twice in your head, it's long enough.
