"""FastAPI main: CORS, logging middleware, 8 routers, GET /api/v1/health"""
import logging, time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .routers import companies, screener, sectors, peers, valuation, portfolio, documents, health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI(title="Financial Intelligence Platform API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} [{duration:.3f}s]")
    return response

# include 8 routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(companies.router, prefix="/api/v1", tags=["companies"])
app.include_router(screener.router, prefix="/api/v1", tags=["screener"])
app.include_router(sectors.router, prefix="/api/v1", tags=["sectors"])
app.include_router(peers.router, prefix="/api/v1", tags=["peers"])
app.include_router(valuation.router, prefix="/api/v1", tags=["valuation"])
app.include_router(portfolio.router, prefix="/api/v1", tags=["portfolio"])
app.include_router(documents.router, prefix="/api/v1", tags=["documents"])

@app.get("/")
def root():
    return {"status":"ok", "service":"Financial Intelligence Platform API"}

@app.get("/api/v1/health")
def health_check():
    return {"status":"ok"}
