"""
llm_client.py
-------------
A utility to return an LLM instance with API key rotation to handle rate limits.
"""

import os
from itertools import cycle

from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "gemini-3.6-flash"

# Load available API keys
keys = []
key1 = os.getenv("GOOGLE_API_KEY")
if key1:
    keys.append(key1)

key2 = os.getenv("GOOGLE_API_KEY_2")
if key2:
    keys.append(key2)

if not keys:
    raise ValueError("No GOOGLE_API_KEY found in environment.")

# Create an infinite cycle iterator over the available keys
_key_cycle = cycle(keys)

def get_llm() -> ChatGoogleGenerativeAI:
    """Returns a ChatGoogleGenerativeAI instance using the next key in rotation."""
    next_key = next(_key_cycle)
    return ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        google_api_key=next_key,
        temperature=0,
        max_retries=3,
    )
