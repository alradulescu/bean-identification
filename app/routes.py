"""Flask routes for the Coffee Brewing Assistant."""

import json
import os
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from .analysis import analyze_bean_image, analyze_ground_coffee_image, analyze_label_image
from .models import BrewingFeedback, CoffeeSession, db
from .recipes import adjust_recipe_from_feedback, generate_recipe, get_grind_adjustment_recommendation

main = Blueprint("main", __name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "jfif",
    "gif",
    "webp",
    "heic",
    "heif",
}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _ALLOWED_EXTENSIONS


def _save_upload(file_storage) -> str | None:
    """Save an uploaded file and return its absolute path, or None on failure."""
    if not file_storage or not file_storage.filename:
        return None
    if not _allowed_file(file_storage.filename):
        return None
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4()}.{ext}"
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file_storage.save(path)
    return path


def _save_base64_image(data_url: str) -> str | None:
    """
    Decode a data-URL (base64) image and save it.  Returns file path or None.
    Expected format: ``data:<mime>;base64,<data>``
    """
    try:
        import base64
        header, encoded = data_url.split(",", 1)
        ext = "jpg"
        if "png" in header:
            ext = "png"
        elif "webp" in header:
            ext = "webp"
        filename = f"{uuid.uuid4()}.{ext}"
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(encoded))
        return path
    except Exception:  # noqa: BLE001
        return None


def _get_image_path(field_name: str) -> str | None:
    """
    Resolve an image from either a multipart upload or a JSON base64 data-URL.
    Returns the saved file path or None.
    """
    if field_name in request.files:
        return _save_upload(request.files[field_name])
    # Try JSON body
    body = request.get_json(silent=True) or {}
    data_url = body.get(field_name)
    if data_url and isinstance(data_url, str) and data_url.startswith("data:"):
        return _save_base64_image(data_url)
    return None


# ---------------------------------------------------------------------------
# Web UI
# ---------------------------------------------------------------------------


@main.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# API – label analysis
# ---------------------------------------------------------------------------


@main.route("/api/analyze-label", methods=["POST"])
def api_analyze_label():
    """
    Analyse a coffee bag label image.

    Accepts multipart/form-data with field ``label_image``,
    or JSON body with ``label_image`` as a base64 data-URL.

    Returns JSON with extracted coffee information and a new session id.
    """
    image_path = _get_image_path("label_image")
    if not image_path:
        return jsonify({"error": "No valid image provided in 'label_image' field"}), 400

    try:
        api_key = current_app.config.get("OPENAI_API_KEY", "")
        coffee_info = analyze_label_image(image_path, api_key=api_key)

        # Persist a new session
        session = CoffeeSession(
            origin=coffee_info.get("origin"),
            species=coffee_info.get("species"),
            masl=coffee_info.get("masl"),
            roast_level=coffee_info.get("roast_level"),
            roast_date=coffee_info.get("roast_date"),
            tasting_notes=coffee_info.get("tasting_notes"),
            producer=coffee_info.get("producer"),
            process=coffee_info.get("process"),
            decaf_status=coffee_info.get("decaf_status"),
            certifications=coffee_info.get("certifications"),
            lot_number=coffee_info.get("lot_number"),
        )
        db.session.add(session)
        db.session.commit()

        return jsonify({"session_id": session.id, "coffee_info": coffee_info}), 200
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        current_app.logger.exception("Failed to analyze/persist label session: %s", exc)
        return jsonify({"error": "Failed to analyze label image"}), 500


# ---------------------------------------------------------------------------
# API – bean image analysis
# ---------------------------------------------------------------------------


@main.route("/api/analyze-beans", methods=["POST"])
def api_analyze_beans():
    """
    Analyse a bean image.

    Required: ``bean_image`` (file or base64) + ``session_id`` (form or JSON).
    """
    image_path = _get_image_path("bean_image")
    if not image_path:
        return jsonify({"error": "No valid image provided in 'bean_image' field"}), 400

    body = request.form or (request.get_json(silent=True) or {})
    session_id = body.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    session = db.session.get(CoffeeSession, int(session_id))
    if not session:
        return jsonify({"error": "Session not found"}), 404

    api_key = current_app.config.get("OPENAI_API_KEY", "")
    bean_data = analyze_bean_image(image_path, api_key=api_key)

    session.bean_color = bean_data.get("bean_color")
    session.bean_size = bean_data.get("bean_size")
    session.bean_uniformity = bean_data.get("bean_uniformity")
    session.bean_density_estimate = bean_data.get("bean_density_estimate")
    session.bean_analysis_notes = bean_data.get("analysis_notes")

    # Generate recipe now that we have bean info
    coffee_info = {
        "origin": session.origin,
        "species": session.species,
        "masl": session.masl,
        "roast_level": session.roast_level,
        "process": session.process,
        "decaf_status": session.decaf_status,
    }
    recipe = generate_recipe(coffee_info, bean_analysis=bean_data)
    session.recipe_json = json.dumps(recipe)
    db.session.commit()

    return jsonify({"bean_analysis": bean_data, "recipe": recipe}), 200


# ---------------------------------------------------------------------------
# API – ground coffee analysis
# ---------------------------------------------------------------------------


@main.route("/api/analyze-grounds", methods=["POST"])
def api_analyze_grounds():
    """
    Analyse a ground-coffee image.

    Required: ``grounds_image`` (file or base64) + ``session_id``.
    """
    image_path = _get_image_path("grounds_image")
    if not image_path:
        return jsonify({"error": "No valid image provided in 'grounds_image' field"}), 400

    body = request.form or (request.get_json(silent=True) or {})
    session_id = body.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    session = db.session.get(CoffeeSession, int(session_id))
    if not session:
        return jsonify({"error": "Session not found"}), 404

    api_key = current_app.config.get("OPENAI_API_KEY", "")
    ground_data = analyze_ground_coffee_image(image_path, api_key=api_key)

    session.particle_size_distribution = ground_data.get("particle_size_distribution")
    session.fines_percentage = ground_data.get("fines_percentage")
    session.grind_uniformity = ground_data.get("grind_uniformity")
    session.ground_analysis_notes = ground_data.get("analysis_notes")

    # Optionally regenerate recipe with grind info
    existing_recipe = json.loads(session.recipe_json) if session.recipe_json else None
    if existing_recipe:
        coffee_info = {
            "origin": session.origin,
            "species": session.species,
            "masl": session.masl,
            "roast_level": session.roast_level,
            "process": session.process,
            "decaf_status": session.decaf_status,
        }
        bean_data_for_recipe = {
            "bean_color": session.bean_color,
            "bean_size": session.bean_size,
            "bean_uniformity": session.bean_uniformity,
            "bean_density_estimate": session.bean_density_estimate,
            "fines_percentage": ground_data.get("fines_percentage"),
        }
        recipe = generate_recipe(coffee_info, bean_analysis=bean_data_for_recipe)
        session.recipe_json = json.dumps(recipe)

    db.session.commit()

    # Compare observed grind size to recipe target and advise adjustments
    current_recipe = json.loads(session.recipe_json) if session.recipe_json else {}
    grind_recommendation = get_grind_adjustment_recommendation(ground_data, current_recipe)

    return jsonify(
        {
            "ground_analysis": ground_data,
            "recipe": current_recipe if current_recipe else None,
            "grind_recommendation": grind_recommendation,
        }
    ), 200


# ---------------------------------------------------------------------------
# API – generate / retrieve recipe
# ---------------------------------------------------------------------------


@main.route("/api/recipe/<int:session_id>", methods=["GET"])
def api_get_recipe(session_id):
    """Return the current recipe for a session."""
    session = db.session.get(CoffeeSession, session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    if not session.recipe_json:
        # Generate a basic recipe from label info only
        coffee_info = {
            "origin": session.origin,
            "species": session.species,
            "masl": session.masl,
            "roast_level": session.roast_level,
            "process": session.process,
            "decaf_status": session.decaf_status,
        }
        recipe = generate_recipe(coffee_info)
        session.recipe_json = json.dumps(recipe)
        db.session.commit()
    else:
        recipe = json.loads(session.recipe_json)

    return jsonify({"session_id": session_id, "recipe": recipe}), 200


# ---------------------------------------------------------------------------
# API – feedback
# ---------------------------------------------------------------------------


@main.route("/api/feedback", methods=["POST"])
def api_submit_feedback():
    """
    Submit taste feedback and receive an adjusted recipe.

    Body (JSON or form): session_id, acidity, sweetness, bitterness, body,
    overall, extraction, notes.
    """
    body = request.get_json(silent=True) or request.form.to_dict()

    session_id = body.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    session = db.session.get(CoffeeSession, int(session_id))
    if not session:
        return jsonify({"error": "Session not found"}), 404

    def _int_or_none(val):
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    feedback = BrewingFeedback(
        session_id=session.id,
        acidity=_int_or_none(body.get("acidity")),
        sweetness=_int_or_none(body.get("sweetness")),
        bitterness=_int_or_none(body.get("bitterness")),
        body=_int_or_none(body.get("body")),
        overall=_int_or_none(body.get("overall")),
        extraction=body.get("extraction"),
        notes=body.get("notes"),
    )

    # Build adjusted recipe
    base_recipe = json.loads(session.recipe_json) if session.recipe_json else {}
    feedback_dict = {
        "acidity": feedback.acidity,
        "sweetness": feedback.sweetness,
        "bitterness": feedback.bitterness,
        "body": feedback.body,
        "overall": feedback.overall,
        "extraction": feedback.extraction,
    }
    adjusted = adjust_recipe_from_feedback(base_recipe, feedback_dict)
    feedback.adjusted_recipe_json = json.dumps(adjusted)

    # Update session recipe to adjusted version for future reference
    session.recipe_json = json.dumps(adjusted)

    db.session.add(feedback)
    db.session.commit()

    return jsonify(
        {"feedback_id": feedback.id, "adjusted_recipe": adjusted}
    ), 201


# ---------------------------------------------------------------------------
# API – sessions
# ---------------------------------------------------------------------------


@main.route("/api/sessions", methods=["GET"])
def api_list_sessions():
    """List all brewing sessions (newest first)."""
    sessions = CoffeeSession.query.order_by(CoffeeSession.created_at.desc()).all()
    return jsonify([s.to_dict() for s in sessions]), 200


@main.route("/api/sessions/<int:session_id>", methods=["GET"])
def api_get_session(session_id):
    """Get a single brewing session by id."""
    session = db.session.get(CoffeeSession, session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session.to_dict()), 200
