"""main.py: inisialisasi FastAPI dan registrasi router."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import init_db
from routes import resource, transaction


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dijalankan sekali saat server start: pastikan tabel sudah ada.
    await init_db()
    yield


app = FastAPI(title="API Perpustakaan", version="1.0.0", lifespan=lifespan)

app.include_router(resource.router)
app.include_router(transaction.router)


@app.get("/", tags=["Root"])
async def root():
    return {"message": "API Perpustakaan berjalan. Dokumentasi di /docs"}