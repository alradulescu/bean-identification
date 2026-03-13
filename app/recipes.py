"""
Pour-over recipe generation and feedback-based adjustment.

Recipes target a standard V60 (or similar) pour-over setup.
All weights are in grams, temperatures in °C, times in seconds.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Constants / look-up tables
# ---------------------------------------------------------------------------

_ROAST_PROFILES = {
    "light": {
        "water_temp": 95,
        "ratio": 16,          # 1 g coffee : 16 g water
        "bloom_water_g": 50,
        "bloom_time_s": 45,
        "total_time_s": 210,  # ~3:30
        "grind_clicks": 26,   # Comandante C40 equivalent
        "grind_label": "fine-medium",
    },
    "medium-light": {
        "water_temp": 94,
        "ratio": 16,
        "bloom_water_g": 45,
        "bloom_time_s": 40,
        "total_time_s": 210,
        "grind_clicks": 28,
        "grind_label": "medium-fine",
    },
    "medium": {
        "water_temp": 93,
        "ratio": 15,
        "bloom_water_g": 45,
        "bloom_time_s": 35,
        "total_time_s": 195,  # ~3:15
        "grind_clicks": 30,
        "grind_label": "medium",
    },
    "medium-dark": {
        "water_temp": 91,
        "ratio": 15,
        "bloom_water_g": 40,
        "bloom_time_s": 30,
        "total_time_s": 180,  # ~3:00
        "grind_clicks": 32,
        "grind_label": "medium-coarse",
    },
    "dark": {
        "water_temp": 89,
        "ratio": 14,
        "bloom_water_g": 40,
        "bloom_time_s": 30,
        "total_time_s": 165,  # ~2:45
        "grind_clicks": 34,
        "grind_label": "coarse",
    },
}

# Origin → slight ratio/temp adjustments
_ORIGIN_ADJUSTMENTS = {
    # African origins: bright, fruity → keep temp high, ratio slightly higher
    "ethiopia": {"water_temp": +1, "ratio": +0.5},
    "kenya": {"water_temp": +1, "ratio": +0.5},
    "rwanda": {"water_temp": +1, "ratio": 0},
    "burundi": {"water_temp": +1, "ratio": 0},
    # South American: nutty, balanced → standard
    "colombia": {"water_temp": 0, "ratio": 0},
    "brazil": {"water_temp": -1, "ratio": -0.5},
    "peru": {"water_temp": 0, "ratio": 0},
    # Central American: clean, bright
    "guatemala": {"water_temp": +1, "ratio": 0},
    "honduras": {"water_temp": 0, "ratio": 0},
    "costa rica": {"water_temp": +1, "ratio": 0},
    # Asian
    "indonesia": {"water_temp": -1, "ratio": -0.5},
    "sumatra": {"water_temp": -1, "ratio": -0.5},
    "yemen": {"water_temp": 0, "ratio": 0},
}


def _normalise_roast(roast_level: str | None) -> str:
    if not roast_level:
        return "medium"
    rl = roast_level.lower().strip()
    for key in _ROAST_PROFILES:
        if rl == key or rl.replace(" ", "-") == key:
            return key
    if "light" in rl:
        return "light" if "medium" not in rl else "medium-light"
    if "dark" in rl:
        return "dark" if "medium" not in rl else "medium-dark"
    return "medium"


def _origin_key(origin: str | None) -> str | None:
    if not origin:
        return None
    return origin.lower().strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_recipe(
    coffee_info: dict,
    bean_analysis: dict | None = None,
    coffee_dose_g: float = 15.0,
) -> dict:
    """
    Generate a pour-over recipe from label info and optional bean analysis.

    Parameters
    ----------
    coffee_info:
        Dict returned by ``analysis.analyze_label_image``.
    bean_analysis:
        Dict returned by ``analysis.analyze_bean_image`` (optional).
    coffee_dose_g:
        Amount of coffee in grams (default 15 g).

    Returns
    -------
    dict with keys: coffee_g, water_g, water_temp_c, ratio, bloom_water_g,
    bloom_time_s, total_time_s, grind_clicks, grind_label, pour_schedule,
    notes.
    """
    roast_key = _normalise_roast(coffee_info.get("roast_level"))
    profile = dict(_ROAST_PROFILES[roast_key])

    # Apply origin adjustments
    origin_key = _origin_key(coffee_info.get("origin"))
    for known_origin, adj in _ORIGIN_ADJUSTMENTS.items():
        if origin_key and known_origin in origin_key:
            profile["water_temp"] = round(profile["water_temp"] + adj["water_temp"])
            profile["ratio"] = profile["ratio"] + adj["ratio"]
            break

    # MASL adjustment: higher altitude → denser beans → slightly finer / higher temp
    masl = coffee_info.get("masl")
    if masl and isinstance(masl, (int, float)):
        if masl > 2000:
            profile["water_temp"] = min(profile["water_temp"] + 1, 98)
            profile["grind_clicks"] = max(profile["grind_clicks"] - 1, 18)
        elif masl > 1500:
            pass  # baseline
        else:
            profile["grind_clicks"] = profile["grind_clicks"] + 1

    # Bean density adjustment from visual analysis
    if bean_analysis:
        density = (bean_analysis.get("bean_density_estimate") or "").lower()
        if density == "dense":
            profile["water_temp"] = min(profile["water_temp"] + 1, 98)
        elif density == "light":
            profile["water_temp"] = max(profile["water_temp"] - 1, 85)

    # Fines adjustment from ground analysis (if provided in bean_analysis)
    if bean_analysis:
        fines_str = (bean_analysis.get("fines_percentage") or "").replace("%", "")
        try:
            fines_pct = float(fines_str)
            if fines_pct > 20:
                # High fines → risk of over-extraction → coarsen slightly
                profile["grind_clicks"] += 2
            elif fines_pct < 5:
                # Very few fines → slightly finer
                profile["grind_clicks"] -= 1
        except ValueError:
            pass

    water_g = round(coffee_dose_g * profile["ratio"])
    remaining_water_g = water_g - profile["bloom_water_g"]

    # Simple 3-pour schedule: bloom + 2 even pours
    pour1_g = round(remaining_water_g * 0.55)
    pour2_g = remaining_water_g - pour1_g

    bloom_end_s = profile["bloom_time_s"]
    pour1_start_s = bloom_end_s
    pour1_end_s = bloom_end_s + 30
    pour2_start_s = pour1_end_s + 20
    pour2_end_s = pour2_start_s + 30

    pour_schedule = [
        {
            "step": 1,
            "action": "Bloom pour",
            "water_g": profile["bloom_water_g"],
            "start_s": 0,
            "end_s": 10,
            "notes": f"Pour {profile['bloom_water_g']} g, wait {profile['bloom_time_s']} s",
        },
        {
            "step": 2,
            "action": "Second pour",
            "water_g": pour1_g,
            "start_s": pour1_start_s,
            "end_s": pour1_end_s,
            "notes": f"Pour to {profile['bloom_water_g'] + pour1_g} g total",
        },
        {
            "step": 3,
            "action": "Final pour",
            "water_g": pour2_g,
            "start_s": pour2_start_s,
            "end_s": pour2_end_s,
            "notes": f"Pour to {water_g} g total",
        },
    ]

    notes_parts = [f"Roast: {roast_key}"]
    if coffee_info.get("origin"):
        notes_parts.append(f"Origin: {coffee_info['origin']}")
    if masl:
        notes_parts.append(f"MASL: {masl}")
    if coffee_info.get("process"):
        notes_parts.append(f"Process: {coffee_info['process']}")

    return {
        "coffee_g": coffee_dose_g,
        "water_g": water_g,
        "water_temp_c": profile["water_temp"],
        "ratio": f"1:{profile['ratio']}",
        "bloom_water_g": profile["bloom_water_g"],
        "bloom_time_s": profile["bloom_time_s"],
        "total_time_s": profile["total_time_s"],
        "grind_clicks": profile["grind_clicks"],
        "grind_label": profile["grind_label"],
        "pour_schedule": pour_schedule,
        "notes": " | ".join(notes_parts),
    }


def adjust_recipe_from_feedback(original_recipe: dict, feedback: dict) -> dict:
    """
    Adjust a recipe based on taste feedback.

    Parameters
    ----------
    original_recipe:
        The recipe dict previously generated by ``generate_recipe``.
    feedback:
        Dict with optional keys: acidity (1-5), sweetness (1-5),
        bitterness (1-5), body (1-5), overall (1-5),
        extraction ('under' | 'over' | 'balanced').

    Returns
    -------
    Adjusted recipe dict with an added 'adjustments_made' key.
    """
    import copy

    recipe = copy.deepcopy(original_recipe)
    adjustments: list[str] = []

    extraction = (feedback.get("extraction") or "balanced").lower()
    bitterness = feedback.get("bitterness") if feedback.get("bitterness") is not None else 3
    acidity = feedback.get("acidity") if feedback.get("acidity") is not None else 3

    if extraction == "under" or bitterness < 2 or acidity > 4:
        # Under-extracted: sour, lack of sweetness → finer grind, higher temp
        recipe["grind_clicks"] = max(recipe.get("grind_clicks", 30) - 2, 18)
        recipe["water_temp_c"] = min(recipe.get("water_temp_c", 93) + 1, 98)
        recipe["total_time_s"] = recipe.get("total_time_s", 195) + 15
        adjustments.append("Finer grind, higher temp, longer brew (under-extraction)")
    elif extraction == "over" or bitterness > 4:
        # Over-extracted: bitter, harsh → coarser grind, lower temp
        recipe["grind_clicks"] = min(recipe.get("grind_clicks", 30) + 2, 40)
        recipe["water_temp_c"] = max(recipe.get("water_temp_c", 93) - 1, 85)
        recipe["total_time_s"] = recipe.get("total_time_s", 195) - 15
        adjustments.append("Coarser grind, lower temp, shorter brew (over-extraction)")

    body = feedback.get("body") if feedback.get("body") is not None else 3
    if body < 2:
        # Thin body → increase dose slightly
        recipe["coffee_g"] = round(recipe.get("coffee_g", 15) + 1, 1)
        new_water = round(recipe["coffee_g"] * float(recipe.get("ratio", "1:15").split(":")[1]))
        recipe["water_g"] = new_water
        adjustments.append("Increased coffee dose for more body")
    elif body > 4:
        # Heavy body → reduce dose
        recipe["coffee_g"] = round(recipe.get("coffee_g", 15) - 1, 1)
        new_water = round(recipe["coffee_g"] * float(recipe.get("ratio", "1:15").split(":")[1]))
        recipe["water_g"] = new_water
        adjustments.append("Reduced coffee dose for lighter body")

    sweetness = feedback.get("sweetness") if feedback.get("sweetness") is not None else 3
    if sweetness < 2:
        # Lacking sweetness → slightly finer or more bloom
        recipe["bloom_time_s"] = min(recipe.get("bloom_time_s", 35) + 10, 60)
        adjustments.append("Extended bloom for more sweetness")

    recipe["adjustments_made"] = adjustments if adjustments else ["No adjustments needed"]
    return recipe
