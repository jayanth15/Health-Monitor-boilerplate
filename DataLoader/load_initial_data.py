import sys
import os
from pathlib import Path

# Add the project root directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from Connectivity.database import engine, init_db
from Scheduler.model.models import Cloud_Services
from sqlmodel import Session, select

def load_mock_data():
    """
    Load mock data into the Cloud_Services table.
    
    Service Names: storm, ember, earth, void
    Service IDs: 1, 2, 3, 4
    Endpoints: Based on Health-Mock/main.py endpoints
    All services are set to live
    """
    print("Loading mock data into Cloud_Services table...")
    
    # Define mock services
    mock_services = [
        {
            "id": 1,
            "service_name": "storm",
            "endpoint": "http://localhost:8000/health/service1", 
            "is_live": True
        },
        {
            "id": 2,
            "service_name": "ember",
            "endpoint": "http://localhost:8000/health/service2",
            "is_live": True
        },
        {
            "id": 3,
            "service_name": "earth",
            "endpoint": "http://localhost:8000/health/service3",
            "is_live": True
        },
        {
            "id": 4,
            "service_name": "void",
            "endpoint": "http://localhost:8000/health/service4",
            "is_live": True
        }
    ]
    
    # Initialize database tables
    init_db()
    
    with Session(engine) as session:
        # Check if there are existing records
        statement = select(Cloud_Services)
        existing_services = session.exec(statement).all()
        
        if existing_services:
            print(f"Found {len(existing_services)} existing records in Cloud_Services table.")
            print("Skipping data loading to avoid duplicate entries.")
            return
            
        # Create and add services to the database
        cloud_services = [
            Cloud_Services(
                id=svc["id"],
                service_name=svc["service_name"],
                endpoint=svc["endpoint"],
                is_live=svc["is_live"]
            )
            for svc in mock_services
        ]
        
        session.add_all(cloud_services)
        session.commit()
        
        print(f"Successfully loaded {len(mock_services)} mock services into the database.")
        
        # List all services in the table
        print("\nCurrent services in the database:")
        services = session.exec(select(Cloud_Services)).all()
        for service in services:
            print(f"ID: {service.id}, Name: {service.service_name}, Endpoint: {service.endpoint}, Live: {service.is_live}")

if __name__ == "__main__":
    load_mock_data()