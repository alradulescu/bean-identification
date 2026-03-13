"""Database models for the Coffee Brewing Assistant."""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class CoffeeSession(db.Model):
    """Stores a single coffee brewing session with all extracted information."""

    __tablename__ = "coffee_sessions"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Label-extracted information
    origin = db.Column(db.String(128))
    species = db.Column(db.String(64))
    masl = db.Column(db.Integer)
    roast_level = db.Column(db.String(32))
    roast_date = db.Column(db.String(32))
    tasting_notes = db.Column(db.String(256))
    producer = db.Column(db.String(128))
    process = db.Column(db.String(64))
    decaf_status = db.Column(db.String(16))

    # Bean analysis
    bean_color = db.Column(db.String(64))
    bean_size = db.Column(db.String(32))
    bean_uniformity = db.Column(db.String(32))
    bean_density_estimate = db.Column(db.String(32))
    bean_analysis_notes = db.Column(db.Text)

    # Ground coffee analysis
    particle_size_distribution = db.Column(db.String(32))
    fines_percentage = db.Column(db.String(16))
    grind_uniformity = db.Column(db.String(32))
    ground_analysis_notes = db.Column(db.Text)

    # Recommended recipe (stored as JSON string)
    recipe_json = db.Column(db.Text)

    # Relationships
    feedback = db.relationship(
        "BrewingFeedback", backref="session", lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self):
        import json

        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "origin": self.origin,
            "species": self.species,
            "masl": self.masl,
            "roast_level": self.roast_level,
            "roast_date": self.roast_date,
            "tasting_notes": self.tasting_notes,
            "producer": self.producer,
            "process": self.process,
            "decaf_status": self.decaf_status,
            "bean_color": self.bean_color,
            "bean_size": self.bean_size,
            "bean_uniformity": self.bean_uniformity,
            "bean_density_estimate": self.bean_density_estimate,
            "bean_analysis_notes": self.bean_analysis_notes,
            "particle_size_distribution": self.particle_size_distribution,
            "fines_percentage": self.fines_percentage,
            "grind_uniformity": self.grind_uniformity,
            "ground_analysis_notes": self.ground_analysis_notes,
            "recipe": json.loads(self.recipe_json) if self.recipe_json else None,
            "feedback": [f.to_dict() for f in self.feedback],
        }


class BrewingFeedback(db.Model):
    """Stores taste feedback for a brewing session."""

    __tablename__ = "brewing_feedback"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("coffee_sessions.id"), nullable=False
    )
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Taste attributes (1-5 scale)
    acidity = db.Column(db.Integer)  # 1=flat, 5=bright/acidic
    sweetness = db.Column(db.Integer)  # 1=lacking, 5=very sweet
    bitterness = db.Column(db.Integer)  # 1=none, 5=very bitter
    body = db.Column(db.Integer)  # 1=thin, 5=heavy
    overall = db.Column(db.Integer)  # 1=poor, 5=excellent

    # Extraction assessment
    extraction = db.Column(
        db.String(16)
    )  # "under", "over", "balanced"
    notes = db.Column(db.Text)

    # Adjusted recipe after feedback
    adjusted_recipe_json = db.Column(db.Text)

    def to_dict(self):
        import json

        return {
            "id": self.id,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "acidity": self.acidity,
            "sweetness": self.sweetness,
            "bitterness": self.bitterness,
            "body": self.body,
            "overall": self.overall,
            "extraction": self.extraction,
            "notes": self.notes,
            "adjusted_recipe": (
                json.loads(self.adjusted_recipe_json)
                if self.adjusted_recipe_json
                else None
            ),
        }
