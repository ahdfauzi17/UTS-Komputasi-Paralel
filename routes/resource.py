"""routes/resource.py: endpoint CRUD untuk resource utama (buku)."""
import aiosqlite
from fastapi import APIRouter, HTTPException, Query, status

from database import get_db
from models import BookCreate, BookOut, BookUpdate, MessageOut

router = APIRouter(prefix="/books", tags=["Books"])


async def _ambil_buku(db: aiosqlite.Connection, book_id: int) -> dict | None:
    cur = await db.execute("SELECT * FROM books WHERE id = ?", (book_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


@router.get("", response_model=list[BookOut])
async def list_books(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
):
    """Daftar buku dengan paginasi ?skip=0&limit=10."""
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM books ORDER BY id LIMIT ? OFFSET ?", (limit, skip)
        )
        return [dict(r) for r in await cur.fetchall()]


@router.get("/{book_id}", response_model=BookOut)
async def get_book(book_id: int):
    async with get_db() as db:
        buku = await _ambil_buku(db, book_id)
    if buku is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buku tidak ditemukan")
    return buku


@router.post("", response_model=BookOut, status_code=status.HTTP_201_CREATED)
async def create_book(data: BookCreate):
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO books (judul, penulis, kategori, tahun_terbit, stok) "
            "VALUES (?, ?, ?, ?, ?)",
            (data.judul, data.penulis, data.kategori, data.tahun_terbit, data.stok),
        )
        await db.commit()
        return await _ambil_buku(db, cur.lastrowid)


@router.put("/{book_id}", response_model=BookOut)
async def update_book(book_id: int, data: BookUpdate):
    """Perbarui buku dan kembalikan data terbaru."""
    async with get_db() as db:
        if await _ambil_buku(db, book_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Buku tidak ditemukan")
        await db.execute(
            "UPDATE books SET judul=?, penulis=?, kategori=?, tahun_terbit=?, stok=? "
            "WHERE id=?",
            (data.judul, data.penulis, data.kategori, data.tahun_terbit, data.stok, book_id),
        )
        await db.commit()
        return await _ambil_buku(db, book_id)


@router.delete("/{book_id}", response_model=MessageOut)
async def delete_book(book_id: int):
    """Hard delete: baris benar-benar dihapus dari basis data."""
    async with get_db() as db:
        if await _ambil_buku(db, book_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Buku tidak ditemukan")
        try:
            await db.execute("DELETE FROM books WHERE id = ?", (book_id,))
            await db.commit()
        except aiosqlite.IntegrityError:
            # Buku masih dirujuk oleh data transaksi (foreign key).
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Buku tidak bisa dihapus karena masih punya riwayat peminjaman",
            )
    return {"message": f"Buku {book_id} berhasil dihapus"}