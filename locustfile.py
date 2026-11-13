"""locustfile.py: benchmark beban dengan Locust.

Dua skenario (dijalankan TERPISAH, pilih lewat nama kelas):
  BookUser        : GET /books            -> 100 request, 20 pengguna bersamaan
  TransactionUser : POST /transactions    ->  50 request, 10 pengguna bersamaan

Tes berhenti otomatis tepat setelah jumlah request target tercapai.
Jalankan (server harus hidup), contoh:
  python -m locust -f locustfile.py --headless --host http://127.0.0.1:8000 -u 20 -r 20 BookUser
  python -m locust -f locustfile.py --headless --host http://127.0.0.1:8000 -u 10 -r 10 TransactionUser
"""
import os
import random
import time

import gevent
import requests
from locust import HttpUser, constant, events, task

JUMLAH_GET = 100    # total request GET /books
JUMLAH_POST = 50    # total request POST /transactions
JUMLAH_BUKU = 15    # sesuai jumlah data di seed.py
STOK_BENCHMARK = 1000  # stok besar agar POST tidak gagal karena stok habis
TIMEOUT_DETIK = 15     # request tanpa balasan dianggap gagal, bukan ditunggu selamanya

# Penghitung bersama (aman karena Locust memakai gevent, bukan thread paralel).
state = {"dikirim": 0, "selesai": 0, "mulai": 0.0, "dicetak": False}


def ambil_jatah(total: int) -> bool:
    """True jika request ini masih termasuk kuota total."""
    if state["dikirim"] >= total:
        return False
    state["dikirim"] += 1
    return True


def cetak_ringkasan(environment) -> None:
    """Cetak ringkasan siap salin ke tabel laporan (hanya sekali)."""
    if state["dicetak"]:
        return
    state["dicetak"] = True
    total = environment.stats.total
    durasi = time.time() - state["mulai"]
    print("\n===== RINGKASAN UNTUK LAPORAN =====")
    print(f"Total request     : {total.num_requests} (gagal: {total.num_failures})")
    print(f"Total waktu       : {durasi:.2f} detik")
    print(f"Throughput        : {total.num_requests / durasi:.2f} req/detik")
    print(f"Rata-rata latensi : {total.avg_response_time:.2f} ms")
    print("===================================\n", flush=True)


def tandai_selesai(user: HttpUser, total: int) -> None:
    """Akhiri tes tepat setelah request ke-`total` selesai."""
    state["selesai"] += 1
    if state["selesai"] >= total:
        # Ringkasan dicetak SEKARANG (waktu paling akurat), tidak menunggu quit().
        cetak_ringkasan(user.environment)
        # quit() dijalankan di greenlet terpisah (dari dalam greenlet user ia
        # ikut mematikan dirinya sendiri).
        gevent.spawn(user.environment.runner.quit)
        # Pengaman: pada sebagian lingkungan quit() tidak tuntas dan Locust
        # menggantung. Jika 3 detik kemudian proses masih hidup, paksa keluar.
        gevent.spawn_later(3, os._exit, 0)


@events.test_start.add_listener
def siapkan_data(environment, **kwargs):
    """Naikkan stok semua buku agar skenario POST tidak terganggu 409."""
    host = environment.host
    state["mulai"] = time.time()
    # Pastikan server hidup; kalau tidak, hentikan dengan pesan yang jelas.
    try:
        requests.get(f"{host}/", timeout=5)
    except requests.exceptions.ConnectionError:
        print(f"\n[ERROR] Server tidak hidup di {host}.")
        print("Jalankan dulu di terminal 1: python -m uvicorn main:app --port 8000\n")
        gevent.spawn(environment.runner.quit)
        return
    for book_id in range(1, JUMLAH_BUKU + 1):
        r = requests.get(f"{host}/books/{book_id}", timeout=10)
        if r.status_code != 200:
            print(f"[PERINGATAN] Buku {book_id} tidak ada. Jalankan 'python seed.py' dulu.")
            continue
        data = r.json()
        data.pop("id")
        data["stok"] = STOK_BENCHMARK
        requests.put(f"{host}/books/{book_id}", json=data, timeout=10)
    state["mulai"] = time.time()


@events.test_stop.add_listener
def saat_berhenti(environment, **kwargs):
    cetak_ringkasan(environment)  # tidak mencetak ulang jika sudah tercetak


class BookUser(HttpUser):
    """Skenario 1: baca daftar buku (read-only)."""
    wait_time = constant(0)

    @task
    def baca_daftar_buku(self):
        if not ambil_jatah(JUMLAH_GET):
            self.stop()
            return
        self.client.get("/books?skip=0&limit=10", name="GET /books", timeout=TIMEOUT_DETIK)
        tandai_selesai(self, JUMLAH_GET)


class TransactionUser(HttpUser):
    """Skenario 2: buat transaksi peminjaman (write + background task)."""
    wait_time = constant(0)

    @task
    def pinjam_buku(self):
        if not ambil_jatah(JUMLAH_POST):
            self.stop()
            return
        payload = {"item_id": random.randint(1, JUMLAH_BUKU), "qty": 1}
        with self.client.post(
            "/transactions", json=payload, name="POST /transactions",
            catch_response=True, timeout=TIMEOUT_DETIK,
        ) as resp:
            if resp.status_code == 202:
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}: {resp.text[:80]}")
        tandai_selesai(self, JUMLAH_POST)