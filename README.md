# Bean Identification – Coffee Brewing Assistant

A web-based tool that helps you brew better pour-over coffee by analysing your
coffee bag label, whole beans, and ground coffee through photos.

## Features

| Step | What you do | What you get |
|------|-------------|--------------|
| **1 – Label** | Photo of the bag label | Origin, MASL, species, roast level, roast date, tasting notes, process |
| **2 – Beans** | Photo of whole beans on white/A4 background | Bean colour, size, uniformity, density estimate |
| **3 – Grounds** | Photo of your ground coffee | Particle size distribution, fines %, grind uniformity |
| **4 – Recipe** | — | Personalised V60 pour-over recipe (dose, water, temp, grind, pour schedule) |
| **5 – Feedback** | Rate acidity, sweetness, bitterness, body | Adjusted recipe for your next brew |
| **History** | — | All previous brewing sessions |

Recipe parameters (water temperature, grind size, ratio, bloom time) are
automatically tuned based on roast level, altitude (MASL), origin region,
bean density, and particle size / fines content.

## Tech stack

* **Python 3.10+** · **Flask 3** · **SQLAlchemy** (SQLite)
* **OpenCV** + **pytesseract** for fully local image analysis (no API key needed)
* Bootstrap 5 + Vanilla JS frontend with camera capture support

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/alradulescu/bean-identification.git
cd bean-identification
pip install -r requirements.txt

# 2. (Linux) Install the Tesseract OCR engine for label text extraction
#    sudo apt-get install tesseract-ocr          # Debian/Ubuntu
#    brew install tesseract                      # macOS

# 3. Run
python run.py
# → open http://localhost:5000
```

All image analysis runs locally – no API key or internet connection is required.

## Running tests

```bash
pytest tests/ -v
```

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
├── requirements.txt
├── run.py               # Entry point
└── README.md
```

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

