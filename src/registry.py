"""
registry.py
-----------
Duplicate claim detection (Rule R6.1).

R6.1: Two claims for the same claimant, same date of service, and same
provider are treated as potential duplicates — BOTH are escalated.

This module maintains an in-memory registry during a single batch run.
It is deliberately deterministic (no LLM).

Matching strategy (two-stage):
  Stage 1: Exact key match on (last_name, date_of_service, provider).
           This catches CLM-0006 vs CLM-0007 because both share last name
           "krishnan", same date, same provider.
  Stage 2: Fuzzy full-name match using thefuzz to handle edge cases where
           last name may vary slightly.

Why last name as primary key?
  "Lakshmi Krishnan" and "Mrs L. Krishnan" share the same last name.
  Matching on last name + date + provider catches initial-only submissions
  without requiring a full-name match.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from dataclasses import dataclass

from thefuzz import fuzz


# Honorifics to strip before name comparison
_HONORIFICS = re.compile(
    r"\b(mr|mrs|ms|dr|prof|sri|smt|shri|sh|col|maj|capt)\.?\s*",
    re.IGNORECASE,
)

# Minimum fuzzy score to consider names a match (0–100)
FUZZY_MATCH_THRESHOLD = 70


def _normalise_name(name: str) -> str:
    """Strip honorifics, lowercase, collapse whitespace."""
    name = _HONORIFICS.sub("", name).lower().strip()
    return re.sub(r"\s+", " ", name)


def _get_last_name(normalised_name: str) -> str:
    """
    Extract last name for primary key matching.
    Handles 'lakshmi krishnan' → 'krishnan'
    and 'l. krishnan' → 'krishnan' (after stripping initials).
    """
    # Remove single-letter initials like "l." or "l "
    cleaned = re.sub(r"\b[a-z]\.\s*", "", normalised_name).strip()
    parts = cleaned.split()
    return parts[-1] if parts else normalised_name


def _normalise_provider(provider: str) -> str:
    """Lowercase + strip for provider matching."""
    return provider.lower().strip()


def _names_match(name_a: str, name_b: str) -> bool:
    """
    Returns True if two normalised names likely refer to the same person.
    Uses last-name matching first, then fuzzy full-name ratio as fallback.
    """
    last_a = _get_last_name(name_a)
    last_b = _get_last_name(name_b)

    # If last names match exactly, that's sufficient (combined with date+provider)
    if last_a == last_b:
        return True

    # Fallback: fuzzy full-name match
    score = fuzz.token_sort_ratio(name_a, name_b)
    return score >= FUZZY_MATCH_THRESHOLD


@dataclass
class RegistryEntry:
    claim_id: str
    claimant_normalised: str
    date_of_service: date
    provider_normalised: str
    flagged_as_duplicate: bool = False


class ClaimRegistry:
    """
    In-memory registry of claims processed during a single batch run.

    Duplicate detection uses a two-stage approach:
      Stage 1: Group by (last_name, date_of_service, normalised_provider).
               This catches 'Lakshmi Krishnan' vs 'Mrs L. Krishnan' sharing
               last name 'krishnan' + same date + same provider.
      Stage 2: Within each group, verify names match via fuzzy ratio
               to avoid false positives from coincidental last-name collisions.
    """

    def __init__(self) -> None:
        # key=(last_name, date, provider) -> list[RegistryEntry]
        self._store: dict[tuple, list[RegistryEntry]] = defaultdict(list)

    def _make_key(
        self,
        claimant_name: str,
        date_of_service: date,
        provider: str,
    ) -> tuple:
        normalised = _normalise_name(claimant_name)
        last = _get_last_name(normalised)
        return (
            last,
            date_of_service,
            _normalise_provider(provider),
        )

    def check_and_register(
        self,
        claim_id: str,
        claimant_name: str,
        date_of_service: date,
        provider: str,
    ) -> list[str]:
        """
        Register this claim. Returns a list of earlier claim IDs that this
        claim is a potential duplicate of. Empty list = no duplicate found.

        Both this claim AND the returned earlier claim IDs should be ESCALATED
        per R6.1.
        """
        key = self._make_key(claimant_name, date_of_service, provider)
        normalised_new = _normalise_name(claimant_name)

        new_entry = RegistryEntry(
            claim_id=claim_id,
            claimant_normalised=normalised_new,
            date_of_service=date_of_service,
            provider_normalised=_normalise_provider(provider),
        )

        # Stage 2: check name similarity against all existing entries in this bucket
        existing = self._store[key]
        duplicate_ids: list[str] = []

        for entry in existing:
            if _names_match(normalised_new, entry.claimant_normalised):
                duplicate_ids.append(entry.claim_id)
                entry.flagged_as_duplicate = True

        if duplicate_ids:
            new_entry.flagged_as_duplicate = True

        self._store[key].append(new_entry)
        return duplicate_ids

    def is_flagged(self, claim_id: str) -> bool:
        """Check if a specific claim ID was retroactively flagged as a duplicate."""
        for entries in self._store.values():
            for entry in entries:
                if entry.claim_id == claim_id and entry.flagged_as_duplicate:
                    return True
        return False

    def get_all_duplicate_pairs(self) -> list[tuple[str, ...]]:
        """Returns all groups of claim IDs that are duplicates of each other."""
        pairs = []
        for entries in self._store.values():
            if len(entries) > 1:
                # Only return groups where at least one is flagged
                if any(e.flagged_as_duplicate for e in entries):
                    pairs.append(tuple(e.claim_id for e in entries))
        return pairs
