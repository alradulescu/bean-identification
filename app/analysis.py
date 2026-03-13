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
    # Ethiopian regions (more specific first)
    "yirgacheffe": "Ethiopia (Yirgacheffe)",
    "yirgecheffe": "Ethiopia (Yirgacheffe)",  # common OCR variant
    "sidamo": "Ethiopia (Sidamo)",
    "sidama": "Ethiopia (Sidama)",
    "harrar": "Ethiopia (Harrar)",
    "harrar": "Ethiopia (Harrar)",
    "harar": "Ethiopia (Harrar)",
    "guji": "Ethiopia (Guji)",
    "gedeo": "Ethiopia (Gedeo)",
    "limu": "Ethiopia (Limu)",
    "jimma": "Ethiopia (Jimma)",
    "kaffa": "Ethiopia (Kaffa)",
    "ethiopia": "Ethiopia",
    "ethiopian": "Ethiopia",
    # Kenyan regions
    "nyeri": "Kenya (Nyeri)",
    "kirinyaga": "Kenya (Kirinyaga)",
    "murang'a": "Kenya (Muranga)",
    "muranga": "Kenya (Muranga)",
    "embu": "Kenya (Embu)",
    "kenya": "Kenya",
    "kenyan": "Kenya",
    # Colombian regions
    "huila": "Colombia (Huila)",
    "nariño": "Colombia (Nariño)",
    "narino": "Colombia (Nariño)",
    "antioquia": "Colombia (Antioquia)",
    "cauca": "Colombia (Cauca)",
    "boyaca": "Colombia (Boyacá)",
    "boyacá": "Colombia (Boyacá)",
    "tolima": "Colombia (Tolima)",
    "sierra nevada": "Colombia (Sierra Nevada)",
    "colombia": "Colombia",
    "colombian": "Colombia",
    # Brazilian regions
    "minas gerais": "Brazil (Minas Gerais)",
    "cerrado mineiro": "Brazil (Cerrado Mineiro)",
    "cerrado": "Brazil (Cerrado)",
    "sul de minas": "Brazil (Sul de Minas)",
    "mogiana": "Brazil (Mogiana)",
    "chapada diamantina": "Brazil (Chapada Diamantina)",
    "espirito santo": "Brazil (Espírito Santo)",
    "brazil": "Brazil",
    "brasil": "Brazil",
    # Guatemalan regions
    "antigua": "Guatemala (Antigua)",
    "huehuetenango": "Guatemala (Huehuetenango)",
    "atitlan": "Guatemala (Atitlán)",
    "atitlán": "Guatemala (Atitlán)",
    "acatenango": "Guatemala (Acatenango)",
    "coban": "Guatemala (Cobán)",
    "guatemal": "Guatemala",
    # Costa Rican regions
    "tarrazú": "Costa Rica (Tarrazú)",
    "tarrazu": "Costa Rica (Tarrazú)",
    "costa rica": "Costa Rica",
    # Panamanian regions
    "boquete": "Panama (Boquete)",
    "panama": "Panama",
    "panamanian": "Panama",
    # Central American
    "el salvador": "El Salvador",
    "honduran": "Honduras",
    "honduras": "Honduras",
    "marcala": "Honduras (Marcala)",
    "peru": "Peru",
    "peruvian": "Peru",
    "ecuador": "Ecuador",
    "ecuadorian": "Ecuador",
    "mexico": "Mexico",
    "mexican": "Mexico",
    "oaxaca": "Mexico (Oaxaca)",
    "chiapas": "Mexico (Chiapas)",
    "nicaragua": "Nicaragua",
    "bolivia": "Bolivia",
    "venezuela": "Venezuela",
    # Indonesian islands & regions
    "sumatra": "Indonesia (Sumatra)",
    "sulawesi": "Indonesia (Sulawesi)",
    "toraja": "Indonesia (Sulawesi, Toraja)",
    "kalosi": "Indonesia (Sulawesi, Kalosi)",
    "java": "Indonesia (Java)",
    "flores": "Indonesia (Flores)",
    "timor": "Indonesia (Timor)",
    "lintong": "Indonesia (Sumatra, Lintong)",
    "mandheling": "Indonesia (Sumatra, Mandheling)",
    "gayo": "Indonesia (Sumatra, Gayo)",
    "indonesia": "Indonesia",
    "indonesian": "Indonesia",
    "papua new guinea": "Papua New Guinea",
    "p.n.g": "Papua New Guinea",
    "png coffee": "Papua New Guinea",
    # Asian origins
    "vietnam": "Vietnam",
    "vietnamese": "Vietnam",
    "china": "China (Yunnan)",
    "yunnan": "China (Yunnan)",
    "laos": "Laos",
    "myanmar": "Myanmar",
    "thailand": "Thailand",
    "philippines": "Philippines",
    "india": "India",
    "coorg": "India (Coorg)",
    "chikmagalur": "India (Chikmagalur)",
    "araku": "India (Araku Valley)",
    "yemen": "Yemen",
    "yemeni": "Yemen",
    # African origins
    "rwanda": "Rwanda",
    "rwandan": "Rwanda",
    "burundi": "Burundi",
    "tanzania": "Tanzania",
    "tanzanian": "Tanzania",
    "uganda": "Uganda",
    "zimbabwe": "Zimbabwe",
    "malawi": "Malawi",
    "cameroon": "Cameroon",
    "congo": "DR Congo",
    "zambia": "Zambia",
    # Caribbean & Pacific
    "kona": "Hawaii (Kona, USA)",
    "hawaii": "Hawaii (USA)",
    "jamaica": "Jamaica",
    "dominican": "Dominican Republic",
    "cuba": "Cuba",
    "haiti": "Haiti",
    "puerto rico": "Puerto Rico",
}

_PROCESS_KEYWORDS: dict[str, str] = {
    "wet-processed": "washed",
    "wet process": "washed",
    "fully washed": "washed",
    "washed": "washed",
    "semi-washed": "semi-washed",
    "semi washed": "semi-washed",
    "wet-hulled": "wet-hulled",
    "wet hulled": "wet-hulled",
    "giling basah": "wet-hulled",       # Indonesian term
    "black honey process": "black honey",
    "black honey-processed": "black honey",
    "black honey": "black honey",
    "red honey process": "red honey",
    "red honey-processed": "red honey",
    "red honey": "red honey",
    "yellow honey process": "yellow honey",
    "yellow honey-processed": "yellow honey",
    "yellow honey": "yellow honey",
    "white honey process": "white honey",
    "white honey-processed": "white honey",
    "white honey": "white honey",
    "honey process": "honey",
    "honey-processed": "honey",
    "honey": "honey",
    "pulped natural": "honey",
    "natural": "natural",
    "dry process": "natural",
    "dry-process": "natural",
    "sun-dried": "natural",
    "sun dried": "natural",
    "dry natural": "natural",
    "anaerobic natural": "anaerobic natural",
    "anaerobic washed": "anaerobic washed",
    "anaerobic": "anaerobic",
    "carbonic maceration": "carbonic maceration",
    "extended fermentation": "extended fermentation",
    "double fermentation": "double fermentation",
    "lactic": "lactic fermentation",
    "thermal shock": "thermal shock",
}

_ROAST_KEYWORDS: dict[str, str] = {
    "lightly roasted": "light",
    "light-roast": "light",
    "light roast": "light",
    "blonde": "light",
    "cinnamon roast": "light",
    "new england roast": "light",
    "half city": "light",
    "half-city": "light",
    "medium-light": "medium-light",
    "medium light": "medium-light",
    "city roast": "medium-light",
    "medium-dark": "medium-dark",
    "medium dark": "medium-dark",
    "full-city": "medium-dark",
    "full city": "medium-dark",
    "full city+": "medium-dark",
    "full-city+": "medium-dark",
    "vienna roast": "medium-dark",
    "continental roast": "medium-dark",
    "medium-roast": "medium",
    "medium roast": "medium",
    "city+": "medium",
    "dark-roast": "dark",
    "dark roast": "dark",
    "darkly roasted": "dark",
    "french roast": "dark",
    "italian roast": "dark",
    "espresso roast": "dark",
    "high roast": "dark",
    "new orleans roast": "dark",
}

_SPECIES_KEYWORDS: dict[str, str] = {
    "coffea arabica": "Arabica",
    "arabica": "Arabica",
    "coffea canephora": "Robusta",
    "coffea robusta": "Robusta",
    "robusta": "Robusta",
    "liberica": "Liberica",
    "excelsa": "Liberica (Excelsa)",
    "geisha": "Arabica (Geisha)",
    "gesha": "Arabica (Gesha)",
    "pink bourbon": "Arabica (Pink Bourbon)",
    "red bourbon": "Arabica (Red Bourbon)",
    "yellow bourbon": "Arabica (Yellow Bourbon)",
    "orange bourbon": "Arabica (Orange Bourbon)",
    "bourbon": "Arabica (Bourbon)",
    "typica": "Arabica (Typica)",
    "caturra": "Arabica (Caturra)",
    "catuai": "Arabica (Catuai)",
    "pacamara": "Arabica (Pacamara)",
    "pacas": "Arabica (Pacas)",
    "maragogype": "Arabica (Maragogype)",
    "maragogipe": "Arabica (Maragogype)",
    "sl28": "Arabica (SL28)",
    "sl34": "Arabica (SL34)",
    "wush wush": "Arabica (Wush Wush)",
    "castillo": "Arabica (Castillo)",
    "mundo novo": "Arabica (Mundo Novo)",
    "villa sarchi": "Arabica (Villa Sarchi)",
    "villalobos": "Arabica (Villalobos)",
    "mokka": "Arabica (Mokka)",
    "moka": "Arabica (Mokka)",
    "ruiru 11": "Arabica (Ruiru 11)",
    "ruiru11": "Arabica (Ruiru 11)",
    "batian": "Arabica (Batian)",
    "heirloom": "Arabica (Heirloom)",
    "landrace": "Arabica (Heirloom)",
    "catimor": "Arabica (Catimor)",
    "sarchimor": "Arabica (Sarchimor)",
    "hibrido de timor": "Arabica (Timor-Hybrid)",
    "timor hybrid": "Arabica (Timor-Hybrid)",
    "sudan rume": "Arabica (Sudan Rume)",
    "obatã": "Arabica (Obatã)",
    "obata": "Arabica (Obatã)",
    "icatu": "Arabica (Icatu)",
    "kent": "Arabica (Kent)",
    "s795": "Arabica (S795)",
    "s288": "Arabica (S288)",
    "74110": "Arabica (74110)",
    "74158": "Arabica (74158)",
    "laurina": "Arabica (Laurina)",
    "java variety": "Arabica (Java Variety)",
    "maracaturra": "Arabica (Maracaturra)",
    "anacafe 14": "Arabica (Anacafe 14)",
    "marsellesa": "Arabica (Marsellesa)",
    "lempira": "Arabica (Lempira)",
    "ihcafe 90": "Arabica (IHCAFE 90)",
    "parainema": "Arabica (Parainema)",
}

_DECAF_KEYWORDS: dict[str, str] = {
    "naturally decaffeinated": "decaf",
    "caffeine-free": "decaf",
    "caffeine free": "decaf",
    "swiss water process": "decaf",
    "swiss water": "decaf",
    "mountain water process": "decaf",
    "mountain water": "decaf",
    "co2 decaffeinated": "decaf",
    "co2 decaf": "decaf",
    "decaffeinated": "decaf",
    "decaf": "decaf",
    "half-decaf": "half-caf",
    "half decaf": "half-caf",
    "half-caf": "half-caf",
    "half caf": "half-caf",
    "50/50 blend": "half-caf",
}

_CERTIFICATION_KEYWORDS: dict[str, str] = {
    "certified organic": "organic",
    "usda organic": "organic",
    "usda certified organic": "organic",
    "eu organic": "organic",
    "organic certified": "organic",
    "organic": "organic",
    "fair trade certified": "fair-trade",
    "fairtrade certified": "fair-trade",
    "fair trade": "fair-trade",
    "fairtrade": "fair-trade",
    "rainforest alliance certified": "rainforest-alliance",
    "rainforest alliance": "rainforest-alliance",
    "utz certified": "utz",
    "utz": "utz",
    "bird friendly": "bird-friendly",
    "smithsonian bird friendly": "bird-friendly",
    "shade grown": "shade-grown",
    "shade-grown": "shade-grown",
    "direct trade": "direct-trade",
    "direct-trade": "direct-trade",
    "specialty grade": "specialty",
    "specialty coffee": "specialty",
    "single estate": "single-estate",
    "single origin": "single-origin",
    "micro lot": "micro-lot",
    "microlot": "micro-lot",
    "cup of excellence": "cup-of-excellence",
    "coe": "cup-of-excellence",
    "4c certified": "4c",
    "rainforest": "rainforest-alliance",
}

_TASTING_NOTE_WORDS: set[str] = {
    # Berries & stone fruits
    "blueberry", "blackberry", "raspberry", "strawberry", "cherry",
    "black cherry", "maraschino", "grape", "currant", "elderberry",
    "peach", "apricot", "plum", "nectarine", "lychee",
    # Citrus
    "lemon", "lime", "orange", "grapefruit", "tangerine", "yuzu",
    "bergamot", "mandarin", "blood orange",
    # Tropical fruits
    "mango", "papaya", "pineapple", "passionfruit", "passion fruit",
    "guava", "coconut", "banana", "jackfruit", "tamarind",
    # Other fruits
    "apple", "pear", "fig", "date", "raisin", "prune", "melon",
    "watermelon", "pomegranate",
    # Chocolate & sweet
    "chocolate", "dark chocolate", "milk chocolate", "cocoa", "cacao",
    "caramel", "toffee", "brown sugar", "molasses", "butterscotch",
    "honey", "maple syrup", "marshmallow", "marzipan",
    # Vanilla & floral
    "vanilla", "jasmine", "rose", "lavender", "hibiscus", "chamomile",
    "orange blossom", "honeysuckle", "lilac", "violet",
    # Nuts
    "almond", "hazelnut", "walnut", "pecan", "cashew", "peanut",
    "macadamia", "pistachio",
    # Spices & herbs
    "cinnamon", "clove", "nutmeg", "cardamom", "ginger", "anise",
    "black pepper", "allspice", "mint", "herbal", "thyme", "sage",
    # Earthy & woody
    "cedar", "tobacco", "leather", "earth", "musty", "forest floor",
    "oak", "sandalwood", "pine", "resinous",
    # Tea-like
    "tea", "black tea", "green tea", "oolong", "earl grey",
    # Descriptive
    "winey", "bright", "fruity", "sweet", "juicy", "crisp",
    "floral", "nutty", "spicy", "smoky", "buttery", "creamy",
    "silky", "velvety", "clean", "complex", "balanced", "delicate",
}


def _normalize_ocr_text(text: str) -> str:
    """
    Normalize raw OCR output to improve keyword-matching reliability.

    Collapses excess whitespace, lowercases, and normalises common OCR
    character substitutions that occur on coffee bag labels.
    The original text is *not* modified in-place.
    """
    # Collapse runs of whitespace / newlines to a single space
    normalized = re.sub(r"[\r\n\t]+", " ", text)
    normalized = re.sub(r" {2,}", " ", normalized)
    # Lowercase before applying character substitutions so that the
    # lookbehind/lookahead patterns (`[a-z]`) always match correctly.
    normalized = normalized.lower()
    # Common OCR letter/digit confusions on printed labels
    substitutions = [
        (r"(?<=[a-z])0(?=[a-z])", "o"),   # 0 → o inside words (e.g. "c0lombia")
        (r"(?<=[a-z])1(?=[a-z])", "l"),   # 1 → l inside words (e.g. "1ight")
    ]
    for pattern, replacement in substitutions:
        normalized = re.sub(pattern, replacement, normalized)
    return normalized


def _extract_from_ocr_text(text: str) -> dict:
    """Parse raw OCR text and extract coffee label fields via keyword matching."""
    tl = _normalize_ocr_text(text)
    result: dict = {}

    # Match origin keywords – prefer specific regional entries (those whose value
    # contains a parenthetical region, e.g. "Ethiopia (Guji)") over bare country
    # names before falling back to longest-key-first within each priority tier.
    def _origin_sort_key(item: tuple) -> tuple:
        kw, val = item
        has_region = "(" in val
        return (not has_region, -len(kw))

    for kw, val in sorted(_ORIGIN_KEYWORDS.items(), key=_origin_sort_key):
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

    for kw, val in sorted(_DECAF_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if kw in tl:
            result["decaf_status"] = val
            break

    # Certifications – collect all that match (a bag can carry multiple)
    found_certs: list[str] = []
    seen_certs: set[str] = set()
    for kw, val in sorted(_CERTIFICATION_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if kw in tl and val not in seen_certs:
            found_certs.append(val)
            seen_certs.add(val)
    if found_certs:
        result["certifications"] = ", ".join(found_certs)

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

    # Lot / batch number
    for pattern in (
        r"(?:lot|batch)\s*(?:no\.?|number|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-]{1,19})",
        r"\blot\s+([A-Z0-9\-]{2,20})\b",
    ):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            # Skip tokens that look like dates or are purely numeric
            if (
                not re.fullmatch(r"\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}", candidate)
                and not candidate.isdigit()
            ):
                result["lot_number"] = candidate
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
    roast_date, tasting_notes, producer, process, decaf_status,
    certifications, lot_number.
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
        "decaf_status": None,
        "certifications": None,
        "lot_number": None,
    }

    if not _TESSERACT_AVAILABLE or not _PIL_AVAILABLE:
        logger.warning("pytesseract/PIL not available – returning default label data.")
        return default

    try:
        pil_img = Image.open(image_path)
        processed_standard = _preprocess_for_ocr(pil_img)

        # Also prepare an inverted version for labels with light text on dark
        # backgrounds (e.g. kraft paper, foil bags with white print).
        try:
            from PIL import ImageOps
            processed_inverted = _preprocess_for_ocr(ImageOps.invert(pil_img.convert("RGB")))
        except Exception as inv_exc:  # noqa: BLE001
            logger.debug("Could not create inverted label image: %s", inv_exc)
            processed_inverted = None

        raw_texts: list[str] = []

        # Try multiple page-segmentation modes on the standard preprocessed image.
        # PSM 6 = uniform block of text (most common for labels)
        # PSM 3 = fully automatic (handles mixed layouts)
        # PSM 4 = single column (good for tall, narrow labels)
        # PSM 11 = sparse text (best for text scattered over the bag)
        for psm in (6, 3, 4, 11):
            for img_variant in ([processed_standard] + ([processed_inverted] if processed_inverted else [])):
                try:
                    t = pytesseract.image_to_string(img_variant, config=f"--psm {psm} --oem 3")
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
