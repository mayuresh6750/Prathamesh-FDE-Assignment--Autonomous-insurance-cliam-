"""
llm_client.py
-------------
A utility to return an LLM instance backed by Groq.

Model: openai/gpt-oss-120b
  - 120B parameter model on Groq's free tier with a high RPD limit.
  - Does not have a "thinking" mode that conflicts with json_mode (unlike qwen3).
  - groq/compound was avoided: only 250 RPD, burns quota via internal sub-calls.
  - qwen/qwen3.6-27b was avoided: thinking mode conflicts with json_mode → 400 errors.
  - Our prompts embed the explicit JSON schema so field names are always correct.
"""

import os

from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "openai/gpt-oss-120b"


def get_llm() -> ChatGroq:
    """Returns a ChatGroq instance using the GROQ_API_KEY from .env."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("No GROQ_API_KEY found in .env file.")

    return ChatGroq(
        model=MODEL_NAME,
        groq_api_key=api_key,
        temperature=0,
        max_retries=5,
    )
