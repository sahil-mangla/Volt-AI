from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import pandas as pd
import io

from app.services.blob_service import blob_service

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
    """ Placeholder for manual JSON dataset bulk upload process """
    return {"status": "success", "message": "File processed (Mocked upload endpoint)"}

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """ Uploads a CSV stream securely to the Azure Blob Container natively """
    try:
        url = await blob_service.upload_file(file)
        return {"filename": file.filename, "url": url}
    except Exception as e:
        log_error("Blob Upload", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files")
def list_files():
    """ Returns index of telemetry datasets resting in the Blob container """
    try:
        return blob_service.list_files()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def __process_blob_csv(filename: str, db: Session) -> int:
    """ Core ingestion logic cleanly decoupled """
    csv_bytes = blob_service.download_file_to_bytes(filename)
    df = pd.read_csv(io.BytesIO(csv_bytes))
    
    records_inserted = 0
    
    for _, row in df.iterrows():
        bat_id = str(row.get("battery_id", f"BATT_{filename}"))
        cycle = int(row.get("cycle", 1))
        capacity = float(row.get("capacity", 2.0))
        health_score = float(row.get("health_score", 100.0))
        rul_cycles = float(row.get("rul_cycles", 1000.0))
        
        # Map physical database object constraints
        battery = db.query(domain.Battery).filter(domain.Battery.id == bat_id).first()
        if not battery:
            battery = domain.Battery(id=bat_id, capacity=capacity, status="HEALTHY")
            db.add(battery)
            db.commit()
            
        prediction = domain.Prediction(
            battery_id=bat_id,
            cycle=cycle,
            health_score=health_score,
            rul_cycles=rul_cycles,
            failure_risk=0.0
        )
        db.add(prediction)
        records_inserted += 1
        
    # Vectorially compute and update BatterySummary limits accurately
    if not df.empty:
        bat_id_summary = str(df.iloc[0].get("battery_id", f"BATT_{filename}"))
        avg_health = float(df["health_score"].mean()) if "health_score" in df.columns else 100.0
        max_cycles = int(df["cycle"].max()) if "cycle" in df.columns else len(df)
        failure_risk = float(df["failure_risk"].mean()) if "failure_risk" in df.columns else 0.0

        summary = db.query(domain.BatterySummary).filter(domain.BatterySummary.battery_id == bat_id_summary).first()
        if summary:
            summary.avg_health = avg_health
            summary.max_cycles = max_cycles
            summary.failure_risk = failure_risk
        else:
            summary = domain.BatterySummary(
                battery_id=bat_id_summary,
                avg_health=avg_health,
                max_cycles=max_cycles,
                failure_risk=failure_risk
            )
            db.add(summary)
            
    db.commit()
    return records_inserted


@router.post("/process/{filename}")
def process_file(filename: str, db: Session = Depends(get_db)):
    """ Specific single-file processing via native HTTP trigger """
    try:
        records_inserted = __process_blob_csv(filename, db)
        return {
            "status": "success",
            "message": f"Successfully processed {filename}",
            "records_inserted": records_inserted
        }
    except Exception as e:
        log_error("Blob Processing", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process CSV: {e}")

@router.post("/process-all")
def process_all_files(db: Session = Depends(get_db)):
    """ Triggers a bulk array crawl processing all valid CSV files resting statically within Azure Blob Container """
    try:
        files = blob_service.list_files()
        
        files_processed = 0
        total_records_inserted = 0
        failed_files = []
        
        for f in files:
            filename = f.get("name", "")
            if filename.endswith(".csv"):
                try:
                    records = __process_blob_csv(filename, db)
                    total_records_inserted += records
                    files_processed += 1
                except Exception as file_err:
                    log_error(f"Bulk Process Failed on {filename}", str(file_err))
                    failed_files.append(filename)
                    
        return {
            "status": "success",
            "files_processed": files_processed,
            "records_inserted": total_records_inserted,
            "failed_files": failed_files
        }
    except Exception as e:
        log_error("Bulk Process Master Thread", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/batteries", response_model=List[BatterySummary])
def get_fleet_summary(limit: int = 50, db: Session = Depends(get_db)):
    """ Returns paginated fleet summary mapped natively to BatterySummary calculations """
    summaries = db.query(domain.BatterySummary).limit(limit).all()
    
    result = []
    for s in summaries:
        b = db.query(domain.Battery).filter(domain.Battery.id == s.battery_id).first()
        result.append({
            "id": s.battery_id,
            "health": round(s.avg_health, 2),
            "rul": max(0.0, float(1000 - s.max_cycles)),
            "status": b.status if b else "HEALTHY",
            "model_type": b.model_type if b else "Linear"
        })
    return result

@router.get("/fleet/summary")
def get_fleet_statistics(db: Session = Depends(get_db)):
    """ Calculates overall generic fleet summary natively aggregated within the database dimension """
    summaries = db.query(domain.BatterySummary).all()
    total_batteries = len(summaries)
    
    if total_batteries == 0:
        return {"avg_health": 0, "predicted_failures": 0, "total_batteries": 0}
        
    total_health = sum(s.avg_health for s in summaries)
    predicted_failures = sum(1 for s in summaries if s.avg_health < 70)
            
    avg_health = round(total_health / total_batteries)
    
    return {
        "avg_health": avg_health,
        "predicted_failures": predicted_failures,
        "total_batteries": total_batteries
    }

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
