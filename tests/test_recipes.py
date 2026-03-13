"""Tests for the recipe generation and adjustment logic."""

import pytest

from app.recipes import adjust_recipe_from_feedback, generate_recipe


# ---------------------------------------------------------------------------
# generate_recipe
# ---------------------------------------------------------------------------

class TestGenerateRecipe:
    def _minimal_info(self, roast_level="medium", origin=None, masl=None, process=None):
        return {
            "origin": origin,
            "species": "Arabica",
            "masl": masl,
            "roast_level": roast_level,
            "process": process,
        }

    def test_returns_required_keys(self):
        recipe = generate_recipe(self._minimal_info())
        required = [
            "coffee_g", "water_g", "water_temp_c", "ratio",
            "bloom_water_g", "bloom_time_s", "total_time_s",
            "grind_clicks", "grind_label", "pour_schedule", "notes",
        ]
        for key in required:
            assert key in recipe, f"Missing key: {key}"

    def test_water_g_respects_ratio(self):
        recipe = generate_recipe(self._minimal_info("medium"), coffee_dose_g=15)
        # medium roast has ratio 15, so 15*15 = 225
        assert recipe["water_g"] == 225

    def test_light_roast_is_hotter_than_dark(self):
        light = generate_recipe(self._minimal_info("light"))
        dark = generate_recipe(self._minimal_info("dark"))
        assert light["water_temp_c"] > dark["water_temp_c"]

    def test_light_roast_finer_grind_than_dark(self):
        light = generate_recipe(self._minimal_info("light"))
        dark = generate_recipe(self._minimal_info("dark"))
        assert light["grind_clicks"] < dark["grind_clicks"]

    def test_pour_schedule_has_three_steps(self):
        recipe = generate_recipe(self._minimal_info())
        assert len(recipe["pour_schedule"]) == 3

    def test_pour_schedule_water_sums_to_total(self):
        recipe = generate_recipe(self._minimal_info(), coffee_dose_g=15)
        total = sum(step["water_g"] for step in recipe["pour_schedule"])
        assert total == recipe["water_g"]

    def test_african_origin_increases_temp(self):
        base = generate_recipe(self._minimal_info("medium", origin=None))
        ethiopia = generate_recipe(self._minimal_info("medium", origin="Ethiopia"))
        # Ethiopia adjustment: +1 temp
        assert ethiopia["water_temp_c"] >= base["water_temp_c"]

    def test_high_masl_increases_temp(self):
        low = generate_recipe(self._minimal_info("medium", masl=800))
        high = generate_recipe(self._minimal_info("medium", masl=2200))
        assert high["water_temp_c"] >= low["water_temp_c"]

    def test_normalise_roast_handles_none(self):
        recipe = generate_recipe(self._minimal_info(roast_level=None))
        assert recipe is not None
        assert "water_temp_c" in recipe

    def test_normalise_roast_handles_unusual_strings(self):
        recipe = generate_recipe(self._minimal_info(roast_level="Very Dark"))
        assert recipe["water_temp_c"] <= 92  # should map to dark profile

    def test_bean_density_dense_increases_temp(self):
        base = generate_recipe(self._minimal_info())
        dense = generate_recipe(
            self._minimal_info(),
            bean_analysis={"bean_density_estimate": "dense"},
        )
        assert dense["water_temp_c"] >= base["water_temp_c"]

    def test_high_fines_coarsens_grind(self):
        base = generate_recipe(self._minimal_info())
        fines = generate_recipe(
            self._minimal_info(),
            bean_analysis={"fines_percentage": "25%"},
        )
        assert fines["grind_clicks"] > base["grind_clicks"]

    def test_custom_dose_affects_water(self):
        recipe = generate_recipe(self._minimal_info("medium"), coffee_dose_g=20)
        # ratio 15 → water = 20 * 15 = 300
        assert recipe["water_g"] == 300
        assert recipe["coffee_g"] == 20


# ---------------------------------------------------------------------------
# adjust_recipe_from_feedback
# ---------------------------------------------------------------------------

class TestAdjustRecipeFromFeedback:
    def _base_recipe(self):
        return generate_recipe(
            {"origin": "Colombia", "species": "Arabica", "masl": 1600,
             "roast_level": "medium", "process": "washed"}
        )

    def test_returns_dict_with_adjustments_key(self):
        result = adjust_recipe_from_feedback(self._base_recipe(), {})
        assert "adjustments_made" in result

    def test_over_extraction_coarsens_and_cools(self):
        base = self._base_recipe()
        adjusted = adjust_recipe_from_feedback(
            base, {"extraction": "over", "bitterness": 5}
        )
        assert adjusted["grind_clicks"] > base["grind_clicks"]
        assert adjusted["water_temp_c"] < base["water_temp_c"]

    def test_under_extraction_fines_and_heats(self):
        base = self._base_recipe()
        adjusted = adjust_recipe_from_feedback(
            base, {"extraction": "under", "bitterness": 1}
        )
        assert adjusted["grind_clicks"] < base["grind_clicks"]
        assert adjusted["water_temp_c"] > base["water_temp_c"]

    def test_thin_body_increases_dose(self):
        base = self._base_recipe()
        adjusted = adjust_recipe_from_feedback(base, {"body": 1})
        assert adjusted["coffee_g"] > base["coffee_g"]

    def test_heavy_body_reduces_dose(self):
        base = self._base_recipe()
        adjusted = adjust_recipe_from_feedback(base, {"body": 5})
        assert adjusted["coffee_g"] < base["coffee_g"]

    def test_low_sweetness_extends_bloom(self):
        base = self._base_recipe()
        adjusted = adjust_recipe_from_feedback(base, {"sweetness": 1})
        assert adjusted["bloom_time_s"] > base["bloom_time_s"]

    def test_balanced_feedback_no_changes(self):
        base = self._base_recipe()
        adjusted = adjust_recipe_from_feedback(
            base,
            {"extraction": "balanced", "bitterness": 3, "acidity": 3,
             "body": 3, "sweetness": 3, "overall": 3},
        )
        assert adjusted["adjustments_made"] == ["No adjustments needed"]
