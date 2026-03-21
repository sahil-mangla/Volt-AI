import logging
import sys

def setup_logger():
    logger = logging.getLogger("voltai")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

log = setup_logger()

# Helper structured logs
def log_prediction(battery_id: str, cycle: int, health: float, rul: float, risk: float):
    log.info(f"[PREDICTION] Battery: {battery_id} | Cycle: {cycle} | Health: {health:.1f}% | RUL: {rul:.0f} | Risk: {risk:.2f}")

def log_error(context: str, error: str):
    log.error(f"[ERROR] {context}: {error}")

def log_alert(battery_id: str, severity: str, message: str):
    log.warning(f"[ALERT] Battery: {battery_id} | Severity: {severity} | Message: {message}")

def log_maintenance(battery_id: str, priority: str):
    log.info(f"[MAINTENANCE] Created Work Order for {battery_id} | Priority: {priority}")
