from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import requests
from datetime import datetime, timezone
import sys
import os
from pathlib import Path
import concurrent.futures
from typing import List, Dict, Any

# Add the parent directory to sys.path to import the models
sys.path.append(str(Path(__file__).parent.parent.parent))
from Scheduler.model.models import Cloud_Services, Health_Status
from Connectivity.database import engine, init_db
from sqlmodel import Session, select

def create_db_and_tables():
    """Create database tables if they don't exist"""
    init_db()

def check_single_endpoint(service: Cloud_Services) -> Dict[str, Any]:
    """
    Check a single endpoint and return the result
    """
    try:
        # Send a GET request to the endpoint
        response = requests.get(service.endpoint, timeout=10)
        is_healthy = 200 <= response.status_code < 300
        status_code = response.status_code
    except Exception as e:
        # If request fails, mark as unhealthy
        is_healthy = False
        status_code = 0  # Use 0 to indicate connection error
        print(f"Error checking {service.service_name} at {service.endpoint}: {str(e)}")
    
    # If service is not healthy, trigger degradation check
    if not is_healthy:
        try:
            degradation_url = f"http://localhost:8001/auto-check-degradation/{service.id}"
            degradation_response = requests.post(degradation_url, timeout=10)
            if degradation_response.status_code == 200:
                degradation_data = degradation_response.json()
                if degradation_data.get("is_degraded"):
                    print(f"DEGRADATION ALERT: Service {service.service_name} is DEGRADED!")
                    if "message" in degradation_data:
                        print(f"Message: {degradation_data['message']}")
        except Exception as e:
            print(f"Failed to check degradation for service {service.service_name}: {str(e)}")
    
    return {
        "service_id": service.id,
        "is_health": is_healthy,
        "timestamp": datetime.now(timezone.utc),
        "status_code": status_code,
        "service_name": service.service_name  # For logging purposes
    }

def check_endpoints():
    """
    Fetch all endpoints from Cloud_Services and check their health status in parallel
    Update the Health_Status table with the results
    """
    with Session(engine) as session:
        # Get all active cloud services
        statement = select(Cloud_Services).where(Cloud_Services.is_live == True)
        services = session.exec(statement).all()
        
        # Use ThreadPoolExecutor to make API calls in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Start all API calls in parallel and collect futures
            future_to_service = {
                executor.submit(check_single_endpoint, service): service 
                for service in services
            }
            
            # Process results as they complete
            results = []
            for future in concurrent.futures.as_completed(future_to_service):
                result = future.result()
                results.append(result)
                print(f"Updated health status for {result['service_name']}: "
                      f"{'Healthy' if result['is_health'] else 'Unhealthy'} "
                      f"(Status code: {result['status_code']})")
        
        # Batch insert all health status records
        health_statuses = [
            Health_Status(
                service_id=result["service_id"],
                is_health=result["is_health"],
                timestamp=result["timestamp"],
                status_code=result["status_code"]
            )
            for result in results
        ]
        
        # Add all records to the database
        session.add_all(health_statuses)
        session.commit()

def start_scheduler():
    """Initialize and start the scheduler"""
    scheduler = BackgroundScheduler()
    
    # Add job to run every minute
    scheduler.add_job(
        check_endpoints,
        trigger=IntervalTrigger(minutes=1),
        id='health_check_job',
        name='Check endpoint health every minute',
        replace_existing=True
    )
    
    # Start the scheduler
    scheduler.start()
    print("Scheduler started. Health checks will run every minute.")
    return scheduler

