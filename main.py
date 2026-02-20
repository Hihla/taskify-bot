import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "success", "message": "Server is LIVE now!"}

@app.get("/api/test")
async def test():
    return {"status": "ok"}

# ملاحظة: شلنا كل كود Playwright المعقد مؤقتاً لنضمن التشغيل
