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


def main():
    if not os.getenv("GOOGLE_API_KEY"):
        logger.error("GOOGLE_API_KEY is not set. Please update your .env file.")
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
            summary = final_state.get("extraction_error")
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

    # 5. Save results
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
