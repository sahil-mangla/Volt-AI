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


def get_ml_progress(db: Session):
    """
    Calculates ML recompute progress metrics.
    """
    from sqlalchemy import func, distinct

    total_batteries = db.query(func.count(distinct(domain.Battery.id))).scalar() or 0
    batteries_with_predictions = db.query(func.count(distinct(domain.BatteryPrediction.battery_id))).scalar() or 0

    remaining = total_batteries - batteries_with_predictions
    progress_percent = (batteries_with_predictions / total_batteries * 100) if total_batteries > 0 else 100.0

    return {
        "total_batteries": total_batteries,
        "batteries_with_predictions": batteries_with_predictions,
        "batteries_remaining": remaining,
        "progress_percent": round(progress_percent, 2)
    }
