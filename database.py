"""database.py: koneksi aiosqlite dan inisialisasi tabel.

Semua operasi DB memakai aiosqlite sehingga bersifat async (non-blocking):
saat menunggu I/O disk, event loop bebas melayani request lain.
"""
from contextlib import asynccontextmanager

import aiosqlite

DB_PATH = "perpustakaan.db"

# Tabel resource utama: wajib punya kolom kuantitas (stok) bertipe integer.
CREATE_BOOKS_TABLE = """
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judul TEXT NOT NULL,
    penulis TEXT NOT NULL,
    kategori TEXT NOT NULL,
    tahun_terbit INTEGER NOT NULL,
    stok INTEGER NOT NULL  -- Kolom kuantitas wajib
);
"""

# Tabel transaksi peminjaman.
CREATE_TRANSACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES books(id),
    qty INTEGER NOT NULL CHECK (qty > 0),
    peminjam TEXT NOT NULL DEFAULT 'anonim',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@asynccontextmanager
async def get_db():
    """Buka koneksi aiosqlite baru per operasi, lalu tutup otomatis.

    row_factory = aiosqlite.Row membuat hasil query bisa diakses seperti dict.
    """
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    """Buat tabel jika belum ada. Dipanggil sekali saat aplikasi start."""
    async with get_db() as db:
        # WAL: pembaca tidak memblokir penulis, lebih aman untuk multi-worker.
        await db.execute("PRAGMA journal_mode = WAL")
        await db.execute(CREATE_BOOKS_TABLE)
        await db.execute(CREATE_TRANSACTIONS_TABLE)
        await db.commit()


# ---------- Helper transaksi (dipakai routes/transaction.py) ----------

async def get_stok(item_id: int) -> int | None:
    """Baca stok buku. None jika buku tidak ada."""
    async with get_db() as db:
        cur = await db.execute("SELECT stok FROM books WHERE id = ?", (item_id,))
        row = await cur.fetchone()
        return row["stok"] if row else None


async def decrement_stok(item_id: int, qty: int) -> None:
    async with get_db() as db:
        await db.execute("UPDATE books SET stok = stok - ? WHERE id = ?", (qty, item_id))
        await db.commit()


async def increment_stok(item_id: int, qty: int) -> None:
    async with get_db() as db:
        await db.execute("UPDATE books SET stok = stok + ? WHERE id = ?", (qty, item_id))
        await db.commit()


async def insert_transaction(item_id: int, qty: int, peminjam: str, status: str) -> int:
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO transactions (item_id, qty, peminjam, status) VALUES (?, ?, ?, ?)",
            (item_id, qty, peminjam, status),
        )
        await db.commit()
        return cur.lastrowid


async def update_trx_status(trx_id: int, status: str) -> None:
    async with get_db() as db:
        await db.execute("UPDATE transactions SET status = ? WHERE id = ?", (status, trx_id))
        await db.commit()