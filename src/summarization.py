"""
summarization.py
----------------
Station 3: Caseworker Summary Generation.

Only runs if the final decision is ESCALATE.
Uses Gemini to generate a concise, human-readable summary of WHY the claim
was escalated, referencing the specific rules triggered.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from models import AgentState

load_dotenv()
logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.6-flash"


class SummaryOutput(BaseModel):
    caseworker_summary: str


SUMMARY_SYSTEM_PROMPT = """You are a medical claims assistant.
Your job is to write a concise exception summary for a human caseworker.
The claim has been ESCALATED. You will be provided with the extraction details
and the exact rules that were violated.

Rules for your summary:
1. Be extremely concise (max 3-4 sentences).
2. Explicitly name the rules that triggered the escalation (e.g., 'R3.4', 'R7.1').
3. Focus ONLY on why the claim was escalated. Do not summarise the entire claim.
4. If extraction failed entirely, state that the document could not be read.
"""

SUMMARY_USER_TEMPLATE = """
--- EXTRACTION ---
{extraction}

--- VIOLATIONS ---
{violations}
"""


def _get_llm() -> ChatGoogleGenerativeAI:
    api_key = os.getenv("GOOGLE_API_KEY")
    return ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        google_api_key=api_key,
        temperature=0,
    )


def run_summarization(state: AgentState) -> AgentState:
    """
    LangGraph node: Station 3 — Summarization.
    """
    logger.info(f"[{state.claim_id}] Generating caseworker summary...")

    # If it's not an escalation, we don't need a summary
    if state.final_decision and state.final_decision.value != "ESCALATE":
        return state

    try:
        llm = _get_llm()
        structured_llm = llm.with_structured_output(SummaryOutput)

        if state.extraction_error:
            extraction_text = f"EXTRACTION FAILED: {state.extraction_error}"
            violations_text = "N/A - Could not extract data."
        else:
            extraction_text = state.extracted.model_dump_json(indent=2) if state.extracted else "None"
            if state.validation_result and state.validation_result.triggered_rules:
                violations_text = "\n".join(
                    f"- {v.rule_code}: {v.description}"
                    for v in state.validation_result.triggered_rules
                )
            else:
                # E.g. manual override or logic error, shouldn't happen if properly escalated
                violations_text = "No specific rules logged."

        messages = [
            ("system", SUMMARY_SYSTEM_PROMPT),
            ("human", SUMMARY_USER_TEMPLATE.format(
                extraction=extraction_text,
                violations=violations_text,
            )),
        ]

        result: SummaryOutput = structured_llm.invoke(messages)
        
        return state.model_copy(update={"caseworker_summary": result.caseworker_summary})

    except Exception as e:
        error_msg = f"Failed to generate summary: {str(e)}"
        logger.error(f"[{state.claim_id}] {error_msg}")
        return state.model_copy(update={"caseworker_summary": error_msg})
