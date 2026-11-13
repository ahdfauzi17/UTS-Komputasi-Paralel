"""models.py: skema Pydantic untuk validasi request dan serialisasi response."""
from pydantic import BaseModel, Field


class BookBase(BaseModel):
    judul: str = Field(..., min_length=1, max_length=200)
    penulis: str = Field(..., min_length=1, max_length=100)
    kategori: str = Field(..., min_length=1, max_length=50)
    tahun_terbit: int = Field(..., ge=1000, le=2100)
    stok: int = Field(..., ge=0)  # jumlah eksemplar tersedia


class BookCreate(BookBase):
    """Body untuk POST /books."""


class BookUpdate(BookBase):
    """Body untuk PUT /books/{id} (penggantian penuh)."""


class BookOut(BaseModel):
    """Bentuk response. stok TIDAK divalidasi ge=0 di sini agar nilai minus
    akibat race condition (demo B3 Tahap 1) tetap bisa ditampilkan."""
    id: int
    judul: str
    penulis: str
    kategori: str
    tahun_terbit: int
    stok: int


class MessageOut(BaseModel):
    message: str


class TransactionCreate(BaseModel):
    item_id: int = Field(..., ge=1)
    qty: int = Field(1, ge=1)
    peminjam: str = Field("anonim", min_length=1, max_length=100)


class TransactionAccepted(BaseModel):
    """Respon instan POST /transactions."""
    id: int
    status: str
    message: str


class TransactionOut(BaseModel):
    id: int
    item_id: int
    qty: int
    peminjam: str
    status: str
    created_at: str