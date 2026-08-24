"""
run.py
------
The main entry point for the Autonomous Claims Adjudication Agent.

Usage:
  python src/run.py

This script:
1. Initializes the in-memory duplicate ClaimRegistry.
2. Builds the LangGraph workflow.
3. Iterates over all claims in `data/claims/`.
4. Runs the graph for each claim.
5. Saves the final output to `results/adjudication_output.csv`.
"""

import csv
import glob
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from models import AgentState
from registry import ClaimRegistry
from graph import build_adjudication_graph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run")

load_dotenv()

DATA_DIR = Path("data/claims")
RESULTS_DIR = Path("results")
OUTPUT_CSV = RESULTS_DIR / "adjudication_output.csv"

# Delay between claims to stay under Groq free-tier 30 RPM limit.
# At 3 LLM calls per claim, 15s gap keeps us at ~12 RPM — well under the limit.
# This prevents retry storms that burn through the 250 RPD daily quota.
INTER_CLAIM_DELAY_SECONDS = 15


def main():
    if not os.getenv("GROQ_API_KEY"):
        logger.error("GROQ_API_KEY is not set. Please add it to your .env file.")
        return

    # Ensure results directory exists
    RESULTS_DIR.mkdir(exist_ok=True)

    # 1. Initialize registry and compile graph
    logger.info("Initializing duplicate registry and building workflow graph...")
    registry = ClaimRegistry()
    app = build_adjudication_graph(registry)

    # 2. Find all claims
    claim_files = sorted(glob.glob(str(DATA_DIR / "CLM-*.txt")))
    if not claim_files:
        logger.error(f"No claims found in {DATA_DIR}")
        return

    logger.info(f"Found {len(claim_files)} claims to process.")

    results_data = []

    # 3. Run the batch
    for filepath in claim_files:
        filename = Path(filepath).name
        claim_id = filename.replace(".txt", "")
        
        logger.info("-" * 60)
        logger.info(f"Processing {claim_id}...")

        with open(filepath, "r", encoding="utf-8") as f:
            raw_text = f.read()

        initial_state = AgentState(
            claim_id=claim_id,
            raw_text=raw_text,
        )

        # Run the LangGraph app
        final_state = app.invoke(initial_state)

        # 4. Extract metrics
        decision = "ERROR"
        rules_triggered = []
        shortfall = ""
        delay = ""
        summary = ""

        if final_state.get("extraction_error"):
            decision = "ESCALATE"
            rules_triggered = ["EXTRACTION_FAILED"]
            err = str(final_state.get("extraction_error", ""))
            if "RateLimitError" in err or "rate_limit_exceeded" in err:
                summary = (
                    "Document could not be processed: API rate limit reached. "
                    "Claim escalated automatically for manual caseworker review."
                )
            else:
                summary = (
                    "Document extraction failed — the claim document could not be "
                    "parsed into structured data. Escalated for manual review."
                )
        elif final_state.get("final_decision"):
            decision = final_state.get("final_decision").value
            val_res = final_state.get("validation_result")
            if val_res:
                rules_triggered = [v.rule_code for v in val_res.triggered_rules]
                shortfall = val_res.shortfall_inr if val_res.shortfall_inr is not None else ""
                delay = val_res.submission_delay_days if val_res.submission_delay_days is not None else ""
            
            if decision == "ESCALATE":
                summary = final_state.get("caseworker_summary", "No summary generated.")

        # Prepare for CSV
        row = {
            "Claim ID": claim_id,
            "Outcome": decision,
            "Triggered Rules": ", ".join(rules_triggered),
            "Shortfall (INR)": shortfall,
            "Submission Delay (Days)": delay,
            "Caseworker Summary": summary,
        }
        results_data.append(row)

        logger.info(f"Completed {claim_id}: {decision}")

        # Rate-limit guard: pause between claims to avoid burning RPD quota on retries
        logger.info(f"Waiting {INTER_CLAIM_DELAY_SECONDS}s before next claim (rate-limit guard)...")
        time.sleep(INTER_CLAIM_DELAY_SECONDS)

    # 5. Post-processing: catch retroactively flagged duplicates (R6.1)
    # When CLM-0006 is processed first, no duplicate exists yet, so it passes.
    # When CLM-0007 comes in, the registry retroactively flags CLM-0006 in memory.
    # But CLM-0006 has already been adjudicated. This pass corrects that.
    logger.info("Running post-processing duplicate check...")
    for row in results_data:
        cid = row["Claim ID"]
        if registry.is_flagged(cid) and row["Outcome"] != "ESCALATE":
            logger.info(
                f"[{cid}] Retroactively upgrading to ESCALATE (R6.1 — duplicate detected "
                f"after initial adjudication)."
            )
            existing_rules = row["Triggered Rules"]
            row["Outcome"] = "ESCALATE"
            row["Triggered Rules"] = (
                f"{existing_rules}, R6.1" if existing_rules else "R6.1"
            )
            row["Caseworker Summary"] = (
                f"This claim was retroactively flagged as a potential duplicate (R6.1) "
                f"during batch post-processing. A later claim in the same batch was "
                f"submitted for the same claimant, date, and provider. Both claims must "
                f"be reviewed by a caseworker before any payment is made."
            )

    # 6. Save results
    logger.info("-" * 60)
    logger.info(f"Batch complete. Writing results to {OUTPUT_CSV}")
    
    fieldnames = [
        "Claim ID", "Outcome", "Triggered Rules", 
        "Shortfall (INR)", "Submission Delay (Days)", "Caseworker Summary"
    ]
    
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results_data)

    logger.info("Done.")


if __name__ == "__main__":
    main()
