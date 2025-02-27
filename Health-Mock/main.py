from fastapi import FastAPI
from fastapi.responses import JSONResponse
import random
import uvicorn

app = FastAPI()

def random_status():
    """Returns either 200 or 500 randomly"""
    return random.choice([200, 500])

@app.get('/health/service1')
async def health_service1():
    status = random_status()
    return JSONResponse(
        content={'status': 'ok' if status == 200 else 'error'},
        status_code=status
    )

@app.get('/health/service2')
async def health_service2():
    status = random_status()
    return JSONResponse(
        content={'status': 'ok' if status == 200 else 'error'},
        status_code=status
    )

@app.get('/health/service3')
async def health_service3():
    status = random_status()
    return JSONResponse(
        content={'status': 'ok' if status == 200 else 'error'},
        status_code=status
    )

@app.get('/health/service4')
async def health_service4():
    status = random_status()
    return JSONResponse(
        content={'status': 'ok' if status == 200 else 'error'},
        status_code=status
    )

if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)