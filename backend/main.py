import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="강의 추천 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_SECRET_KEY = os.getenv("API_SECRET_KEY")
PUBLIC_PATHS = ["/docs", "/openapi.json", "/redoc", "/health"]

@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if any(request.url.path.startswith(p) for p in PUBLIC_PATHS):
        return await call_next(request)
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != API_SECRET_KEY:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

from app.api import lectures, instructors, reviews, exams, zapier_webhook
app.include_router(lectures.router, prefix="/api")
app.include_router(instructors.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(exams.router, prefix="/api")
app.include_router(zapier_webhook.router, prefix="/api")
