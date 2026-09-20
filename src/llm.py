"""One door to the LLM. Every prompt in the project goes through chat()."""

import json
import os
import re
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # copies the key=value lines of .env into os.environ, once, at import

# One client for the whole process. The base URL decides whether this talks to
# OpenAI, OpenRouter, or a local server; nothing else in the project changes.
_client = None

# Every call appends one entry here. The notebook uses it to show how many calls
# a run made and how long they took, which is the cost and timing evidence.
CALL_LOG = []


# Build the client on first use so importing this module never needs a key.
def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("LLM_API_KEY", "local"),  # local servers ignore the key but the SDK requires one
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            timeout=float(os.getenv("LLM_TIMEOUT", "60")),  # seconds per call; no call may hang the notebook
            max_retries=2,  # transport errors only; JSON retries are handled below
        )
    return _client


# Some models wrap JSON in ```json fences even when told not to. Take what is inside.
def _strip_fences(text):
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return match.group(1) if match else text


# Send one prompt and return the reply. With json_mode=True the reply is parsed
# into a dict; a reply that is not valid JSON is sent back once for correction,
# then the call raises so the caller never receives a half-parsed string.
def chat(system, user, json_mode=False, max_tokens=800, temperature=0.2):
    model = os.getenv("LLM_MODEL")
    if not model:
        raise RuntimeError("LLM_MODEL is not set. Copy .env.example to .env and fill it in.")

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    extra = {"response_format": {"type": "json_object"}} if json_mode else {}
    attempts = 2 if json_mode else 1

    for attempt in range(1, attempts + 1):
        started = time.time()
        response = _get_client().chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **extra,
        )
        text = response.choices[0].message.content or ""
        usage = response.usage
        CALL_LOG.append({
            "model": model,
            "json_mode": json_mode,
            "attempt": attempt,
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "seconds": round(time.time() - started, 2),
        })

        if not json_mode:
            return text
        try:
            return json.loads(_strip_fences(text))
        except json.JSONDecodeError as err:
            if attempt == attempts:
                raise ValueError(f"LLM returned invalid JSON after {attempts} attempts: {text[:200]!r}") from err
            # Give the model its own reply back and ask again, once.
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": "That was not valid JSON. Reply with a single JSON object and nothing else."})
