"""Calls to the LLM. Every prompt in the project goes through chat()."""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Settings come from the .env at the repo root (two levels up from this file), read once
# at import. Edit .env, then restart the kernel; the values below do not change while running.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# One client for the whole project. The base URL decides which server this talks to:
# OpenAI, a gateway such as Nous Portal or OpenRouter, or a local llama.cpp server.
client = OpenAI(
    api_key=os.getenv("LLM_API_KEY", "local"),  # local servers ignore the key but the SDK requires one
    base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
    timeout=float(os.getenv("LLM_TIMEOUT", "60")),  # seconds per call; no call may hang the notebook
)
MODEL = os.getenv("LLM_MODEL")

# One entry per completed call (a request the server rejects is not logged), so the
# notebook can show how many calls a run made and what they cost.
CALL_LOG = []


# Make one API call and return the reply text. Raises on a reply that was cut off by
# max_tokens (retrying under the same budget cannot help) and on an empty reply.
def _complete(messages, json_mode, max_tokens, temperature, think):
    if not MODEL:
        raise RuntimeError("LLM_MODEL is not set. Copy .env.example to .env and fill it in.")
    options = {}
    if json_mode:
        options["response_format"] = {"type": "json_object"}
    if not think:
        # Reasoning models think by default and those hidden tokens count against max_tokens.
        # This is the switch the gateway honors for DeepSeek; a model that rejects it (GLM does) is not a drop-in.
        options["extra_body"] = {"reasoning": {"enabled": False}}

    started = time.time()
    response = client.chat.completions.create(
        model=MODEL, messages=messages, max_tokens=max_tokens, temperature=temperature, **options
    )
    choice = response.choices[0]
    usage = response.usage  # every backend we use reports it, but a missing count must not fail the call
    CALL_LOG.append({
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
        "seconds": round(time.time() - started, 2),
    })
    if choice.finish_reason == "length":
        raise ValueError(f"Reply truncated at max_tokens={max_tokens}; raise it.")
    text = choice.message.content or ""
    if not text.strip():
        raise ValueError("The model returned an empty reply.")
    return text


# Parse a JSON-mode reply. Only a JSON object satisfies the contract; an array or a
# bare value parses fine but is not a dict, so it is treated the same as bad JSON.
def _parse_object(text):
    result = json.loads(text)
    if not isinstance(result, dict):
        raise json.JSONDecodeError("Reply is valid JSON but not an object", text, 0)
    return result


# Send one prompt and return the reply: text, or a dict when json_mode=True.
# A reply that is not a JSON object is shown back to the model once for correction.
# think=True allows the model's hidden reasoning, for a call where deliberation is
# worth the extra latency and tokens; off everywhere else.
def chat(system, user, json_mode=False, max_tokens=800, temperature=1.0, think=False):
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    text = _complete(messages, json_mode, max_tokens, temperature, think)
    if not json_mode:
        return text
    try:
        return _parse_object(text)
    except json.JSONDecodeError:
        messages.append({"role": "assistant", "content": text})
        messages.append({"role": "user", "content": "That was not a JSON object. Reply with a single JSON object and nothing else."})
        text = _complete(messages, json_mode, max_tokens, temperature, think)
        return _parse_object(text)  # a second failure raises to the caller
