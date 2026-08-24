"""
models.py
---------
All data schemas for the Claims Adjudication Agent.

These Pydantic models serve two purposes:
1. They define exactly what fields the LLM extraction step must return.
2. They define the state object that flows through the LangGraph pipeline.

Using Pydantic means if the LLM returns invalid data, we get a hard error
immediately — not a silent failure downstream.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Decision(str, Enum):
    """The three possible adjudication outcomes."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


# ---------------------------------------------------------------------------
# Extraction schema  (what the LLM must return from Station 1)
# ---------------------------------------------------------------------------

class ExtractedClaim(BaseModel):
    """
    Structured fields extracted from a raw, unstructured claim document.

    IMPORTANT: Every field is Optional. If the LLM cannot extract a field
    with confidence, it MUST return None — never guess. A None field is not
    a failure; it triggers the appropriate rule (e.g., None policy_number → R1.3 ESCALATE).
    """

    claim_id: Optional[str] = Field(
        default=None,
        description="The claim reference number, e.g. CLM-2026-0001"
    )
    policy_number: Optional[str] = Field(
        default=None,
        description="The policy number exactly as it appears in the document. "
                    "If illegible or partially obscured, return None — do NOT guess."
    )
    claimant_name: Optional[str] = Field(
        default=None,
        description="Full name of the person receiving treatment, as written."
    )
    date_of_service: Optional[date] = Field(
        default=None,
        description="The date treatment was received. Parse to YYYY-MM-DD. "
                    "If ambiguous or missing, return None."
    )
    date_of_submission: Optional[date] = Field(
        default=None,
        description="The date the claim was submitted. Parse to YYYY-MM-DD. "
                    "If missing, return None."
    )
    provider: Optional[str] = Field(
        default=None,
        description="Name and location of the hospital or clinic."
    )
    treatment_description: Optional[str] = Field(
        default=None,
        description="Full description of the medical procedure or treatment, "
                    "verbatim from the document."
    )
    amount_in_figures: Optional[float] = Field(
        default=None,
        description="The claim amount as stated in numeric figures (e.g., 78400.00). "
                    "Do not convert from words."
    )
    amount_in_words: Optional[str] = Field(
        default=None,
        description="The claim amount as written in words, verbatim "
                    "(e.g., 'Rupees Seventy Eight Thousand Four Hundred Only')."
    )
    amount_in_words_numeric: Optional[float] = Field(
        default=None,
        description="Your best numeric interpretation of amount_in_words. "
                    "If you cannot parse it confidently, return None."
    )
    extraction_notes: Optional[str] = Field(
        default=None,
        description="Any observations about document quality, illegible text, "
                    "or fields that were uncertain. Be specific."
    )


# ---------------------------------------------------------------------------
# Policy record  (loaded deterministically from policy_master.csv)
# ---------------------------------------------------------------------------

class PolicyRecord(BaseModel):
    """Represents one row from policy_master.csv."""

    policy_no: str
    holder_name: str
    plan: str
    policy_start: date
    policy_end: date
    sum_insured_inr: float
    sum_utilised_inr: float
    dependants: list[str] = Field(default_factory=list)

    @property
    def remaining_balance(self) -> float:
        """How much cover is left on this policy."""
        return self.sum_insured_inr - self.sum_utilised_inr

    @property
    def plan_type(self) -> str:
        """Returns Silver, Gold, or Platinum regardless of Family/Individual prefix."""
        for tier in ("Silver", "Gold", "Platinum"):
            if tier in self.plan:
                return tier
        return "Unknown"


# ---------------------------------------------------------------------------
# Validation result  (output of Station 2)
# ---------------------------------------------------------------------------

class RuleViolation(BaseModel):
    """A single rule that fired during validation."""
    rule_code: str = Field(description="e.g. 'R3.3'")
    description: str = Field(description="Plain English explanation of why this rule fired.")


class ValidationResult(BaseModel):
    """The complete output of the rule validation step."""
    decision: Decision
    triggered_rules: list[RuleViolation] = Field(default_factory=list)
    shortfall_inr: Optional[float] = Field(
        default=None,
        description="Populated when R3.2 fires — the exact amount by which the "
                    "claim exceeds the remaining balance."
    )
    submission_delay_days: Optional[int] = Field(
        default=None,
        description="Populated when R4.2 or R4.3 fires."
    )


# ---------------------------------------------------------------------------
# Agent State  (the object that flows through the entire LangGraph pipeline)
# ---------------------------------------------------------------------------

class AgentState(BaseModel):
    """
    The state object passed between every node in the LangGraph pipeline.

    Each node reads from this state and writes back to it.
    No node communicates with another except through this object.
    """

    # Input
    raw_text: str = Field(description="The original, unmodified claim document text.")
    claim_id: str = Field(description="Claim ID, extracted from filename or document.")

    # After Station 1 (Extraction)
    extracted: Optional[ExtractedClaim] = Field(default=None)
    extraction_error: Optional[str] = Field(
        default=None,
        description="If extraction failed entirely (e.g. LLM returned malformed JSON), "
                    "this field holds the error message. The pipeline routes to ESCALATE."
    )

    # After policy lookup (deterministic step between Station 1 and 2)
    policy_record: Optional[PolicyRecord] = Field(default=None)

    # After Station 2 (Validation)
    validation_result: Optional[ValidationResult] = Field(default=None)

    # After Station 3 (Caseworker Summary — only if ESCALATE)
    caseworker_summary: Optional[str] = Field(
        default=None,
        description="Written for the caseworker. Names every rule that fired, "
                    "explains what is uncertain, and states what they need to check."
    )

    # Final output fields (written at end of pipeline)
    final_decision: Optional[Decision] = Field(default=None)
    pipeline_error: Optional[str] = Field(
        default=None,
        description="Set if an unexpected error caused the pipeline to fail. "
                    "A pipeline_error always results in ESCALATE."
    )
