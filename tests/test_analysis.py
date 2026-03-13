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


# ---------------------------------------------------------------------------
# _extract_from_ocr_text – new varietal detection
# ---------------------------------------------------------------------------

class TestExtractNewVarietals:
    def test_catimor_detected(self):
        result = _extract_from_ocr_text("Honduras Catimor Washed Medium Roast")
        assert result.get("species") == "Arabica (Catimor)"

    def test_sarchimor_detected(self):
        result = _extract_from_ocr_text("Colombia Sarchimor Natural Light Roast")
        assert result.get("species") == "Arabica (Sarchimor)"

    def test_sudan_rume_detected(self):
        result = _extract_from_ocr_text("Ethiopia Sudan Rume Natural Process")
        assert result.get("species") == "Arabica (Sudan Rume)"

    def test_obata_detected(self):
        result = _extract_from_ocr_text("Brazil Obata Natural Honey")
        assert result.get("species") == "Arabica (Obatã)"

    def test_obata_with_accent_detected(self):
        result = _extract_from_ocr_text("Brazil Obatã Natural Process")
        assert result.get("species") == "Arabica (Obatã)"

    def test_icatu_detected(self):
        result = _extract_from_ocr_text("Brazil Icatu Natural Medium")
        assert result.get("species") == "Arabica (Icatu)"

    def test_robusta_detected(self):
        result = _extract_from_ocr_text("100% Robusta Dark Roast Espresso")
        assert result.get("species") == "Robusta"

    def test_liberica_detected(self):
        result = _extract_from_ocr_text("Philippines Liberica Coffee")
        assert result.get("species") == "Liberica"

    def test_excelsa_detected(self):
        result = _extract_from_ocr_text("Laos Excelsa Natural")
        assert result.get("species") == "Liberica (Excelsa)"

    def test_kent_detected(self):
        result = _extract_from_ocr_text("India Coorg Kent Washed")
        assert result.get("species") == "Arabica (Kent)"


# ---------------------------------------------------------------------------
# _extract_from_ocr_text – expanded origin detection
# ---------------------------------------------------------------------------

class TestExtractExpandedOrigins:
    def test_guji_detected(self):
        result = _extract_from_ocr_text("Ethiopia Guji Natural Light Roast")
        assert result.get("origin") == "Ethiopia (Guji)"

    def test_sidama_detected(self):
        result = _extract_from_ocr_text("Ethiopia Sidama Washed")
        assert result.get("origin") == "Ethiopia (Sidama)"

    def test_nyeri_detected(self):
        result = _extract_from_ocr_text("Kenya Nyeri SL28 Washed")
        assert result.get("origin") == "Kenya (Nyeri)"

    def test_huila_detected(self):
        result = _extract_from_ocr_text("Colombia Huila Caturra Natural")
        assert result.get("origin") == "Colombia (Huila)"

    def test_narino_detected(self):
        result = _extract_from_ocr_text("Colombia Narino Washed")
        assert result.get("origin") == "Colombia (Nariño)"

    def test_cerrado_detected(self):
        result = _extract_from_ocr_text("Brazil Cerrado Natural Medium Roast")
        assert result.get("origin") == "Brazil (Cerrado)"

    def test_antigua_detected(self):
        result = _extract_from_ocr_text("Guatemala Antigua Washed Medium-Dark")
        assert result.get("origin") == "Guatemala (Antigua)"

    def test_boquete_detected(self):
        result = _extract_from_ocr_text("Panama Boquete Geisha Washed")
        assert result.get("origin") == "Panama (Boquete)"

    def test_tarrazu_detected(self):
        result = _extract_from_ocr_text("Costa Rica Tarrazu Honey Process")
        assert result.get("origin") == "Costa Rica (Tarrazú)"

    def test_toraja_detected(self):
        result = _extract_from_ocr_text("Indonesia Toraja Wet-Hulled")
        assert result.get("origin") == "Indonesia (Sulawesi, Toraja)"

    def test_gayo_detected(self):
        result = _extract_from_ocr_text("Indonesia Gayo Natural Dark")
        assert result.get("origin") == "Indonesia (Sumatra, Gayo)"

    def test_yunnan_detected(self):
        result = _extract_from_ocr_text("China Yunnan Natural Honey")
        assert result.get("origin") == "China (Yunnan)"

    def test_zimbabwe_detected(self):
        result = _extract_from_ocr_text("Zimbabwe Coffee Natural")
        assert result.get("origin") == "Zimbabwe"

    def test_bolivia_detected(self):
        result = _extract_from_ocr_text("Bolivia Natural Light Roast")
        assert result.get("origin") == "Bolivia"

    def test_papua_new_guinea_detected(self):
        result = _extract_from_ocr_text("Papua New Guinea Goroka Natural")
        assert result.get("origin") == "Papua New Guinea"


# ---------------------------------------------------------------------------
# _extract_from_ocr_text – certifications detection
# ---------------------------------------------------------------------------

class TestExtractCertifications:
    def test_organic_detected(self):
        result = _extract_from_ocr_text("Ethiopia Organic Light Roast")
        assert result.get("certifications") == "organic"

    def test_usda_organic_detected(self):
        result = _extract_from_ocr_text("Colombia USDA Organic Medium Roast")
        assert result.get("certifications") == "organic"

    def test_certified_organic_detected(self):
        result = _extract_from_ocr_text("Kenya Certified Organic Washed")
        assert result.get("certifications") == "organic"

    def test_fair_trade_detected(self):
        result = _extract_from_ocr_text("Colombia Fair Trade Certified Washed")
        assert result.get("certifications") == "fair-trade"

    def test_fairtrade_single_word_detected(self):
        result = _extract_from_ocr_text("Ethiopia Fairtrade Natural")
        assert result.get("certifications") == "fair-trade"

    def test_rainforest_alliance_detected(self):
        result = _extract_from_ocr_text("Honduras Rainforest Alliance Certified")
        assert result.get("certifications") == "rainforest-alliance"

    def test_bird_friendly_detected(self):
        result = _extract_from_ocr_text("Mexico Bird Friendly Shade Grown")
        certs = result.get("certifications", "")
        assert "bird-friendly" in certs

    def test_multiple_certs_detected(self):
        result = _extract_from_ocr_text("Peru USDA Organic Fair Trade Certified Single Origin")
        certs = result.get("certifications", "")
        assert "organic" in certs
        assert "fair-trade" in certs

    def test_single_origin_detected(self):
        result = _extract_from_ocr_text("Single Origin Ethiopia Light Roast")
        assert result.get("certifications") == "single-origin"

    def test_micro_lot_detected(self):
        result = _extract_from_ocr_text("Kenya Micro Lot SL28 Washed")
        assert result.get("certifications") == "micro-lot"

    def test_direct_trade_detected(self):
        result = _extract_from_ocr_text("Guatemala Direct Trade Honey Process")
        assert result.get("certifications") == "direct-trade"

    def test_no_certifications_returns_none(self):
        result = _extract_from_ocr_text("Ethiopia Yirgacheffe Light Roast Washed")
        assert result.get("certifications") is None

    def test_certifications_in_label_image_default(self, tmp_path):
        """analyze_label_image default must include certifications key."""
        img_path = str(tmp_path / "label.jpg")
        _make_test_image(img_path)
        result = analyze_label_image(img_path, api_key="")
        assert "certifications" in result


# ---------------------------------------------------------------------------
# _extract_from_ocr_text – lot number and extended processing detection
# ---------------------------------------------------------------------------

class TestExtractLotAndProcess:
    def test_lot_number_detected(self):
        result = _extract_from_ocr_text("Ethiopia Yirgacheffe Lot: AB1234 Washed")
        assert result.get("lot_number") == "AB1234"

    def test_batch_number_detected(self):
        result = _extract_from_ocr_text("Colombia Batch No. BT-2024-07 Honey")
        assert result.get("lot_number") == "BT-2024-07"

    def test_black_honey_detected(self):
        result = _extract_from_ocr_text("El Salvador Black Honey Process")
        assert result.get("process") == "black honey"

    def test_red_honey_detected(self):
        result = _extract_from_ocr_text("Costa Rica Red Honey Medium Roast")
        assert result.get("process") == "red honey"

    def test_wet_hulled_detected(self):
        result = _extract_from_ocr_text("Indonesia Sumatra Giling Basah")
        assert result.get("process") == "wet-hulled"

    def test_anaerobic_natural_detected(self):
        result = _extract_from_ocr_text("Ethiopia Guji Anaerobic Natural Light")
        assert result.get("process") == "anaerobic natural"

    def test_anaerobic_washed_detected(self):
        result = _extract_from_ocr_text("Colombia Anaerobic Washed Light Roast")
        assert result.get("process") == "anaerobic washed"


# ---------------------------------------------------------------------------
# _extract_from_ocr_text – OCR normalization
# ---------------------------------------------------------------------------

class TestOCRNormalization:
    def test_normalize_ocr_text_imported(self):
        """_normalize_ocr_text should be importable and work."""
        from app.analysis import _normalize_ocr_text
        assert _normalize_ocr_text("hello  world\n\ntest") == "hello world test"

    def test_normalize_collapses_whitespace(self):
        from app.analysis import _normalize_ocr_text
        result = _normalize_ocr_text("  multiple   spaces  ")
        assert "  " not in result

    def test_normalize_handles_newlines(self):
        from app.analysis import _normalize_ocr_text
        result = _normalize_ocr_text("line1\nline2\nline3")
        assert "\n" not in result
