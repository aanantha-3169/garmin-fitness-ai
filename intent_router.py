"""
intent_router.py — Lightweight Gemini-based NLP intent classifier.

Classifies incoming free-text Telegram messages into one of six intents
before any downstream handler processes them, preventing meal descriptions
from being parsed when the user is actually reporting an injury or asking
a question.

Intents:
  MEAL          — food/drink description to be macro-analysed
  METRIC        — a numeric self-reported metric (weight, soreness, sleep hrs)
  SUBJECTIVE    — qualitative feeling, injury note, fatigue observation
  QUERY         — a question directed at the bot
  FEAR          — water or race fear expression
  TRAINING_LOG  — athlete reporting a completed session

Usage:
    from intent_router import classify_intent
    result = await classify_intent("My knee is sore after yesterday's run")
    # {"intent": "SUBJECTIVE", "confidence": 0.97, "extracted_value": None}
"""

import json
import logging
import os
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
logger = logging.getLogger(__name__)

_ROUTER_MODEL = "gemini-3-flash-preview"

_SYSTEM_PROMPT = """\
You are a message intent classifier for a fitness AI bot.

Classify the user's message into EXACTLY ONE of these intents:

  MEAL       — describes food or drink they consumed or plan to eat
               e.g. "2 eggs and toast", "I had a chicken salad", "nasi goreng"

  METRIC     — a self-reported numeric body metric
               e.g. "I weigh 82kg", "soreness level 7/10", "slept 6 hours"

  SUBJECTIVE — a qualitative feeling, injury, fatigue, or mood note
               e.g. "my hamstring is tight", "feeling exhausted today",
               "lower back pain since yesterday", "mentally drained"

  QUERY      — a direct question to the bot
               e.g. "how many calories do I have left?", "what should I eat?",
               "did I hit my protein goal?"

  FEAR       — expresses water, open-water, or race fear/anxiety
               e.g. "felt okay in the pool today", "panicked at the wall",
               "water fear was 3/10 this morning", "still scared of open water",
               "not sure I can handle the swim leg"

  TRAINING_LOG — athlete reporting a completed training session with data
               e.g. "did 750m in 16 minutes", "45 min bike avg HR 138",
               "ran 8km at 6:30 pace", "finished the brick — 60 min bike then 20 min run"

Return ONLY valid JSON with these fields:
  intent          : one of MEAL | METRIC | SUBJECTIVE | QUERY | FEAR | TRAINING_LOG
  confidence      : float 0.0–1.0
  extracted_value : for METRIC, a dict {"type": str, "value": float/str};
                    for TRAINING_LOG, a dict {"sport": str, "duration_min": float/null,
                    "distance": str/null, "avg_hr": float/null};
                    for all others, null

Examples:
  "rice and grilled fish"
  → {"intent":"MEAL","confidence":0.98,"extracted_value":null}

  "I weigh 83.5 kg this morning"
  → {"intent":"METRIC","confidence":0.96,"extracted_value":{"type":"weight_kg","value":83.5}}

  "hamstring feels really tight today"
  → {"intent":"SUBJECTIVE","confidence":0.95,"extracted_value":null}

  "how many calories left today?"
  → {"intent":"QUERY","confidence":0.97,"extracted_value":null}

  "water fear was 3/10 this morning"
  → {"intent":"FEAR","confidence":0.97,"extracted_value":null}

  "panicked at the wall again"
  → {"intent":"FEAR","confidence":0.94,"extracted_value":null}

  "did 750m in 16 minutes"
  → {"intent":"TRAINING_LOG","confidence":0.97,"extracted_value":{"sport":"swim","duration_min":16,"distance":"750m","avg_hr":null}}

  "45 min bike avg HR 138"
  → {"intent":"TRAINING_LOG","confidence":0.96,"extracted_value":{"sport":"bike","duration_min":45,"distance":null,"avg_hr":138}}
"""

_FALLBACK = {"intent": "MEAL", "confidence": 0.0, "extracted_value": None}


async def classify_intent(text: str) -> dict:
    """Classify a user message and return an intent dict.

    Falls back to MEAL with confidence 0.0 on any error so the existing
    meal-logging path is never blocked by a router failure.

    Args:
        text: Raw message text from the Telegram user.

    Returns:
        dict with keys: intent (str), confidence (float), extracted_value (any).
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set — defaulting to MEAL intent.")
        return _FALLBACK

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=_ROUTER_MODEL,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        raw = response.text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        result = json.loads(raw)

        # Validate required fields
        if result.get("intent") not in ("MEAL", "METRIC", "SUBJECTIVE", "QUERY", "FEAR", "TRAINING_LOG"):
            logger.warning("Router returned unknown intent '%s' — falling back to MEAL.", result.get("intent"))
            return _FALLBACK

        logger.info(
            "Intent: %s (%.2f) — '%s'",
            result["intent"], result.get("confidence", 0), text[:60]
        )
        return result

    except Exception as exc:
        logger.error("Intent classification failed: %s — defaulting to MEAL.", exc)
        return _FALLBACK
