"""Integration tests for the Flask API routes."""

import io
import json

import pytest
from PIL import Image


def _make_jpeg_bytes():
    """Create a tiny JPEG image in memory and return its bytes."""
    img = Image.new("RGB", (20, 20), color=(180, 120, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------------

class TestIndex:
    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Coffee Brewing Assistant" in resp.data


# ---------------------------------------------------------------------------
# /api/analyze-label
# ---------------------------------------------------------------------------

class TestAnalyzeLabel:
    def test_analyse_label_missing_image_returns_400(self, client):
        resp = client.post("/api/analyze-label")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_analyse_label_with_image_returns_200(self, client):
        resp = client.post(
            "/api/analyze-label",
            data={"label_image": (io.BytesIO(_make_jpeg_bytes()), "label.jpg")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "session_id" in data
        assert "coffee_info" in data
        assert isinstance(data["session_id"], int)

    def test_analyse_label_creates_session(self, client):
        resp = client.post(
            "/api/analyze-label",
            data={"label_image": (io.BytesIO(_make_jpeg_bytes()), "label.jpg")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        session_id = resp.get_json()["session_id"]

        # Verify session exists
        resp2 = client.get(f"/api/sessions/{session_id}")
        assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# /api/analyze-beans
# ---------------------------------------------------------------------------

class TestAnalyzeBeans:
    def _create_session(self, client):
        resp = client.post(
            "/api/analyze-label",
            data={"label_image": (io.BytesIO(_make_jpeg_bytes()), "label.jpg")},
            content_type="multipart/form-data",
        )
        return resp.get_json()["session_id"]

    def test_analyse_beans_missing_image_returns_400(self, client):
        session_id = self._create_session(client)
        resp = client.post(
            "/api/analyze-beans",
            data={"session_id": session_id},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_analyse_beans_missing_session_id_returns_400(self, client):
        resp = client.post(
            "/api/analyze-beans",
            data={"bean_image": (io.BytesIO(_make_jpeg_bytes()), "beans.jpg")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_analyse_beans_invalid_session_returns_404(self, client):
        resp = client.post(
            "/api/analyze-beans",
            data={
                "bean_image": (io.BytesIO(_make_jpeg_bytes()), "beans.jpg"),
                "session_id": "99999",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 404

    def test_analyse_beans_returns_recipe(self, client):
        session_id = self._create_session(client)
        resp = client.post(
            "/api/analyze-beans",
            data={
                "bean_image": (io.BytesIO(_make_jpeg_bytes()), "beans.jpg"),
                "session_id": str(session_id),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "bean_analysis" in data
        assert "recipe" in data
        assert data["recipe"]["coffee_g"] > 0


# ---------------------------------------------------------------------------
# /api/analyze-grounds
# ---------------------------------------------------------------------------

class TestAnalyzeGrounds:
    def _create_session_with_beans(self, client):
        resp = client.post(
            "/api/analyze-label",
            data={"label_image": (io.BytesIO(_make_jpeg_bytes()), "label.jpg")},
            content_type="multipart/form-data",
        )
        session_id = resp.get_json()["session_id"]
        client.post(
            "/api/analyze-beans",
            data={
                "bean_image": (io.BytesIO(_make_jpeg_bytes()), "beans.jpg"),
                "session_id": str(session_id),
            },
            content_type="multipart/form-data",
        )
        return session_id

    def test_analyse_grounds_returns_200(self, client):
        session_id = self._create_session_with_beans(client)
        resp = client.post(
            "/api/analyze-grounds",
            data={
                "grounds_image": (io.BytesIO(_make_jpeg_bytes()), "grounds.jpg"),
                "session_id": str(session_id),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ground_analysis" in data
        assert "recipe" in data


# ---------------------------------------------------------------------------
# /api/recipe/<session_id>
# ---------------------------------------------------------------------------

class TestGetRecipe:
    def test_get_recipe_not_found(self, client):
        resp = client.get("/api/recipe/99999")
        assert resp.status_code == 404

    def test_get_recipe_after_label(self, client):
        resp = client.post(
            "/api/analyze-label",
            data={"label_image": (io.BytesIO(_make_jpeg_bytes()), "label.jpg")},
            content_type="multipart/form-data",
        )
        session_id = resp.get_json()["session_id"]
        resp2 = client.get(f"/api/recipe/{session_id}")
        assert resp2.status_code == 200
        data = resp2.get_json()
        assert "recipe" in data
        recipe = data["recipe"]
        assert recipe["coffee_g"] == 15.0  # default dose


# ---------------------------------------------------------------------------
# /api/feedback
# ---------------------------------------------------------------------------

class TestFeedback:
    def _create_session(self, client):
        resp = client.post(
            "/api/analyze-label",
            data={"label_image": (io.BytesIO(_make_jpeg_bytes()), "label.jpg")},
            content_type="multipart/form-data",
        )
        return resp.get_json()["session_id"]

    def test_feedback_missing_session_id_returns_400(self, client):
        resp = client.post(
            "/api/feedback",
            json={"extraction": "balanced"},
        )
        assert resp.status_code == 400

    def test_feedback_invalid_session_returns_404(self, client):
        resp = client.post(
            "/api/feedback",
            json={"session_id": 99999, "extraction": "balanced"},
        )
        assert resp.status_code == 404

    def test_feedback_returns_adjusted_recipe(self, client):
        session_id = self._create_session(client)
        resp = client.post(
            "/api/feedback",
            json={
                "session_id": session_id,
                "extraction": "over",
                "acidity": 2,
                "sweetness": 3,
                "bitterness": 5,
                "body": 3,
                "overall": 2,
                "notes": "Too bitter",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "adjusted_recipe" in data
        assert "adjustments_made" in data["adjusted_recipe"]

    def test_feedback_over_extraction_coarsens_grind(self, client):
        session_id = self._create_session(client)
        # Get base recipe first
        base_resp = client.get(f"/api/recipe/{session_id}")
        base_clicks = base_resp.get_json()["recipe"]["grind_clicks"]

        resp = client.post(
            "/api/feedback",
            json={
                "session_id": session_id,
                "extraction": "over",
                "bitterness": 5,
            },
        )
        adjusted = resp.get_json()["adjusted_recipe"]
        assert adjusted["grind_clicks"] > base_clicks


# ---------------------------------------------------------------------------
# /api/sessions
# ---------------------------------------------------------------------------

class TestSessions:
    def test_list_sessions_returns_list(self, client):
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_session_appears_in_list_after_label(self, client):
        resp = client.post(
            "/api/analyze-label",
            data={"label_image": (io.BytesIO(_make_jpeg_bytes()), "label.jpg")},
            content_type="multipart/form-data",
        )
        session_id = resp.get_json()["session_id"]
        list_resp = client.get("/api/sessions")
        ids = [s["id"] for s in list_resp.get_json()]
        assert session_id in ids

    def test_get_session_not_found(self, client):
        resp = client.get("/api/sessions/99999")
        assert resp.status_code == 404

    def test_get_session_returns_full_data(self, client):
        resp = client.post(
            "/api/analyze-label",
            data={"label_image": (io.BytesIO(_make_jpeg_bytes()), "label.jpg")},
            content_type="multipart/form-data",
        )
        session_id = resp.get_json()["session_id"]
        data = client.get(f"/api/sessions/{session_id}").get_json()
        assert data["id"] == session_id
        assert "feedback" in data
        assert isinstance(data["feedback"], list)
