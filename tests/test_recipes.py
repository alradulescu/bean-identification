"""Tests for the recipe generation and adjustment logic."""

import pytest

from app.recipes import (
    _compute_grinder_settings,
    adjust_recipe_from_feedback,
    generate_recipe,
)


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


# ---------------------------------------------------------------------------
# Multi-grinder settings
# ---------------------------------------------------------------------------

class TestGrinderSettings:
    def _minimal_info(self, roast_level="medium", decaf_status=None):
        return {
            "origin": None,
            "species": "Arabica",
            "masl": None,
            "roast_level": roast_level,
            "process": None,
            "decaf_status": decaf_status,
        }

    def test_recipe_includes_grinder_settings(self):
        recipe = generate_recipe(self._minimal_info())
        assert "grinder_settings" in recipe
        assert isinstance(recipe["grinder_settings"], dict)

    def test_all_supported_grinders_present(self):
        recipe = generate_recipe(self._minimal_info())
        expected_grinders = {
            "Comandante C40",
            "1Zpresso ZP6",
            "KinGrinder K6",
            "Timemore C3 / S2",
            "Baratza Encore",
            "Fellow Ode Gen 2",
            "Hario Mini Mill Plus",
        }
        assert expected_grinders == set(recipe["grinder_settings"].keys())

    def test_compute_grinder_settings_medium_roast(self):
        settings = _compute_grinder_settings(30)
        # Comandante C40 medium baseline is 30 clicks
        assert settings["Comandante C40"] == "30 clicks"
        # 1Zpresso ZP6 medium baseline is 2.0 rotations
        assert settings["1Zpresso ZP6"] == "2.0 rotations"
        # KinGrinder K6 medium baseline is 4.5 rotations
        assert settings["KinGrinder K6"] == "4.5 rotations"
        # Timemore C3/S2 medium baseline is 15 clicks
        assert settings["Timemore C3 / S2"] == "15 clicks"
        # Baratza Encore medium baseline is 20
        assert settings["Baratza Encore"] == "20 setting"

    def test_coarser_grind_gives_higher_settings_for_all_grinders(self):
        fine_settings = _compute_grinder_settings(26)
        coarse_settings = _compute_grinder_settings(34)
        for grinder in fine_settings:
            fine_val = float(fine_settings[grinder].split()[0])
            coarse_val = float(coarse_settings[grinder].split()[0])
            assert coarse_val > fine_val, (
                f"{grinder}: coarse ({coarse_val}) should be > fine ({fine_val})"
            )

    def test_grinder_settings_change_with_roast(self):
        light = generate_recipe(self._minimal_info("light"))
        dark = generate_recipe(self._minimal_info("dark"))
        light_cmd = float(light["grinder_settings"]["Comandante C40"].split()[0])
        dark_cmd = float(dark["grinder_settings"]["Comandante C40"].split()[0])
        assert dark_cmd > light_cmd

    def test_zpresso_zp6_setting_is_reasonable(self):
        # For any roast, 1Zpresso ZP6 V60 setting should be between 1.5 and 2.8
        for roast in ("light", "medium", "dark"):
            recipe = generate_recipe(self._minimal_info(roast))
            zp6_val = float(recipe["grinder_settings"]["1Zpresso ZP6"].split()[0])
            assert 1.5 <= zp6_val <= 2.8, (
                f"ZP6 setting {zp6_val} out of expected range for {roast} roast"
            )

    def test_kingrinder_k6_setting_is_reasonable(self):
        # For any roast, KinGrinder K6 V60 setting should be between 3.0 and 6.5
        for roast in ("light", "medium", "dark"):
            recipe = generate_recipe(self._minimal_info(roast))
            k6_val = float(recipe["grinder_settings"]["KinGrinder K6"].split()[0])
            assert 3.0 <= k6_val <= 6.5, (
                f"K6 setting {k6_val} out of expected range for {roast} roast"
            )


# ---------------------------------------------------------------------------
# Decaf / half-caf recipe adjustments
# ---------------------------------------------------------------------------

class TestDecafAdjustments:
    def _info(self, roast="medium", decaf_status=None):
        return {
            "origin": None,
            "species": "Arabica",
            "masl": None,
            "roast_level": roast,
            "process": None,
            "decaf_status": decaf_status,
        }

    def test_decaf_lowers_water_temp(self):
        regular = generate_recipe(self._info())
        decaf = generate_recipe(self._info(decaf_status="decaf"))
        assert decaf["water_temp_c"] < regular["water_temp_c"]

    def test_decaf_temp_reduction_is_two_degrees(self):
        regular = generate_recipe(self._info("medium"))
        decaf = generate_recipe(self._info("medium", decaf_status="decaf"))
        assert regular["water_temp_c"] - decaf["water_temp_c"] == 2

    def test_half_caf_lowers_temp_by_one_degree(self):
        regular = generate_recipe(self._info("medium"))
        half_caf = generate_recipe(self._info("medium", decaf_status="half-caf"))
        assert regular["water_temp_c"] - half_caf["water_temp_c"] == 1

    def test_decaf_temp_does_not_go_below_85(self):
        # Repeated decaf + dark + low-altitude should never breach floor
        info = self._info("dark", decaf_status="decaf")
        recipe = generate_recipe(info, bean_analysis={"bean_density_estimate": "light"})
        assert recipe["water_temp_c"] >= 85

    def test_decaf_note_appears_in_recipe_notes(self):
        info = self._info(decaf_status="decaf")
        recipe = generate_recipe(info)
        assert "decaf" in recipe["notes"].lower()

    def test_regular_coffee_no_temp_reduction(self):
        regular = generate_recipe(self._info())
        from app.recipes import _ROAST_PROFILES
        base_temp = _ROAST_PROFILES["medium"]["water_temp"]
        assert regular["water_temp_c"] == base_temp
