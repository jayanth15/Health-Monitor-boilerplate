from fastapi import FastAPI
from app.apis.degradation_api import router as degradation_router
from app.api.health_endpoints import router as health_router
from app.utils.database import init_db

app = FastAPI(title="Health Checker API",
              description="API for checking service health and handling degradation events")

# Include the routers
app.include_router(degradation_router, prefix="/degradation", tags=["Degradation"])
app.include_router(health_router, prefix="/health", tags=["Health Status"])

# Initialize database tables on startup
@app.on_event("startup")
async def on_startup():
    init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)