"""routes/transaction.py: endpoint transaksi peminjaman dengan async processing."""
import asyncio
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

import database as db
from database import get_db
from models import TransactionAccepted, TransactionCreate, TransactionOut

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# Saklar demo B3: False = versi tanpa lock (race condition), True = pakai lock.
PAKAI_LOCK = False

# Satu lock untuk seluruh proses. Hanya satu coroutine yang boleh berada di
# dalam blok "async with stok_lock" pada satu waktu.
stok_lock = asyncio.Lock()


# ---------- Pemotongan stok ----------
# Versi TANPA lock: sengaja rawan race condition (untuk demo Tahap 1 di B3).
async def potong_stok_tanpa_lock(item_id: int, qty: int) -> bool:
    stok_terkini = await db.get_stok(item_id)
    # Jeda buatan: membuka jendela waktu agar request lain ikut membaca stok
    # yang sama sebelum stok sempat dikurangi (check-then-act tidak atomik).
    await asyncio.sleep(0.01)
    if stok_terkini is None or stok_terkini < qty:
        return False
    await db.decrement_stok(item_id, qty)
    return True


# Versi DENGAN lock: seluruh urutan baca-cek-kurangi dijadikan satu bagian
# kritis, sehingga request kedua baru boleh membaca stok setelah request
# pertama selesai mengurangi stok.
async def potong_stok_dengan_lock(item_id: int, qty: int) -> bool:
    async with stok_lock:
        stok_terkini = await db.get_stok(item_id)
        await asyncio.sleep(0.01)  # jeda yang sama, tapi kini aman
        if stok_terkini is None or stok_terkini < qty:
            return False
        await db.decrement_stok(item_id, qty)
        return True


# ---------- Pekerja latar belakang ----------
# Fungsi internal Python (BUKAN endpoint HTTP). Dijalankan FastAPI SETELAH
# respon pending dikirim, sehingga client tidak menunggu proses ini.
async def proses_transaksi_background(trx_id: int, item_id: int, qty: int):
    try:
        await db.update_trx_status(trx_id, "processing")
        # Simulasi pekerjaan I/O: await melepas event loop sehingga request
        # lain tetap dilayani selama 3 detik ini (non-blocking).
        await asyncio.sleep(3)
        await db.update_trx_status(trx_id, "completed")
    except Exception:
        # Gagal di tengah jalan: tandai failed dan kembalikan stok.
        await db.update_trx_status(trx_id, "failed")
        await db.increment_stok(item_id, qty)


# ---------- Endpoint ----------
@router.post("", response_model=TransactionAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_transaction(data: TransactionCreate, bg: BackgroundTasks):
    # 1. Validasi: buku harus terdaftar
    if await db.get_stok(data.item_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buku tidak ditemukan")

    # 2. Validasi: stok harus mencukupi (sekaligus memotong stok)
    potong_stok = potong_stok_dengan_lock if PAKAI_LOCK else potong_stok_tanpa_lock
    if not await potong_stok(data.item_id, data.qty):
        raise HTTPException(status.HTTP_409_CONFLICT, "Stok habis atau tidak mencukupi")

    # 3. Catat transaksi berstatus pending
    trx_id = await db.insert_transaction(data.item_id, data.qty, data.peminjam, "pending")

    # 4. Jadwalkan proses latar belakang, lalu langsung balas tanpa menunggu
    bg.add_task(proses_transaksi_background, trx_id, data.item_id, data.qty)
    return {"id": trx_id, "status": "pending", "message": "Transaksi diproses"}


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    status_filter: Literal["pending", "processing", "completed", "failed"] | None = Query(
        None, alias="status"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
):
    """Daftar transaksi, mendukung filter ?status=pending."""
    query, params = "SELECT * FROM transactions", []
    if status_filter:
        query += " WHERE status = ?"
        params.append(status_filter)
    query += " ORDER BY id LIMIT ? OFFSET ?"
    params += [limit, skip]
    async with get_db() as conn:
        cur = await conn.execute(query, params)
        return [dict(r) for r in await cur.fetchall()]


@router.get("/{trx_id}", response_model=TransactionOut)
async def get_transaction(trx_id: int):
    """Detail transaksi beserta status terkini."""
    async with get_db() as conn:
        cur = await conn.execute("SELECT * FROM transactions WHERE id = ?", (trx_id,))
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaksi tidak ditemukan")
    return dict(row)