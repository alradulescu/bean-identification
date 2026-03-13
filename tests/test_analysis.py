"""Tests for the image analysis module."""

import json
import os
import tempfile

import pytest
from PIL import Image

from app.analysis import (
    _encode_image,
    _extract_from_ocr_text,
    _parse_json_block,
    analyze_bean_image,
    analyze_ground_coffee_image,
    analyze_label_image,
)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _make_test_image(path: str) -> str:
    """Save a tiny JPEG to *path* and return the path."""
    img = Image.new("RGB", (20, 20), color=(200, 150, 100))
    img.save(path, format="JPEG")
    return path


# ---------------------------------------------------------------------------
# _parse_json_block
# ---------------------------------------------------------------------------

class TestParseJsonBlock:
    def test_plain_json(self):
        text = '{"key": "value", "num": 42}'
        result = _parse_json_block(text)
        assert result == {"key": "value", "num": 42}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result:\n{"origin": "Ethiopia"}\nEnd.'
        result = _parse_json_block(text)
        assert result["origin"] == "Ethiopia"

    def test_invalid_json_returns_empty_dict(self):
        result = _parse_json_block("no json here at all")
        assert result == {}

    def test_malformed_json_returns_empty_dict(self):
        result = _parse_json_block("{broken json }")
        assert result == {}


# ---------------------------------------------------------------------------
# _encode_image
# ---------------------------------------------------------------------------

class TestEncodeImage:
    def test_encodes_to_base64_string(self, tmp_path):
        img_path = str(tmp_path / "test.jpg")
        _make_test_image(img_path)
        encoded = _encode_image(img_path)
        assert isinstance(encoded, str)
        assert len(encoded) > 0
        # Verify it's valid base64
        import base64
        decoded = base64.b64decode(encoded)
        assert len(decoded) > 0


# ---------------------------------------------------------------------------
# analyze_label_image (no API key → returns defaults)
# ---------------------------------------------------------------------------

class TestAnalyzeLabelImage:
    def test_returns_default_when_no_api_key(self, tmp_path):
        img_path = str(tmp_path / "label.jpg")
        _make_test_image(img_path)
        result = analyze_label_image(img_path, api_key="")
        assert isinstance(result, dict)
        assert "origin" in result
        assert "species" in result
        assert "masl" in result
        assert "roast_level" in result
        assert "roast_date" in result
        assert "tasting_notes" in result
        assert "producer" in result
        assert "process" in result

    def test_default_species_is_arabica(self, tmp_path):
        img_path = str(tmp_path / "label.jpg")
        _make_test_image(img_path)
        result = analyze_label_image(img_path, api_key="")
        assert result["species"] == "Arabica"

    def test_default_roast_level_is_medium(self, tmp_path):
        img_path = str(tmp_path / "label.jpg")
        _make_test_image(img_path)
        result = analyze_label_image(img_path, api_key="")
        assert result["roast_level"] == "medium"


# ---------------------------------------------------------------------------
# analyze_bean_image (no API key → returns defaults)
# ---------------------------------------------------------------------------

class TestAnalyzeBeanImage:
    def test_returns_default_when_no_api_key(self, tmp_path):
        img_path = str(tmp_path / "beans.jpg")
        _make_test_image(img_path)
        result = analyze_bean_image(img_path, api_key="")
        assert isinstance(result, dict)
        assert "bean_color" in result
        assert "bean_size" in result
        assert "bean_uniformity" in result
        assert "bean_density_estimate" in result
        assert "analysis_notes" in result

    def test_bean_color_is_valid_value(self, tmp_path):
        img_path = str(tmp_path / "beans.jpg")
        _make_test_image(img_path)
        result = analyze_bean_image(img_path, api_key="")
        valid_colors = {"light-tan", "cinnamon", "medium-brown", "dark-brown", "black"}
        assert result["bean_color"] in valid_colors


# ---------------------------------------------------------------------------
# analyze_ground_coffee_image (no API key → returns defaults)
# ---------------------------------------------------------------------------

class TestAnalyzeGroundCoffeeImage:
    def test_returns_default_when_no_api_key(self, tmp_path):
        img_path = str(tmp_path / "grounds.jpg")
        _make_test_image(img_path)
        result = analyze_ground_coffee_image(img_path, api_key="")
        assert isinstance(result, dict)
        assert "particle_size_distribution" in result
        assert "fines_percentage" in result
        assert "grind_uniformity" in result
        assert "analysis_notes" in result

    def test_particle_size_is_valid_value(self, tmp_path):
        img_path = str(tmp_path / "grounds.jpg")
        _make_test_image(img_path)
        result = analyze_ground_coffee_image(img_path, api_key="")
        valid_sizes = {"fine", "medium-fine", "medium", "medium-coarse", "coarse"}
        assert result["particle_size_distribution"] in valid_sizes


# ---------------------------------------------------------------------------
# _extract_from_ocr_text – decaf / half-caf detection
# ---------------------------------------------------------------------------

class TestExtractDecafStatus:
    def test_decaf_keyword_detected(self):
        result = _extract_from_ocr_text("100% Arabica Decaf Light Roast")
        assert result.get("decaf_status") == "decaf"

    def test_decaffeinated_keyword_detected(self):
        result = _extract_from_ocr_text("Naturally Decaffeinated Ethiopian Coffee")
        assert result.get("decaf_status") == "decaf"

    def test_swiss_water_process_detected(self):
        result = _extract_from_ocr_text("Colombian Swiss Water Process Decaf")
        assert result.get("decaf_status") == "decaf"

    def test_half_caf_detected(self):
        result = _extract_from_ocr_text("Our special Half-Caf blend medium roast")
        assert result.get("decaf_status") == "half-caf"

    def test_half_caf_space_variant_detected(self):
        result = _extract_from_ocr_text("Half Caf morning coffee blend")
        assert result.get("decaf_status") == "half-caf"

    def test_no_decaf_returns_none(self):
        result = _extract_from_ocr_text("Ethiopian Yirgacheffe Light Roast Washed")
        assert result.get("decaf_status") is None

    def test_caffeine_free_detected(self):
        result = _extract_from_ocr_text("Caffeine-Free Colombia Medium Roast")
        assert result.get("decaf_status") == "decaf"


# ---------------------------------------------------------------------------
# _extract_from_ocr_text – expanded variety / species detection
# ---------------------------------------------------------------------------

class TestExtractSpeciesVariety:
    def test_caturra_detected(self):
        result = _extract_from_ocr_text("100% Caturra Colombia Natural")
        assert result.get("species") == "Arabica (Caturra)"

    def test_geisha_detected(self):
        result = _extract_from_ocr_text("Panama Geisha Washed Light Roast")
        assert result.get("species") == "Arabica (Geisha)"

    def test_sl28_detected(self):
        result = _extract_from_ocr_text("Kenya SL28 Natural")
        assert result.get("species") == "Arabica (SL28)"

    def test_sl34_detected(self):
        result = _extract_from_ocr_text("Kenya SL34 Washed")
        assert result.get("species") == "Arabica (SL34)"

    def test_maragogype_detected(self):
        result = _extract_from_ocr_text("Guatemala Maragogype Light Roast")
        assert result.get("species") == "Arabica (Maragogype)"

    def test_maragogipe_variant_detected(self):
        result = _extract_from_ocr_text("Brazil Maragogipe Natural")
        assert result.get("species") == "Arabica (Maragogype)"

    def test_pacas_detected(self):
        result = _extract_from_ocr_text("El Salvador Pacas Honey Process")
        assert result.get("species") == "Arabica (Pacas)"

    def test_pacamara_detected(self):
        result = _extract_from_ocr_text("El Salvador Pacamara Natural")
        assert result.get("species") == "Arabica (Pacamara)"

    def test_wush_wush_detected(self):
        result = _extract_from_ocr_text("Ethiopia Wush Wush Anaerobic Natural")
        assert result.get("species") == "Arabica (Wush Wush)"

    def test_pink_bourbon_detected_before_plain_bourbon(self):
        result = _extract_from_ocr_text("Colombia Pink Bourbon Washed")
        assert result.get("species") == "Arabica (Pink Bourbon)"

    def test_yellow_bourbon_detected(self):
        result = _extract_from_ocr_text("Brazil Yellow Bourbon Natural")
        assert result.get("species") == "Arabica (Yellow Bourbon)"

    def test_mokka_detected(self):
        result = _extract_from_ocr_text("Yemen Mokka Natural Process")
        assert result.get("species") == "Arabica (Mokka)"

    def test_mundo_novo_detected(self):
        result = _extract_from_ocr_text("Brazil Mundo Novo Natural")
        assert result.get("species") == "Arabica (Mundo Novo)"

    def test_default_species_in_label_image_result(self, tmp_path):
        """analyze_label_image default must include decaf_status key with None value."""
        img_path = str(tmp_path / "label.jpg")
        _make_test_image(img_path)
        result = analyze_label_image(img_path, api_key="")
        assert "decaf_status" in result
        assert result["decaf_status"] is None
