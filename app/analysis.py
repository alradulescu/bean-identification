"""
Image analysis module using OpenAI Vision API.

When OPENAI_API_KEY is not set or analysis fails, functions return
structured placeholder data so the app remains functional in demo/dev mode.
"""

import base64
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _encode_image(image_path: str) -> str:
    """Return a base64-encoded string of the image at *image_path*."""
    with open(image_path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("utf-8")


def _call_openai(api_key: str, prompt: str, image_path: str) -> str:
    """
    Send an image + prompt to GPT-4o and return the raw text response.

    Raises RuntimeError on failure so callers can fall back gracefully.
    """
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        b64 = _encode_image(image_path)
        suffix = Path(image_path).suffix.lower().lstrip(".")
        mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=800,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"OpenAI call failed: {exc}") from exc


def _parse_json_block(text: str) -> dict:
    """
    Extract and parse the first JSON object found in *text*.

    Falls back to an empty dict if parsing fails.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


# ---------------------------------------------------------------------------
# Public analysis functions
# ---------------------------------------------------------------------------

def analyze_label_image(image_path: str, api_key: str = "") -> dict:
    """
    Analyse a coffee bag label image and return structured information.

    Returns a dict with keys: origin, species, masl, roast_level,
    roast_date, tasting_notes, producer, process.
    """
    prompt = (
        "You are a coffee expert analysing a coffee bag label image. "
        "Extract the following information and return ONLY a JSON object "
        "(no markdown, no extra text) with these exact keys:\n"
        "- origin (country/region of origin)\n"
        "- species (e.g. Arabica, Robusta, or specific varietal)\n"
        "- masl (altitude in metres above sea level, integer or null)\n"
        "- roast_level (light / medium-light / medium / medium-dark / dark)\n"
        "- roast_date (date string as shown on bag, or null)\n"
        "- tasting_notes (comma-separated flavour descriptors)\n"
        "- producer (farm / producer name, or null)\n"
        "- process (washed / natural / honey / anaerobic / other)\n"
        "Use null for any field that cannot be determined from the image."
    )

    default = {
        "origin": None,
        "species": "Arabica",
        "masl": None,
        "roast_level": "medium",
        "roast_date": None,
        "tasting_notes": None,
        "producer": None,
        "process": None,
    }

    if not api_key:
        logger.warning("No OpenAI API key – returning default label data.")
        return default

    try:
        raw = _call_openai(api_key, prompt, image_path)
        data = _parse_json_block(raw)
        # Merge: keep defaults for keys missing from API response
        result = {**default, **{k: v for k, v in data.items() if k in default}}
        # Coerce MASL to int
        if result["masl"] is not None:
            try:
                result["masl"] = int(str(result["masl"]).replace(",", ""))
            except (ValueError, TypeError):
                result["masl"] = None
        return result
    except RuntimeError as exc:
        logger.error("Label analysis failed: %s", exc)
        return default


def analyze_bean_image(image_path: str, api_key: str = "") -> dict:
    """
    Analyse a photo of coffee beans (ideally on a white/A4 background) and
    return visual characteristics used for recipe fine-tuning.

    Returns a dict with keys: bean_color, bean_size, bean_uniformity,
    bean_density_estimate, analysis_notes.
    """
    prompt = (
        "You are a coffee expert analysing an image of coffee beans, "
        "ideally placed on a white or A4 paper background for scale. "
        "Assess the beans visually and return ONLY a JSON object "
        "(no markdown, no extra text) with these exact keys:\n"
        "- bean_color (e.g. light-tan / cinnamon / medium-brown / dark-brown / black)\n"
        "- bean_size (small / medium / large)\n"
        "- bean_uniformity (uniform / slightly-varied / varied)\n"
        "- bean_density_estimate (dense / medium / light — infer from size/colour)\n"
        "- analysis_notes (brief free-text observations, max 80 words)\n"
        "Use null for any field you cannot determine."
    )

    default = {
        "bean_color": "medium-brown",
        "bean_size": "medium",
        "bean_uniformity": "uniform",
        "bean_density_estimate": "medium",
        "analysis_notes": "Analysis not available – no API key provided.",
    }

    if not api_key:
        logger.warning("No OpenAI API key – returning default bean data.")
        return default

    try:
        raw = _call_openai(api_key, prompt, image_path)
        data = _parse_json_block(raw)
        return {**default, **{k: v for k, v in data.items() if k in default}}
    except RuntimeError as exc:
        logger.error("Bean analysis failed: %s", exc)
        return default


def analyze_ground_coffee_image(image_path: str, api_key: str = "") -> dict:
    """
    Analyse a photo of ground coffee to estimate particle size distribution
    and fines content.

    Returns a dict with keys: particle_size_distribution, fines_percentage,
    grind_uniformity, analysis_notes.
    """
    prompt = (
        "You are a coffee expert analysing a close-up image of ground coffee. "
        "Assess the grind visually and return ONLY a JSON object "
        "(no markdown, no extra text) with these exact keys:\n"
        "- particle_size_distribution (fine / medium-fine / medium / "
        "medium-coarse / coarse)\n"
        "- fines_percentage (estimated percentage of visible fines as a string, "
        "e.g. '5%', '15%', or 'unknown')\n"
        "- grind_uniformity (uniform / slightly-varied / bimodal / varied)\n"
        "- analysis_notes (brief free-text, max 80 words)\n"
        "Use null for any field you cannot determine."
    )

    default = {
        "particle_size_distribution": "medium",
        "fines_percentage": "unknown",
        "grind_uniformity": "uniform",
        "analysis_notes": "Analysis not available – no API key provided.",
    }

    if not api_key:
        logger.warning("No OpenAI API key – returning default ground data.")
        return default

    try:
        raw = _call_openai(api_key, prompt, image_path)
        data = _parse_json_block(raw)
        return {**default, **{k: v for k, v in data.items() if k in default}}
    except RuntimeError as exc:
        logger.error("Ground coffee analysis failed: %s", exc)
        return default
