"""
Image analysis module using local computer vision (OpenCV + pytesseract).

Performs robust local image analysis without requiring any external API key.
Falls back to sensible defaults only if the image cannot be analysed.
The *api_key* parameter is retained for interface compatibility but is unused.
"""

import base64
import json
import logging
import re

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency guards – the app degrades gracefully if missing
# ---------------------------------------------------------------------------

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CV2_AVAILABLE = False
    logger.warning("OpenCV not available – bean/ground analysis will use defaults.")

try:
    import pytesseract
    _TESSERACT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not available – label OCR will use defaults.")

try:
    from PIL import Image, ImageEnhance, ImageFilter
    _PIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PIL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Utility helpers (kept for backward-compatibility with existing imports)
# ---------------------------------------------------------------------------

def _encode_image(image_path: str) -> str:
    """Return a base64-encoded string of the image at *image_path*."""
    with open(image_path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("utf-8")


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
# Image-loading helpers
# ---------------------------------------------------------------------------

def _load_image_cv2(image_path: str):
    """Load an image with OpenCV, falling back to PIL conversion if needed."""
    if not _CV2_AVAILABLE:
        return None
    img = cv2.imread(str(image_path))
    if img is None and _PIL_AVAILABLE:
        # cv2 can fail on certain JPEG/WebP variants – convert via PIL first
        try:
            pil = Image.open(image_path).convert("RGB")
            img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        except Exception:  # noqa: BLE001
            pass
    return img


def _preprocess_for_ocr(pil_image):
    """Enhance a PIL image for better Tesseract OCR accuracy."""
    img = pil_image.convert("L")  # greyscale
    img = ImageEnhance.Contrast(img).enhance(2.5)
    img = img.filter(ImageFilter.SHARPEN)
    # Upscale small images so Tesseract has sufficient resolution
    w, h = img.size
    scale = max(1, 1200 // max(w, h))
    if scale > 1:
        img = img.resize((w * scale, h * scale), Image.LANCZOS)
    return img


# ---------------------------------------------------------------------------
# Label analysis: OCR + keyword matching
# ---------------------------------------------------------------------------

_ORIGIN_KEYWORDS: dict[str, str] = {
    "yirgacheffe": "Ethiopia (Yirgacheffe)",
    "sidamo": "Ethiopia (Sidamo)",
    "harrar": "Ethiopia (Harrar)",
    "ethiopia": "Ethiopia",
    "ethiopian": "Ethiopia",
    "kenya": "Kenya",
    "kenyan": "Kenya",
    "colombia": "Colombia",
    "colombian": "Colombia",
    "brazil": "Brazil",
    "brasil": "Brazil",
    "guatemal": "Guatemala",
    "costa rica": "Costa Rica",
    "panama": "Panama",
    "el salvador": "El Salvador",
    "honduras": "Honduras",
    "peru": "Peru",
    "ecuador": "Ecuador",
    "mexico": "Mexico",
    "nicaragua": "Nicaragua",
    "sumatra": "Indonesia (Sumatra)",
    "sulawesi": "Indonesia (Sulawesi)",
    "java": "Indonesia (Java)",
    "indonesia": "Indonesia",
    "vietnam": "Vietnam",
    "india": "India",
    "yemen": "Yemen",
    "rwanda": "Rwanda",
    "burundi": "Burundi",
    "tanzania": "Tanzania",
    "uganda": "Uganda",
    "kona": "Hawaii (Kona, USA)",
    "hawaii": "Hawaii (USA)",
    "jamaica": "Jamaica",
}

_PROCESS_KEYWORDS: dict[str, str] = {
    "wet-processed": "washed",
    "wet process": "washed",
    "washed": "washed",
    "natural": "natural",
    "dry process": "natural",
    "sun-dried": "natural",
    "sun dried": "natural",
    "honey process": "honey",
    "honey-processed": "honey",
    "honey": "honey",
    "pulped natural": "honey",
    "anaerobic": "anaerobic",
    "carbonic maceration": "anaerobic",
}

_ROAST_KEYWORDS: dict[str, str] = {
    "lightly roasted": "light",
    "light-roast": "light",
    "light roast": "light",
    "blonde": "light",
    "cinnamon roast": "light",
    "medium-light": "medium-light",
    "medium light": "medium-light",
    "medium-dark": "medium-dark",
    "medium dark": "medium-dark",
    "full-city": "medium-dark",
    "full city": "medium-dark",
    "vienna roast": "medium-dark",
    "medium-roast": "medium",
    "medium roast": "medium",
    "dark-roast": "dark",
    "dark roast": "dark",
    "darkly roasted": "dark",
    "french roast": "dark",
    "italian roast": "dark",
    "espresso roast": "dark",
}

_SPECIES_KEYWORDS: dict[str, str] = {
    "coffea arabica": "Arabica",
    "arabica": "Arabica",
    "coffea canephora": "Robusta",
    "robusta": "Robusta",
    "liberica": "Liberica",
    "geisha": "Arabica (Geisha)",
    "gesha": "Arabica (Gesha)",
    "bourbon": "Arabica (Bourbon)",
    "typica": "Arabica (Typica)",
    "caturra": "Arabica (Caturra)",
    "catuai": "Arabica (Catuai)",
    "pacamara": "Arabica (Pacamara)",
    "heirloom": "Arabica (Heirloom)",
    "landrace": "Arabica (Heirloom)",
}

_TASTING_NOTE_WORDS: set[str] = {
    "blueberry", "blackberry", "raspberry", "strawberry", "cherry", "grape",
    "lemon", "lime", "orange", "grapefruit", "peach", "apricot", "plum",
    "mango", "papaya", "pineapple", "passionfruit", "passion fruit",
    "apple", "pear", "fig", "date", "raisin",
    "chocolate", "cocoa",
    "caramel", "toffee", "brown sugar",
    "vanilla", "jasmine", "rose", "lavender", "bergamot",
    "almond", "hazelnut", "walnut",
    "cedar", "tobacco", "leather",
    "tea", "herbal", "mint", "cinnamon", "clove", "nutmeg",
    "winey", "bright", "fruity", "sweet", "juicy",
}


def _extract_from_ocr_text(text: str) -> dict:
    """Parse raw OCR text and extract coffee label fields via keyword matching."""
    tl = text.lower()
    result: dict = {}

    # Match longest keyword first to avoid partial-match shadowing
    for kw, val in sorted(_ORIGIN_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if kw in tl:
            result["origin"] = val
            break

    for kw, val in sorted(_PROCESS_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if kw in tl:
            result["process"] = val
            break

    for kw, val in sorted(_ROAST_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if kw in tl:
            result["roast_level"] = val
            break

    for kw, val in sorted(_SPECIES_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if kw in tl:
            result["species"] = val
            break

    # Altitude / MASL
    for pattern in (
        r"(\d{3,4})\s*[-\u2013]\s*\d{3,4}\s*(?:m|masl)",
        r"(?:altitude|elevation|alt|elev)[:\s]+(\d{3,4})",
        r"masl\s*[:\-]?\s*(\d{3,4})",
        r"(\d{3,4})\s*(?:m|meters?|metres?)\s*(?:above\s*sea\s*level|asl|masl)",
    ):
        m = re.search(pattern, tl)
        if m:
            val_int = int(m.group(1))
            if 500 <= val_int <= 3000:
                result["masl"] = val_int
                break

    # Roast date
    for pattern in (
        r"roast(?:ed)?\s*(?:on|date|:)?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
        r"(?:date|packed)[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
        r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
        r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2},?\s+\d{4}",
    ):
        m = re.search(pattern, tl)
        if m:
            result["roast_date"] = m.group(0).strip()
            break

    # Tasting notes
    notes = [
        w.title()
        for w in sorted(_TASTING_NOTE_WORDS, key=len, reverse=True)
        if w in tl
    ]
    if notes:
        result["tasting_notes"] = ", ".join(notes[:5])

    # Producer name heuristics
    for pattern in (
        r"(?:farm|estate|finca|hacienda|plantation|producer|grower)[:\s]+([A-Z][^\n,]{2,30})",
        r"([A-Z][a-z]+ (?:Farm|Estate|Finca|Hacienda))",
    ):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            result["producer"] = m.group(1).strip()
            break

    return result


# ---------------------------------------------------------------------------
# Bean analysis: OpenCV colour + contour detection
# ---------------------------------------------------------------------------

# LAB L* (0-100) ranges mapped to bean colour labels
_BEAN_COLOR_RANGES = [
    (0,  35, "black"),
    (35, 50, "dark-brown"),
    (50, 65, "medium-brown"),
    (65, 80, "cinnamon"),
    (80, 100, "light-tan"),
]


def _classify_bean_color(mean_l: float) -> str:
    """Map LAB L* mean (0-100) to a bean colour label."""
    for lo, hi, label in _BEAN_COLOR_RANGES:
        if lo <= mean_l < hi:
            return label
    return "medium-brown"


def _analyze_beans_cv2(image_path: str) -> dict:
    """OpenCV-based visual analysis of whole coffee beans."""
    img = _load_image_cv2(image_path)
    if img is None:
        return {}

    h_img, w_img = img.shape[:2]
    img_area = h_img * w_img

    # --- Bean segmentation via adaptive threshold ---
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
        51, 10,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Keep only contours in a plausible size range for coffee beans:
    # at least 0.1 % of image area (noise rejection) and at most 30 %
    # (single-bean close-ups or very large beans on small images).
    min_area = img_area * 0.001
    max_area = img_area * 0.30
    valid = [c for c in contours if min_area < cv2.contourArea(c) < max_area]

    # --- Colour analysis in LAB colour space ---
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    if valid:
        # Build a mask covering only the valid bean regions so background
        # white/paper does not bias the colour measurement
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.drawContours(mask, valid, -1, 255, cv2.FILLED)
        bean_pixels = lab[:, :, 0][mask == 255]
        if bean_pixels.size:
            mean_l = float(np.mean(bean_pixels)) * 100.0 / 255.0
        else:
            mean_l = float(np.mean(lab[:, :, 0])) * 100.0 / 255.0
    else:
        # No distinct regions found – fall back to overall image mean
        mean_l = float(np.mean(lab[:, :, 0])) * 100.0 / 255.0

    bean_color = _classify_bean_color(mean_l)

    # --- Size and uniformity ---
    if len(valid) >= 3:
        areas = [cv2.contourArea(c) for c in valid]
        mean_a = float(np.mean(areas))
        std_a = float(np.std(areas))
        cv_a = std_a / mean_a if mean_a > 0 else 0
        rel_mean = mean_a / img_area
        if rel_mean < 0.005:
            bean_size = "small"
        elif rel_mean > 0.02:
            bean_size = "large"
        else:
            bean_size = "medium"
        uniformity = (
            "uniform" if cv_a < 0.25
            else "slightly-varied" if cv_a < 0.50
            else "varied"
        )
        bean_count = len(valid)
    else:
        bean_size = "medium"
        uniformity = "uniform"
        bean_count = len(valid)

    # --- Density estimate from colour ---
    # Coffee science: darker (more-roasted) beans have expanded cells and are
    # physically less dense ("light" density); lighter (less-roasted),
    # high-altitude beans are compact and physically denser ("dense").
    if mean_l < 45:
        density = "light"
    elif mean_l >= 65:
        density = "dense"
    else:
        density = "medium"

    notes = (
        f"Detected ~{bean_count} bean regions; "
        f"mean brightness L*={mean_l:.1f}/100."
    )
    return {
        "bean_color": bean_color,
        "bean_size": bean_size,
        "bean_uniformity": uniformity,
        "bean_density_estimate": density,
        "analysis_notes": notes,
    }


# ---------------------------------------------------------------------------
# Ground coffee analysis: OpenCV texture + connected-component metrics
# ---------------------------------------------------------------------------

def _analyze_grounds_cv2(image_path: str) -> dict:
    """OpenCV-based analysis of ground coffee images."""
    img = _load_image_cv2(image_path)
    if img is None:
        return {}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img_area = gray.shape[0] * gray.shape[1]

    # --- Particle-size estimate via Laplacian texture score ---
    # The Laplacian of the greyscale image highlights edges (particle
    # boundaries).  Higher variance → more / sharper edges → finer grind.
    # We normalise by image area and scale by 10 000 so the thresholds below
    # are in a convenient 0–1000 range regardless of image resolution.
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    lap_score = float(np.var(lap)) / img_area * 10_000

    if lap_score > 150:
        particle_size = "fine"
    elif lap_score > 80:
        particle_size = "medium-fine"
    elif lap_score > 40:
        particle_size = "medium"
    elif lap_score > 15:
        particle_size = "medium-coarse"
    else:
        particle_size = "coarse"

    # --- Fines estimate via connected-component analysis ---
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((3, 3), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(cleaned)

    fines_percentage = "unknown"
    uniformity = "uniform"
    if num_labels > 1:
        areas = [stats[i, cv2.CC_STAT_AREA] for i in range(1, num_labels)]
        if areas:
            total = len(areas)
            median_a = float(np.median(areas))
            # Particles smaller than 20 % of the median area are classified as
            # "fines" – dust-like particles that can cause over-extraction.
            fines_n = sum(1 for a in areas if a < median_a * 0.2)
            fines_percentage = f"{int(fines_n / total * 100)}%"
            if total > 1:
                cv_p = float(np.std(areas)) / (float(np.mean(areas)) or 1)
                uniformity = (
                    "uniform" if cv_p < 0.5
                    else "slightly-varied" if cv_p < 1.0
                    else "bimodal" if cv_p < 2.0
                    else "varied"
                )

    notes = (
        f"Texture score {lap_score:.1f} → {particle_size} grind; "
        f"estimated fines: {fines_percentage}."
    )
    return {
        "particle_size_distribution": particle_size,
        "fines_percentage": fines_percentage,
        "grind_uniformity": uniformity,
        "analysis_notes": notes,
    }


# ---------------------------------------------------------------------------
# Public analysis functions
# ---------------------------------------------------------------------------

def analyze_label_image(image_path: str, api_key: str = "") -> dict:
    """
    Analyse a coffee bag label using local OCR (pytesseract) and keyword
    extraction.  No external API key is required; *api_key* is accepted for
    interface compatibility but is not used.

    Returns a dict with keys: origin, species, masl, roast_level,
    roast_date, tasting_notes, producer, process.
    """
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

    if not _TESSERACT_AVAILABLE or not _PIL_AVAILABLE:
        logger.warning("pytesseract/PIL not available – returning default label data.")
        return default

    try:
        pil_img = Image.open(image_path)
        processed = _preprocess_for_ocr(pil_img)

        # Try multiple page-segmentation modes for better coverage
        raw_texts: list[str] = []
        for psm in (6, 3, 11):
            try:
                t = pytesseract.image_to_string(processed, config=f"--psm {psm} --oem 3")
                if t.strip():
                    raw_texts.append(t)
            except Exception:  # noqa: BLE001
                pass

        combined = "\n".join(raw_texts)
        if not combined.strip():
            logger.info("OCR returned no text for label image – using defaults.")
            return default

        extracted = _extract_from_ocr_text(combined)
        result = {**default, **extracted}

        if result["masl"] is not None:
            try:
                result["masl"] = int(str(result["masl"]).replace(",", ""))
            except (ValueError, TypeError):
                result["masl"] = None

        return result
    except Exception as exc:  # noqa: BLE001
        logger.error("Label analysis failed: %s", exc)
        return default


def analyze_bean_image(image_path: str, api_key: str = "") -> dict:
    """
    Analyse whole coffee beans using local computer vision (OpenCV).
    Beans on a white/A4 background give the best results.
    The *api_key* parameter is accepted but not used.

    Returns a dict with keys: bean_color, bean_size, bean_uniformity,
    bean_density_estimate, analysis_notes.
    """
    default = {
        "bean_color": "medium-brown",
        "bean_size": "medium",
        "bean_uniformity": "uniform",
        "bean_density_estimate": "medium",
        "analysis_notes": "Visual analysis not available.",
    }

    if not _CV2_AVAILABLE:
        logger.warning("OpenCV not available – returning default bean data.")
        return default

    try:
        result = _analyze_beans_cv2(image_path)
        return result if result else default
    except Exception as exc:  # noqa: BLE001
        logger.error("Bean analysis failed: %s", exc)
        return default


def analyze_ground_coffee_image(image_path: str, api_key: str = "") -> dict:
    """
    Analyse ground coffee using local computer vision (OpenCV).
    The *api_key* parameter is accepted but not used.

    Returns a dict with keys: particle_size_distribution, fines_percentage,
    grind_uniformity, analysis_notes.
    """
    default = {
        "particle_size_distribution": "medium",
        "fines_percentage": "unknown",
        "grind_uniformity": "uniform",
        "analysis_notes": "Visual analysis not available.",
    }

    if not _CV2_AVAILABLE:
        logger.warning("OpenCV not available – returning default ground data.")
        return default

    try:
        result = _analyze_grounds_cv2(image_path)
        return result if result else default
    except Exception as exc:  # noqa: BLE001
        logger.error("Ground analysis failed: %s", exc)
        return default
