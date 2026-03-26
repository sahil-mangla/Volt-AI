from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import pandas as pd
import io

from app.services.blob_service import blob_service

import threading
import time
from app.database.session import get_db, SessionLocal, engine
from app.models import domain
from app.schemas.payloads import PredictionResponse, CycleData, BatterySummary, AlertResponse, MaintenanceRequest, MaintenanceResponse, ModelSelectRequest
from app.features.extractor import extract_features
from app.ml_engine.engine import model_engine
from app.utils.logger import log_prediction, log_alert, log_maintenance, log_error
from app.api.analytics import get_latest_predictions_query, get_ml_progress

router = APIRouter()

@router.get("/init-db", response_model=None)
def initialize_database_schema():
    """ 
    Manually triggers SQLAlchemy Base.metadata.create_all.
    Use this once after deployment to ensure tables exist.
    """
    try:
        from app.database.session import engine, Base
        from app.models import domain
        Base.metadata.create_all(bind=engine)
        return {"status": "success", "message": "Database tables created/verified successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database initialization failed: {e}")

@router.post("/predict", response_model=None)
def predict_battery_health(data: CycleData, db: Session = Depends(get_db)):
    """
    Analyzes a single charge/discharge cycle array and returns predictions.
    Saves the prediction to the database.
    """
    try:
        # Get selected model
        setting = db.query(domain.ModelSetting).first()
        selected_model = setting.selected_model if setting else "physics_model"

        # 1. Feature Engineering
        cycle_dict = {
            "time": data.time,
            "voltage": data.voltage,
            "current": data.current,
            "temperature": data.temperature
        }
        features = extract_features(cycle_dict, data.cycle_id)
        
        # 2. ML Prediction
        results = model_engine.predict(features, selected_model)
        
        status_str = "HEALTHY"
        is_critical = False
        recommendation = "Normal operation."
        
        if results["health_score"] < 70 or results["failure_probability"] > 0.8:
            status_str = "CRITICAL"
            is_critical = True
            recommendation = "Schedule immediate replacement."
        elif results["health_score"] < 85 or results["failure_probability"] > 0.4:
            status_str = "WARNING"
            recommendation = "Plan maintenance check within 30 days."

        # 3. Save to DB (Ensure battery exists first)
        battery = db.query(domain.Battery).filter(domain.Battery.id == data.battery_id).first()
        if not battery:
            # Create battery stub if it doesn't exist
            battery = domain.Battery(id=data.battery_id, capacity=features.get("capacity", 2.0), status=status_str)
            db.add(battery)
            db.commit()

        # Save feature to BatteryFeature
        bat_feature = domain.BatteryFeature(
            battery_id=data.battery_id,
            cycle=data.cycle_id,
            cycle_count=features.get("cycle_count"),
            avg_voltage=features.get("avg_voltage"),
            max_voltage=features.get("max_voltage"),
            min_voltage=features.get("min_voltage"),
            avg_current=features.get("avg_current"),
            avg_temperature=features.get("avg_temperature"),
            capacity_fade=features.get("capacity_fade"),
            internal_resistance=features.get("internal_resistance"),
            charge_time=features.get("charge_time"),
            discharge_time=features.get("discharge_time"),
            energy_efficiency=features.get("energy_efficiency"),
            voltage_variance=features.get("voltage_variance"),
            temperature_variance=features.get("temperature_variance"),
            current_variance=features.get("current_variance"),
            capacity_ah=features.get("capacity_ah"),
            energy_throughput=features.get("energy_throughput")
        )
        db.add(bat_feature)

        # Save Prediction
        prediction_db = domain.BatteryPrediction(
            battery_id=data.battery_id,
            cycle=data.cycle_id,
            model_name=selected_model,
            health_score=results["health_score"],
            remaining_cycles=results["remaining_cycles"],
            remaining_days=results["remaining_days"],
            failure_probability=results["failure_probability"]
        )
        db.add(prediction_db)
        
        # Update Battery status
        battery.status = status_str
        
        # Generate Alert if necessary
        if is_critical and status_str == "CRITICAL":
            alert = domain.Alert(
                battery_id=data.battery_id,
                severity=status_str,
                message=f"Critical health drop detected by {selected_model} during cycle {data.cycle_id}."
            )
            db.add(alert)
            log_alert(data.battery_id, status_str, alert.message)
            
        db.commit()
        
        # Logging
        log_prediction(data.battery_id, data.cycle_id, results["health_score"], results["remaining_cycles"], results["failure_probability"])

        return {
            "battery_id": data.battery_id,
            "cycle": data.cycle_id,
            "health_score": results["health_score"],
            "rul_cycles": results["remaining_cycles"],
            "failure_risk": results["failure_probability"],
            "status": status_str,
            "is_critical": is_critical,
            "recommendation": recommendation
        }

    except Exception as e:
        log_error("Prediction Endpoint", str(e))
        raise HTTPException(status_code=500, detail="Prediction failed")

@router.post("/batteries", response_model=None)
def upload_battery_data(file_context: dict, db: Session = Depends(get_db)):
    """ Placeholder for manual JSON dataset bulk upload process """
    return {"status": "success", "message": "File processed (Mocked upload endpoint)"}

@router.post("/upload", response_model=None)
async def upload_file(file: UploadFile = File(...)):
    """ Uploads a CSV stream securely to the Azure Blob Container natively """
    try:
        url = await blob_service.upload_file(file)
        return {"filename": file.filename, "url": url}
    except Exception as e:
        log_error("Blob Upload", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files", response_model=None)
def list_files():
    """ Returns index of telemetry datasets resting in the Blob container """
    try:
        return blob_service.list_files()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def __process_blob_csv(filename: str, db: Session) -> int:
    """ Core ingestion logic cleanly decoupled using new ML pipeline """
    from sqlalchemy import func
    csv_bytes = blob_service.download_file_to_bytes(filename)
    df = pd.read_csv(io.BytesIO(csv_bytes))
    
    records_inserted = 0
    
    # Get selected model
    setting = db.query(domain.ModelSetting).first()
    selected_model = setting.selected_model if setting else "physics_model"

    for _, row in df.iterrows():
        bat_id = str(row.get("battery_id", f"BATT_{filename}"))
        cycle = int(row.get("cycle", 1))
        capacity = float(row.get("capacity", 2.0))
        
        # Map physical database object constraints
        battery = db.query(domain.Battery).filter(domain.Battery.id == bat_id).first()
        if not battery:
            battery = domain.Battery(id=bat_id, capacity=capacity, status="HEALTHY")
            db.add(battery)
            db.commit()
            
        # Feature Extraction
        cycle_dict = {
            "time": [0.0, 3600.0],
            "voltage": [float(row.get("voltage", 3.7)), float(row.get("voltage", 3.7))],
            "current": [float(row.get("current", 1.5)), float(row.get("current", -1.5))],
            "temperature": [float(row.get("temperature", 25.0)), float(row.get("temperature", 25.0))]
        }
        features = extract_features(cycle_dict, cycle)
        
        bat_feat = domain.BatteryFeature(
            battery_id=bat_id,
            cycle=cycle,
            cycle_count=features.get("cycle_count"),
            avg_voltage=features.get("avg_voltage"),
            max_voltage=features.get("max_voltage"),
            min_voltage=features.get("min_voltage"),
            avg_current=features.get("avg_current"),
            avg_temperature=features.get("avg_temperature"),
            capacity_fade=features.get("capacity_fade"),
            internal_resistance=features.get("internal_resistance"),
            charge_time=features.get("charge_time"),
            discharge_time=features.get("discharge_time"),
            energy_efficiency=features.get("energy_efficiency"),
            voltage_variance=features.get("voltage_variance"),
            temperature_variance=features.get("temperature_variance"),
            current_variance=features.get("current_variance"),
            capacity_ah=features.get("capacity_ah"),
            energy_throughput=features.get("energy_throughput")
        )
        db.add(bat_feat)

        # ML Prediction
        results = model_engine.predict(features, selected_model)

        prediction_db = domain.BatteryPrediction(
            battery_id=bat_id,
            cycle=cycle,
            model_name=selected_model,
            health_score=results["health_score"],
            remaining_cycles=results["remaining_cycles"],
            remaining_days=results["remaining_days"],
            failure_probability=results["failure_probability"]
        )
        db.add(prediction_db)

        # Alerting
        if results["failure_probability"] > 0.8:
            alert = domain.Alert(
                battery_id=bat_id,
                severity="CRITICAL",
                message=f"Critical failure probability detected by {selected_model} during cycle {cycle}."
            )
            db.add(alert)
            battery.status = "CRITICAL"
            
        records_inserted += 1
        
    # Vectorially compute and update BatterySummary limits accurately
    if not df.empty:
        bat_id_summary = str(df.iloc[0].get("battery_id", f"BATT_{filename}"))
        
        recent_preds = db.query(domain.BatteryPrediction).filter(domain.BatteryPrediction.battery_id == bat_id_summary).order_by(domain.BatteryPrediction.cycle.desc()).limit(1).first()
        
        avg_health = recent_preds.health_score if recent_preds else 100.0
        max_cycles = recent_preds.cycle if recent_preds else 1
        failure_risk = recent_preds.failure_probability if recent_preds else 0.0

        summary = db.query(domain.BatterySummary).filter(domain.BatterySummary.battery_id == bat_id_summary).first()
        if summary:
            summary.avg_health = avg_health
            summary.max_cycles = max_cycles
            summary.failure_risk = failure_risk
            summary.last_updated = func.now()
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


@router.post("/process/{filename}", response_model=None)
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

@router.post("/process-all", response_model=None)
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

@router.post("/process-batch", response_model=None)
def process_batch_files(batch_size: int = 50, db: Session = Depends(get_db)):
    """ Triggers a bulk array crawl processing a limited batch of valid CSV files sequentially resolving Azure Gateway timeouts """
    try:
        files = blob_service.list_files()
        
        # Intercept and aggregate historically processed blobs efficiently via SQL set maps
        processed_records = db.query(domain.ProcessedFile.filename).all()
        processed_set = {r[0] for r in processed_records}
        
        unprocessed_files = [
            f.get("name", "") for f in files 
            if f.get("name", "").endswith(".csv") and f.get("name", "") not in processed_set
        ]
        
        batch_files = unprocessed_files[:batch_size]
        
        files_processed = 0
        total_records_inserted = 0
        
        for filename in batch_files:
            try:
                # Reuse underlying cleanly abstracted ML loops 
                records = __process_blob_csv(filename, db)
                total_records_inserted += records
                files_processed += 1
                
                # Flag database array bounds
                db.add(domain.ProcessedFile(filename=filename))
                db.commit()
            except Exception as file_err:
                log_error(f"Batch Process Failed on {filename}", str(file_err))
                db.rollback() 
                
        return {
            "status": "success",
            "files_processed": files_processed,
            "records_inserted": total_records_inserted,
            "remaining_files": len(unprocessed_files) - files_processed
        }
    except Exception as e:
        log_error("Batch Process Master Thread", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/batteries", response_model=None)
def get_fleet_summary(limit: int = 50, db: Session = Depends(get_db)):
    """ Returns paginated fleet summary mapped natively to BatterySummary calculations """
    summaries = db.query(domain.BatterySummary).order_by(domain.BatterySummary.last_updated.desc()).limit(limit).all()
    
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

@router.get("/fleet/summary", response_model=None)
def get_fleet_statistics(db: Session = Depends(get_db)):
    """ Calculates fleet summary dynamically from the latest ML prediction per battery """
    latest_preds = get_latest_predictions_query(db).all()
    total_batteries = len(latest_preds)

    if total_batteries == 0:
        return {"avg_health": 0, "predicted_failures": 0, "total_batteries": 0}
    
    avg_health = round(sum(p.health_score for p in latest_preds) / total_batteries, 1)
    predicted_failures = sum(1 for p in latest_preds if p.failure_probability > 0.7)
    
    return {
        "avg_health": avg_health,
        "predicted_failures": predicted_failures,
        "total_batteries": total_batteries
    }

@router.get("/batteries/{id}", response_model=None)
def get_battery_details(id: str, db: Session = Depends(get_db)):
    """ Detailed history of a specific battery id """
    battery = db.query(domain.Battery).filter(domain.Battery.id == id).first()
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
        
    predictions = db.query(domain.BatteryPrediction).filter(domain.BatteryPrediction.battery_id == id).order_by(domain.BatteryPrediction.cycle.asc()).all()
    
    return {
        "id": battery.id,
        "status": battery.status,
        "history": [
            {
                "cycle": p.cycle,
                "health_score": p.health_score,
                "rul_cycles": p.remaining_cycles,
                "failure_risk": p.failure_probability
            } for p in predictions
        ]
    }

@router.get("/alerts", response_model=None)
def get_active_alerts(db: Session = Depends(get_db)):
    """ Lists at-risk batteries based on their latest ML prediction """
    latest_preds = (
        get_latest_predictions_query(db)
        .filter(
            (domain.BatteryPrediction.health_score < 70) |
            (domain.BatteryPrediction.failure_probability > 0.6)
        )
        .all()
    )
    
    results = []
    for p in latest_preds:
        status_str = "Critical" if p.health_score < 50 or p.failure_probability > 0.8 else "Warning"
        results.append({
            "battery_id": p.battery_id,
            "health": round(p.health_score, 1),
            "failure_risk": round(p.failure_probability, 2),
            "status": status_str
        })
        
    return results

@router.post("/maintenance/create", response_model=None)
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

@router.get("/debug/counts", response_model=None)
def get_debug_counts(db: Session = Depends(get_db)):
    """ Returns database row counts for debugging and integrity verification """
    from sqlalchemy import func, distinct

    unique_batteries = db.query(func.count(distinct(domain.Battery.id))).scalar()
    feature_records = db.query(func.count(domain.BatteryFeature.id)).scalar()
    prediction_records = db.query(func.count(domain.BatteryPrediction.id)).scalar()
    alert_records = db.query(func.count(domain.Alert.id)).scalar()
    
    # raw_records: count from legacy Prediction table
    raw_records = db.query(func.count(domain.Prediction.id)).scalar()

    return {
        "unique_batteries": unique_batteries,
        "raw_records": raw_records,
        "feature_records": feature_records,
        "prediction_records": prediction_records,
        "alert_records": alert_records
    }

@router.get("/debug/latest-count", response_model=None)
def get_debug_latest_count(db: Session = Depends(get_db)):
    """ Verifies that the latest-prediction query returns exactly one row per battery """
    latest_preds = get_latest_predictions_query(db).all()
    unique_ids = len(set(p.battery_id for p in latest_preds))
    return {
        "latest_prediction_rows": len(latest_preds),
        "unique_battery_ids": unique_ids
    }

@router.get("/debug/prediction-coverage", response_model=None)
def get_prediction_coverage(db: Session = Depends(get_db)):
    """ Checks how many batteries have prediction records vs total batteries """
    from sqlalchemy import func, distinct

    unique_batteries = db.query(func.count(distinct(domain.Battery.id))).scalar()
    batteries_with_predictions = db.query(func.count(distinct(domain.BatteryPrediction.battery_id))).scalar()
    prediction_records = db.query(func.count(domain.BatteryPrediction.id)).scalar()

    return {
        "unique_batteries": unique_batteries,
        "batteries_with_predictions": batteries_with_predictions,
        "batteries_without_predictions": unique_batteries - batteries_with_predictions,
        "prediction_records": prediction_records
    }

@router.get("/models", response_model=None)
def get_models():
    """ Returns a list of available ML models """
    return {"models": model_engine.available_models}

@router.post("/model/select", response_model=None)
def select_model(request: ModelSelectRequest, db: Session = Depends(get_db)):
    """ Selects which ML model to use for future predictions """
    if request.model_name not in model_engine.available_models:
        raise HTTPException(status_code=400, detail="Invalid model name")
        
    setting = db.query(domain.ModelSetting).first()
    if not setting:
        setting = domain.ModelSetting(selected_model=request.model_name)
        db.add(setting)
    else:
        setting.selected_model = request.model_name
    db.commit()
    return {"status": "success", "selected_model": request.model_name}

@router.get("/debug/db-url", response_model=None)
def get_db_url():
    """ Returns the active database URL for connection verification """
    return {"database_url": str(engine.url)}

@router.get("/predictions/{battery_id}", response_model=None)
def get_battery_predictions(battery_id: str, db: Session = Depends(get_db)):
    """ Returns history of predictions for a specific battery """
    predictions = db.query(domain.BatteryPrediction).filter(domain.BatteryPrediction.battery_id == battery_id).order_by(domain.BatteryPrediction.cycle.desc()).limit(100).all()
    return predictions

@router.get("/analytics/health-distribution", response_model=None)
def get_health_distribution(db: Session = Depends(get_db)):
    """ Groups batteries into health buckets based on their latest prediction """
    latest_preds = get_latest_predictions_query(db).all()
    bins = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for p in latest_preds:
        h = p.health_score
        if h <= 20: bins["0-20"] += 1
        elif h <= 40: bins["21-40"] += 1
        elif h <= 60: bins["41-60"] += 1
        elif h <= 80: bins["61-80"] += 1
        else: bins["81-100"] += 1
    return bins

@router.get("/analytics/failure-risk", response_model=None)
def get_failure_risk(db: Session = Depends(get_db)):
    """ Computes aggregate failure risk using the latest prediction per battery """
    latest_preds = get_latest_predictions_query(db).all()
    total = len(latest_preds)
    if total == 0: return {"average_risk": 0.0, "high_risk_count": 0}
    high_risk = sum(1 for p in latest_preds if p.failure_probability > 0.8)
    avg_risk = sum(p.failure_probability for p in latest_preds) / total
    return {"average_risk": round(avg_risk, 2), "high_risk_count": high_risk}

@router.get("/ml/progress", response_model=None)
def get_ml_recompute_progress(db: Session = Depends(get_db)):
    """ Returns current ML recompute progress metrics """
    return get_ml_progress(db)

def recompute_ml_internal(db: Session, batch_size: int = 50):
    """ Internal recompute logic reusable across endpoints and background threads """
    try:
        from sqlalchemy import func
        # Find all battery_ids that have no BatteryPrediction records yet
        subquery = db.query(domain.BatteryPrediction.battery_id)
        legacy_batteries = db.query(domain.Battery.id).filter(domain.Battery.id.notin_(subquery)).limit(batch_size).all()
        
        if not legacy_batteries:
            return {"status": "success", "message": "No legacy batteries pending recomputation.", "batteries_processed_this_batch": 0, "remaining": 0}
            
        setting = db.query(domain.ModelSetting).first()
        selected_model = setting.selected_model if setting else "physics_model"
        
        legacy_ids = [str(b.id) for b in legacy_batteries]
        processed_count = 0
        
        for bat_id in legacy_ids:
            # 1. Fetch the LATEST BatteryFeature record for this battery
            latest_feat = db.query(domain.BatteryFeature).filter(domain.BatteryFeature.battery_id == bat_id).order_by(domain.BatteryFeature.cycle.desc()).first()
            
            battery = db.query(domain.Battery).filter(domain.Battery.id == bat_id).first()
            
            if latest_feat:
                # Flow A: Use latest existing feature
                features = {
                    "cycle_count": latest_feat.cycle_count,
                    "avg_voltage": latest_feat.avg_voltage,
                    "max_voltage": latest_feat.max_voltage,
                    "min_voltage": latest_feat.min_voltage,
                    "avg_current": latest_feat.avg_current,
                    "avg_temperature": latest_feat.avg_temperature,
                    "capacity_fade": latest_feat.capacity_fade,
                    "internal_resistance": latest_feat.internal_resistance,
                    "charge_time": latest_feat.charge_time,
                    "discharge_time": latest_feat.discharge_time,
                    "energy_efficiency": latest_feat.energy_efficiency,
                    "voltage_variance": latest_feat.voltage_variance,
                    "temperature_variance": latest_feat.temperature_variance,
                    "current_variance": latest_feat.current_variance,
                    "capacity_ah": latest_feat.capacity_ah
                }
                results = model_engine.predict(features, selected_model)
                
                prediction_db = domain.BatteryPrediction(
                    battery_id=bat_id,
                    cycle=latest_feat.cycle,
                    model_name=selected_model,
                    health_score=results["health_score"],
                    remaining_cycles=results["remaining_cycles"],
                    remaining_days=results["remaining_days"],
                    failure_probability=results["failure_probability"]
                )
                db.add(prediction_db)
                
                if results["failure_probability"] > 0.8:
                    alert = domain.Alert(
                        battery_id=bat_id,
                        severity="CRITICAL",
                        message=f"Critical failure probability detected by {selected_model} during cycle {latest_feat.cycle}."
                    )
                    db.add(alert)
                    if battery:
                        battery.status = "CRITICAL"
            else:
                # Flow B: Fallback to latest legacy cycle simulation
                latest_legacy_cycle = db.query(domain.Prediction).filter(domain.Prediction.battery_id == bat_id).order_by(domain.Prediction.cycle.desc()).first()
                
                if not latest_legacy_cycle:
                    # Default if no legacy data either
                    latest_legacy_cycle = domain.Prediction(cycle=1, health_score=100.0, rul_cycles=1000.0, failure_risk=0.0)
                    
                # Simulate telemetry for the latest cycle only
                cycle_dict = {
                    "time": [0.0, 3600.0],
                    "voltage": [3.7 - (0.01 * latest_legacy_cycle.cycle), 3.7 - (0.01 * latest_legacy_cycle.cycle)], 
                    "current": [1.5, -1.5],
                    "temperature": [25.0 + (0.02 * latest_legacy_cycle.cycle), 25.0 + (0.02 * latest_legacy_cycle.cycle)]
                }
                features = extract_features(cycle_dict, latest_legacy_cycle.cycle)
                results = model_engine.predict(features, selected_model)
                
                # Save Feature (Manual mapping to avoid 'capacity' mismatch)
                bat_feat = domain.BatteryFeature(
                    battery_id=bat_id,
                    cycle=latest_legacy_cycle.cycle,
                    cycle_count=features["cycle_count"],
                    avg_voltage=features["avg_voltage"],
                    max_voltage=features["max_voltage"],
                    min_voltage=features["min_voltage"],
                    avg_current=features["avg_current"],
                    avg_temperature=features["avg_temperature"],
                    capacity_fade=features["capacity_fade"],
                    internal_resistance=features["internal_resistance"],
                    charge_time=features["charge_time"],
                    discharge_time=features["discharge_time"],
                    energy_efficiency=features["energy_efficiency"],
                    voltage_variance=features["voltage_variance"],
                    temperature_variance=features["temperature_variance"],
                    current_variance=features["current_variance"],
                    capacity_ah=features["capacity_ah"],
                    energy_throughput=features["energy_throughput"]
                )
                db.add(bat_feat)

                # Save Prediction
                prediction_db = domain.BatteryPrediction(
                    battery_id=bat_id,
                    cycle=latest_legacy_cycle.cycle,
                    model_name=selected_model,
                    health_score=results["health_score"],
                    remaining_cycles=results["remaining_cycles"],
                    remaining_days=results["remaining_days"],
                    failure_probability=results["failure_probability"]
                )
                db.add(prediction_db)
                
                if results["failure_probability"] > 0.8:
                    alert = domain.Alert(
                        battery_id=bat_id,
                        severity="CRITICAL",
                        message=f"Critical failure probability detected by {selected_model} during cycle {latest_legacy_cycle.cycle}."
                    )
                    db.add(alert)
                    if battery:
                        battery.status = "CRITICAL"
                        
            # Update specific summary boundary securely post telemetry loops
            recent_preds = db.query(domain.BatteryPrediction).filter(domain.BatteryPrediction.battery_id == bat_id).order_by(domain.BatteryPrediction.cycle.desc()).limit(1).first()
            if recent_preds:
                summary = db.query(domain.BatterySummary).filter(domain.BatterySummary.battery_id == bat_id).first()
                if summary:
                    summary.avg_health = recent_preds.health_score
                    summary.max_cycles = recent_preds.cycle
                    summary.failure_risk = recent_preds.failure_probability
                    summary.last_updated = func.now()
                else:
                    summary = domain.BatterySummary(
                        battery_id=bat_id,
                        avg_health=recent_preds.health_score,
                        max_cycles=recent_preds.cycle,
                        failure_risk=recent_preds.failure_probability
                    )
                    db.add(summary)
            
            processed_count += 1
            progress = get_ml_progress(db)
            print(f"Processing battery: {bat_id}")
            print(f"Remaining batteries: {progress['batteries_remaining']}")
            
            db.commit() # Commit natively per batched object structurally resolving timeouts
            
        progress = get_ml_progress(db)
        return {
            "status": "success", 
            "message": f"Successfully recomputed ML logic for {processed_count} batteries.",
            "batteries_processed_this_batch": processed_count,
            "total_batteries_with_predictions": progress["batteries_with_predictions"],
            "remaining": progress["batteries_remaining"],
            "progress_percent": progress["progress_percent"]
        }
    except Exception as e:
        log_error("Recompute ML Pipe", str(e))
        db.rollback()
        raise e

@router.post("/recompute-ml", response_model=None)
def recompute_ml(batch_size: int = 50, db: Session = Depends(get_db)):
    """ Synchronous endpoint to process a single batch of batteries """
    try:
        return recompute_ml_internal(db, batch_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def recompute_all_background(batch_size: int = 50):
    """ Background thread runner that processes all pending batteries with error resilience """
    try:
        print("ML recompute background worker started.")
        while True:
            # Create a fresh session per batch to prevent memory leaks and stale data
            db = SessionLocal()
            try:
                result = recompute_ml_internal(db, batch_size)
                remaining = result.get("remaining", 0)
                processed = result.get("batteries_processed_this_batch", 0)
                
                print(f"Processed batch ({processed} batteries). Remaining: {remaining}")
                
                if remaining == 0:
                    print("ML recompute completed.")
                    break
                
                # Throttle execution to prevent tight loop Resource exhaustion
                time.sleep(1)
            except Exception as batch_error:
                print(f"Error processing ML batch: {batch_error}")
                log_error("Background Recompute Batch", str(batch_error))
                time.sleep(5) # Wait longer on error to prevent tight failing loops
            finally:
                db.close()
    except Exception as e:
        log_error("Background Recompute Fatal", str(e))
        print(f"Background recompute worker encountered fatal error: {e}")

@router.post("/recompute-ml/all", response_model=None)
def recompute_all_ml(batch_size: int = 50):
    """ 
    Starts a background thread to process all pending batteries.
    Returns immediately to avoid HTTP timeouts.
    """
    thread = threading.Thread(target=recompute_all_background, kwargs={"batch_size": batch_size})
    thread.daemon = True
    thread.start()
    
    return {
        "status": "success",
        "message": "Full fleet ML recompute started in background. Monitor progress via /api/ml/progress"
    }
