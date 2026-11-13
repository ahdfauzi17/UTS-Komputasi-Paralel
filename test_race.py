"""test_race.py: uji race condition pada pemotongan stok.

Skenario: stok buku = 1, lalu 2 request peminjaman dikirim BERSAMAAN.
- Tanpa lock : keduanya sukses (202) dan stok akhir menjadi -1 (overselling).
- Dengan lock: satu sukses (202), satu ditolak (409), stok akhir 0.

Jalankan (server harus sedang hidup): python test_race.py
"""
import asyncio

import httpx

BASE_URL = "http://127.0.0.1:8000"
ITEM_ID = 1


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        # 1. Reset: set stok buku menjadi 1
        buku = (await client.get(f"/books/{ITEM_ID}")).json()
        buku.pop("id")
        buku["stok"] = 1
        await client.put(f"/books/{ITEM_ID}", json=buku)
        print(f"Stok awal buku {ITEM_ID}: 1")

        # 2. Kirim 2 request pinjam secara bersamaan
        payload = {"item_id": ITEM_ID, "qty": 1}
        r1, r2 = await asyncio.gather(
            client.post("/transactions", json=payload),
            client.post("/transactions", json=payload),
        )
        print(f"Request 1 -> {r1.status_code} {r1.json()}")
        print(f"Request 2 -> {r2.status_code} {r2.json()}")

        # 3. Cek stok akhir
        stok_akhir = (await client.get(f"/books/{ITEM_ID}")).json()["stok"]
        print(f"Stok akhir: {stok_akhir}")

        sukses = [r.status_code for r in (r1, r2)].count(202)
        if sukses == 2 or stok_akhir < 0:
            print("HASIL: RACE CONDITION TERJADI (stok 1 dipinjam 2 kali)")
        else:
            print("HASIL: AMAN (hanya 1 request yang berhasil)")


if __name__ == "__main__":
    asyncio.run(main())