# Bean Identification – Coffee Brewing Assistant

A web-based tool that helps you brew better pour-over coffee by analysing your
coffee bag label, whole beans, and ground coffee through photos.
All image analysis runs **fully locally** – no API key or internet connection required.

---

## Features

| Step | What you do | What you get |
|------|-------------|--------------|
| **1 – Label** | Photo of the bag label | Origin, MASL, species, roast level, roast date, tasting notes, process |
| **2 – Beans** | Photo of whole beans on white/A4 background | Bean colour, size, uniformity, density estimate |
| **3 – Grounds** | Photo of your ground coffee *(optional)* | Particle size distribution, fines %, grind uniformity |
| **4 – Recipe** | — | Personalised V60 pour-over recipe (dose, water, temp, grind, pour schedule) |
| **5 – Feedback** | Rate acidity, sweetness, bitterness, body | Adjusted recipe for your next brew |
| **History** | — | All previous brewing sessions |

Recipe parameters (water temperature, grind size, ratio, bloom time) are
automatically tuned based on roast level, altitude (MASL), origin region,
bean density, and particle size / fines content.

---

## Tech stack

* **Python 3.10** · **Flask 3** · **SQLAlchemy** (SQLite)
* **OpenCV** + **pytesseract** for fully local image analysis
* Bootstrap 5 + Vanilla JS frontend with camera capture support

---

## Quick start (conda – recommended)

> **Prerequisites:** [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or
> [Anaconda](https://www.anaconda.com/products/distribution) must be installed.

```bash
# 1. Clone the repository
git clone https://github.com/alradulescu/bean-identification.git
cd bean-identification

# 2. Create and activate the conda environment
#    This installs Python, Tesseract OCR, and all Python packages automatically.
conda env create -f environment.yml
conda activate bean-identification

# 3. Run the app
python run.py
# → Open http://localhost:5000 in your browser
```

The `environment.yml` file pins all dependencies (including the Tesseract OCR
engine) so the environment is fully reproducible across macOS, Linux, and
Windows.

### Updating the environment after pulling changes

```bash
conda activate bean-identification
conda env update -f environment.yml --prune
```

### Removing the environment

```bash
conda deactivate
conda env remove -n bean-identification
```

---

## Alternative: pip install (no conda)

If you prefer not to use conda, install dependencies with pip instead.
You will need to install the Tesseract OCR engine separately.

```bash
# Install Tesseract OCR
#   Debian/Ubuntu:  sudo apt-get install tesseract-ocr
#   macOS:          brew install tesseract
#   Windows:        https://github.com/UB-Mannheim/tesseract/wiki

pip install -r requirements.txt
python run.py
```

---

## Running tests

```bash
conda activate bean-identification   # or ensure the pip env is active
pytest tests/ -v
```

---

## Project layout

```
bean-identification/
├── app/
│   ├── __init__.py      # Flask app factory
│   ├── routes.py        # API + web routes
│   ├── models.py        # SQLAlchemy models
│   ├── analysis.py      # Local CV image analysis (OpenCV + pytesseract)
│   ├── recipes.py       # Pour-over recipe logic
│   ├── templates/
│   │   └── index.html   # Single-page web UI
│   └── static/
│       ├── styles.css
│       └── app.js
├── tests/
│   ├── conftest.py
│   ├── test_analysis.py
│   ├── test_recipes.py
│   └── test_routes.py
├── environment.yml      # Conda environment (recommended)
├── requirements.txt     # pip fallback
├── run.py               # Entry point
└── README.md
```

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/analyze-label` | Analyse label image, create session |
| `POST` | `/api/analyze-beans` | Analyse bean image for a session |
| `POST` | `/api/analyze-grounds` | Analyse ground coffee image |
| `GET`  | `/api/recipe/<id>` | Get / generate recipe for a session |
| `POST` | `/api/feedback` | Submit taste feedback, get adjusted recipe |
| `GET`  | `/api/sessions` | List all sessions |
| `GET`  | `/api/sessions/<id>` | Get a single session |

Image endpoints accept either `multipart/form-data` file uploads or a JSON
body with the image as a base64 data-URL (for direct camera capture).

