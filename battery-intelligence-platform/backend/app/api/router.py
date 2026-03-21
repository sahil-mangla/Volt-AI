from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database.session import get_db
from app.models import domain
from app.schemas.payloads import PredictionResponse, CycleData, BatterySummary, AlertResponse, MaintenanceRequest, MaintenanceResponse
from app.ml.ml_service import ml_service
from app.utils.logger import log_prediction, log_alert, log_maintenance, log_error

router = APIRouter()

@router.post("/predict", response_model=PredictionResponse)
def predict_battery_health(data: CycleData, db: Session = Depends(get_db)):
    """
    Analyzes a single charge/discharge cycle array and returns predictions.
    Saves the prediction to the database.
    """
    try:
        # 1. Feature Engineering
        cycle_dict = {
            "time": data.time,
            "voltage": data.voltage,
            "current": data.current,
            "temperature": data.temperature
        }
        features = ml_service.perform_feature_engineering(cycle_dict)
        
        # 2. ML Prediction
        results = ml_service.predict_health_and_rul(features)
        
        status_str = "HEALTHY"
        is_critical = False
        recommendation = "Normal operation."
        
        if results["health_score"] < 70 or results["rul_cycles"] < 20:
            status_str = "CRITICAL"
            is_critical = True
            recommendation = "Schedule immediate replacement."
        elif results["health_score"] < 85 or results["rul_cycles"] < 50:
            status_str = "WARNING"
            recommendation = "Plan maintenance check within 30 days."

        # 3. Save to DB (Ensure battery exists first)
        battery = db.query(domain.Battery).filter(domain.Battery.id == data.battery_id).first()
        if not battery:
            # Create battery stub if it doesn't exist
            battery = domain.Battery(id=data.battery_id, capacity=features.get("capacity", 2.0), status=status_str)
            db.add(battery)
            db.commit()

        # Save Prediction
        prediction_db = domain.Prediction(
            battery_id=data.battery_id,
            cycle=data.cycle_id,
            health_score=results["health_score"],
            rul_cycles=results["rul_cycles"],
            failure_risk=results["failure_risk"]
        )
        db.add(prediction_db)
        
        # Update Battery status
        battery.status = status_str
        
        # Generate Alert if necessary
        if is_critical and status_str == "CRITICAL":
            alert = domain.Alert(
                battery_id=data.battery_id,
                severity=status_str,
                message=f"Critical health drop detected during cycle {data.cycle_id}."
            )
            db.add(alert)
            log_alert(data.battery_id, status_str, alert.message)
            
        db.commit()
        
        # Logging
        log_prediction(data.battery_id, data.cycle_id, results["health_score"], results["rul_cycles"], results["failure_risk"])

        return {
            "battery_id": data.battery_id,
            "cycle": data.cycle_id,
            "health_score": results["health_score"],
            "rul_cycles": results["rul_cycles"],
            "failure_risk": results["failure_risk"],
            "status": status_str,
            "is_critical": is_critical,
            "recommendation": recommendation
        }

    except Exception as e:
        log_error("Prediction Endpoint", str(e))
        raise HTTPException(status_code=500, detail="Prediction failed")

@router.post("/batteries")
def upload_battery_data(file_context: dict, db: Session = Depends(get_db)):
    """ Placeholder for CSV/JSON dataset bulk upload process """
    return {"status": "success", "message": "File processed (Mocked upload endpoint)"}

@router.get("/batteries", response_model=List[BatterySummary])
def get_fleet_summary(db: Session = Depends(get_db)):
    """ Returns summary for all batteries active in the system """
    batteries = db.query(domain.Battery).all()
    summary = []
    for b in batteries:
        # Find latest prediction
        latest_pred = db.query(domain.Prediction).filter(domain.Prediction.battery_id == b.id).order_by(domain.Prediction.cycle.desc()).first()
        health = latest_pred.health_score if latest_pred else 100.0
        rul = latest_pred.rul_cycles if latest_pred else 1000.0
        
        summary.append({
            "id": b.id,
            "health": health,
            "rul": rul,
            "status": b.status,
            "model_type": b.model_type
        })
    return summary

@router.get("/batteries/{id}")
def get_battery_details(id: str, db: Session = Depends(get_db)):
    """ Detailed history of a specific battery id """
    battery = db.query(domain.Battery).filter(domain.Battery.id == id).first()
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
        
    predictions = db.query(domain.Prediction).filter(domain.Prediction.battery_id == id).order_by(domain.Prediction.cycle.asc()).all()
    
    return {
        "id": battery.id,
        "status": battery.status,
        "history": [
            {
                "cycle": p.cycle,
                "health_score": p.health_score,
                "rul_cycles": p.rul_cycles,
                "failure_risk": p.failure_risk
            } for p in predictions
        ]
    }

@router.get("/alerts", response_model=List[AlertResponse])
def get_active_alerts(db: Session = Depends(get_db)):
    """ List unresolved safety or maintenance alerts """
    alerts = db.query(domain.Alert).filter(domain.Alert.is_resolved == False).order_by(domain.Alert.created_at.desc()).all()
    return alerts

@router.post("/maintenance/create", response_model=MaintenanceResponse)
def create_maintenance_order(request: MaintenanceRequest, db: Session = Depends(get_db)):
    """ Generate a maintenance ticket and mark battery as MAINTENANCE """
    battery = db.query(domain.Battery).filter(domain.Battery.id == request.battery_id).first()
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
        
    order = domain.MaintenanceOrder(
        battery_id=request.battery_id,
        priority=request.priority,
        notes=request.notes
    )
    db.add(order)
    
    # Update status safely
    battery.status = "MAINTENANCE"
    
    # Resolve related alerts automatically on dispatch
    alerts = db.query(domain.Alert).filter(domain.Alert.battery_id == request.battery_id, domain.Alert.is_resolved == False).all()
    for alert in alerts:
        alert.is_resolved = True
        
    db.commit()
    db.refresh(order)
    
    log_maintenance(request.battery_id, request.priority)
    
    return {
        "id": order.id,
        "battery_id": order.battery_id,
        "priority": order.priority,
        "status": order.status,
        "message": f"Work order {order.id} generated."
    }
