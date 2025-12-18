from fastapi import FastAPI, Request, status
from fastapi.responses import Response, FileResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from src.perf.system_monitor import get_monitor
from src.services import logs as log_service
from fastapi.staticfiles import StaticFiles
from src.constants import Constants
from src.db import db_init, db_close
from src import middleware
from src.routes import shortener
from src.routes import admin
from src.routes import users_admin
from src.routes import auth
from src.routes import logs_admin
from src.routes import urls_admin
from src.routes import time_perf_admin
from src.routes import domains_admin
from src.routes import tags
from src.routes import user
from src.routes import dashboard
from src import util
from src.cache import RedisLikeCache
import uvicorn
import time
import contextlib
import asyncio
import os



@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[Starting {Constants.API_NAME}]")
    # System Monitor
    system_monitor_task = asyncio.create_task(util.periodic_update())

    # Database
    await db_init()
    
    yield
    
    # SystemMonitor
    system_monitor_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await system_monitor_task

    # Database
    await db_close()    

    print(f"[Shutting down {Constants.API_NAME}]")



app = FastAPI(    
    title=Constants.API_NAME, 
    description=Constants.API_DESCR,
    version=Constants.API_VERSION,
    lifespan=lifespan
)

if Constants.IS_PRODUCTION:
    origins = [
        "https://vitortz.github.io"
    ]
else:
    origins = [        
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ]    


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def read_root():
    return { "status": "ok" }


@app.get("/favicon.ico")
async def favicon():
    favicon_path = os.path.join("static", "favicon.ico")
    return FileResponse(favicon_path)


app.include_router(shortener.router, prefix='', tags=["shorten"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(users_admin.router, prefix="/admin", tags=["admin_users"])
app.include_router(urls_admin.router, prefix="/admin", tags=["admin_urls"])
app.include_router(logs_admin.router, prefix="/admin", tags=["admin_logs"])
app.include_router(time_perf_admin.router, prefix="/admin", tags=["admin_time_perf"])
app.include_router(domains_admin.router, prefix="/admin", tags=["admin_domains"])
app.include_router(tags.router, prefix="/user/tags", tags=["tags"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(user.router, prefix="/user", tags=["user"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])

    

app.add_middleware(GZipMiddleware, minimum_size=1000)


########################## MIDDLEWARES ##########################

@app.middleware("http")
async def http_middleware(request: Request, call_next):
    if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
        response = await call_next(request)
        return response
    
    monitor = get_monitor()
    start_time = time.perf_counter()
    
    # Body size check
    content_length = request.headers.get("content-length")
    if content_length:
        if int(content_length) > Constants.MAX_BODY_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Request entity too large. Max allowed: {Constants.MAX_BODY_SIZE} bytes"
            )
    else:
        body = b""
        async for chunk in request.stream():
            body += chunk
            if len(body) > Constants.MAX_BODY_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"Request entity too large. Max allowed: {Constants.MAX_BODY_SIZE} bytes"
                )
        request._body = body
    
    # Rate limit check
    identifier = util.get_client_identifier(request)
    key = f"rate_limit:{identifier}"

    cache = RedisLikeCache()

    current = cache.get(key)
    new_value = (current + 1) if current else 1

    if new_value > Constants.MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Too many requests",
                "message": "Rate limit exceeded. Try again in 60 seconds.",
                "retry_after": f"{Constants.WINDOW}",
                "limit": Constants.MAX_REQUESTS,
                "window": Constants.WINDOW
            },
            headers={
                "Retry-After": f"{Constants.WINDOW}",
                "X-RateLimit-Limit": str(Constants.MAX_REQUESTS),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": f"{Constants.WINDOW}"
            }
        )

    cache.set(key, new_value, Constants.WINDOW)
    current = new_value
    
    # Headers
    response: Response = await call_next(request)
        
    remaining = max(Constants.MAX_REQUESTS - current, 0)
    response.headers["X-RateLimit-Limit"] = str(Constants.MAX_REQUESTS)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = f"{Constants.WINDOW}"
        
    middleware.add_security_headers(request, response)
    response_time_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Response-Time"] = f"{response_time_ms:.2f}ms"
    
    # System Monitor
    monitor.increment_request(response_time_ms)

    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return await log_service.log_and_build_response(
        request=request,
        exc=exc,
        error_level="WARN" if exc.status_code < 500 else "ERROR",
        status_code=exc.status_code,
        detail=exc.detail
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return await log_service.log_and_build_response(
        request=request,
        exc=exc,
        error_level="WARN",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "message": "Validation error",
            "errors": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return await log_service.log_and_build_response(
        request=request,
        exc=exc,
        error_level="FATAL",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error"
    )



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)