from fastapi import FastAPI
from config.database import engine
from . import user_route
from contextlib import asynccontextmanager # db

@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()

    
app = FastAPI(lifespan=lifespan)

app.include_router(user_route.router, prefix="/api/v1", tags=["Users"])

@app.get("/")
def Home():
    return {
        "message": "Hello World !!!"
    }