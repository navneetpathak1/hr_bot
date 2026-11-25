from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager # db

from app.config.database import engine
from . import user_route
from . import query_route


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()

    
app = FastAPI(lifespan=lifespan)

app.include_router(user_route.router, prefix="/api/v1", tags=["Users"])
app.include_router(query_route.router, prefix="/api/v1", tags=["Query"])


@app.get("/")
def Home():
    return {
        "message": "Hello World !!!"
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    return JSONResponse(
        status_code=422,
        content={
            "message": "Validation failed",
            "errors": exc.errors(),
            "path": str(request.url),
            "headers": dict(request.headers)
        }
    )



# 404 response
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(
    request: Request,
    exc: StarletteHTTPException
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "path": str(request.url)
        }
    )

