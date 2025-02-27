from Scheduler.scheduler import create_db_and_tables, start_scheduler
import time
import signal
import sys

def signal_handler(sig, frame):
    print("Shutting down Health Checker...")
    sys.exit(0)

if __name__ == "__main__":
    print("Initializing health check scheduler...")
    
    # Initialize database tables
    create_db_and_tables()
    
    # Start the scheduler that runs in background threads
    scheduler = start_scheduler()
    
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Health Checker is running. Press Ctrl+C to exit.")
    
    # Keep the main program running indefinitely
    # This allows the background scheduler threads to continue executing
    try:
        while True:
            time.sleep(1)  # Sleep to prevent high CPU usage
    except KeyboardInterrupt:
        print("Shutting down Health Checker...")
        scheduler.shutdown()
