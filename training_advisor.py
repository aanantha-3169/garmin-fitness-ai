"""
training_advisor.py — Gemini-powered training readiness analysis.

Takes Garmin health metrics (from garmin_metrics.get_health_metrics) and
a planned workout description, then returns a structured TrainingDecision
via the Gemini API with enforced JSON schema output.

Usage:
    from garmin_metrics import get_health_metrics
    from training_advisor import analyze_readiness

    metrics = get_health_metrics(garmin_client)
    decision = analyze_readiness(metrics, "Lift A: Push & Quads")
    print(decision)
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()
logger = logging.getLogger(__name__)

# ── Pydantic Schema ──────────────────────────────────────────────────────────

class TrainingDecision(BaseModel):
    """Structured output from the Gemini readiness analysis."""

    adjustment_needed: bool = Field(
        description="Whether the planned workout should be modified based on recovery data."
    )
    recommended_action: str = Field(
        description=(
            "Concrete recommendation, e.g. 'Proceed as planned', "
            "'Reduce intensity by 20%', 'Shift workout to tomorrow'."
        )
    )
    target_calories: int = Field(
        description="Calorie target for the day: Garmin total_calories + 250 surplus."
    )
    zone2_target_hr_low: int = Field(
        default=115,
        description="Lower bound of Zone 2 heart rate target (bpm).",
    )
    zone2_target_hr_high: int = Field(
        default=145,
        description="Upper bound of Zone 2 heart rate target (bpm).",
    )
    principle_violations: list[str] = Field(
        default_factory=list,
        description="Principles from PRINCIPLES.md that this recommendation would break, if any.",
    )
    water_fear_note: Optional[str] = Field(
        default=None,
        description="For swim sessions only: note acknowledging any water fear context.",
    )
    philosophical_reflection: Optional[str] = Field(
        default=None,
        description=(
            "A short mindfulness prompt to help the user re-center. "
            "Include only when stress_avg > 40 or HRV status is UNBALANCED."
        ),
    )


# ── Prompt Construction ──────────────────────────────────────────────────────

_PRINCIPLES = Path("docs/PRINCIPLES.md").read_text()
_SPORT_SCIENCE = Path("docs/SPORT_SCIENCE.md").read_text()

_SYSTEM_PROMPT = f"""\
{_PRINCIPLES}

{_SPORT_SCIENCE}

"""  # coach rules appended below

_SYSTEM_PROMPT += """\
You are an elite sports-performance AI coach. You analyze Garmin wearable
data and make evidence-based training decisions.

RULES:
1. Consider sleep_score, HRV status, body_battery, resting heart rate,
   stress, and calories holistically — no single metric is decisive.
2. CALORIE LOGIC:
   • Base Surplus = 250 kcal.
   • IF recommended_action is "Shift to tomorrow" or suggests skipping training:
     target_calories = calories_resting + Base Surplus.
   • IF recommended_action is "Proceed as planned" or reduced intensity training:
     target_calories = calories_resting + calories_active + Base Surplus.
   • If 'calories_resting' is missing, assume 2000 kcal.
3. ADAPTIVE RECOMMENDATION:
   • Set `adjustment_needed` = true if TWO OR MORE of these are true:
     - sleep_score < 60
     - HRV status is LOW or UNBALANCED
     - body_battery_current < 30 (CRITICAL: if it dropped > 15 pts since morning, pivot to rest)
     - stress_avg > 50
     - resting_heart_rate is elevated (> 10% above typical)
4. Be specific:
   good: "Proceed as planned", "Reduce volume by 25%", "Shift to tomorrow — priority is Naps & Hydration"
   bad: "Normal training", "Take a rest"
5. Include `philosophical_reflection` ONLY when stress_avg > 40 OR
   HRV status is UNBALANCED. Make it 1-2 sentences, grounded and practical.
"""


def _build_user_prompt(
    garmin_data: dict,
    planned_workout: str,
    execution_context: str = "",
    subjective_notes: str = "",
) -> str:
    """Build the user-turn prompt with embedded metrics, workout plan, and
    optional yesterday's execution telemetry and subjective notes."""
    prompt = (
        f"## Today's Garmin Metrics\n"
        f"```json\n{json.dumps(garmin_data, indent=2)}\n```\n\n"
        f"## Planned Workout\n{planned_workout}\n\n"
    )
    if execution_context:
        prompt += f"## Yesterday's Execution\n{execution_context}\n\n"
    if subjective_notes:
        prompt += f"## Recent Athlete Notes\n{subjective_notes}\n\n"
    prompt += "Analyze my readiness and return a TrainingDecision."
    return prompt


# ── Public API ───────────────────────────────────────────────────────────────

def analyze_readiness(
    garmin_json_data: dict,
    planned_workout_string: str,
    model: str = "gemini-3-flash-preview",
    execution_context: str = "",
    subjective_notes: str = "",
) -> TrainingDecision:
    """Analyze training readiness using Gemini with structured output.

    Args:
        garmin_json_data: Output of ``get_health_metrics()`` (dict).
        planned_workout_string: Free-text description of the planned session.
        model: Gemini model identifier.

    Returns:
        A validated ``TrainingDecision`` Pydantic object.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found. Add it to your .env file."
        )

    client = genai.Client(api_key=api_key)

    user_prompt = _build_user_prompt(
        garmin_json_data,
        planned_workout_string,
        execution_context=execution_context,
        subjective_notes=subjective_notes,
    )

    logger.info("Calling Gemini (%s) for readiness analysis …", model)

    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=TrainingDecision,
            temperature=0.3,
        ),
    )

    # Parse the JSON response into the Pydantic model
    raw_json = response.text
    decision = TrainingDecision.model_validate_json(raw_json)

    logger.info(
        "Decision: adjustment_needed=%s, action='%s'",
        decision.adjustment_needed,
        decision.recommended_action,
    )

    return decision
