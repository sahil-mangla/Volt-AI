from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import domain


def get_latest_predictions_query(db: Session):
    """
    Returns a SQLAlchemy Query object scoped to exactly one row per battery_id —
    the row with the highest id (most recently inserted prediction).

    Uses an IN subquery rather than a JOIN to avoid ORM ambiguity when multiple
    rows share the same created_at timestamp (common after bulk inserts).

    Usage:
        latest_preds = get_latest_predictions_query(db).all()
    """
    max_ids_subq = (
        db.query(func.max(domain.BatteryPrediction.id))
        .group_by(domain.BatteryPrediction.battery_id)
        .scalar_subquery()
    )

    return db.query(domain.BatteryPrediction).filter(
        domain.BatteryPrediction.id.in_(max_ids_subq)
    )
