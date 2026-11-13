"""seed.py: isi data awal (15 buku) agar endpoint langsung bisa diuji.

Jalankan: python seed.py
Aman dijalankan ulang: tabel books dikosongkan dulu supaya tidak dobel.
"""
import asyncio

from database import get_db, init_db

BUKU = [
    ("Laskar Pelangi", "Andrea Hirata", "Novel", 2005, 5),
    ("Bumi Manusia", "Pramoedya Ananta Toer", "Novel", 1980, 3),
    ("Negeri 5 Menara", "Ahmad Fuadi", "Novel", 2009, 4),
    ("Filosofi Teras", "Henry Manampiring", "Filsafat", 2018, 6),
    ("Atomic Habits", "James Clear", "Pengembangan Diri", 2018, 4),
    ("Clean Code", "Robert C. Martin", "Teknologi", 2008, 3),
    ("Introduction to Algorithms", "Thomas H. Cormen", "Teknologi", 2009, 2),
    ("Fluent Python", "Luciano Ramalho", "Teknologi", 2022, 3),
    ("Sapiens", "Yuval Noah Harari", "Sejarah", 2011, 5),
    ("Cantik Itu Luka", "Eka Kurniawan", "Novel", 2002, 2),
    ("Dilan 1990", "Pidi Baiq", "Novel", 2014, 7),
    ("Pemrograman Python Dasar", "Budi Raharjo", "Teknologi", 2020, 8),
    ("Madilog", "Tan Malaka", "Filsafat", 1943, 2),
    ("Laut Bercerita", "Leila S. Chudori", "Novel", 2017, 4),
    ("Rich Dad Poor Dad", "Robert Kiyosaki", "Keuangan", 1997, 5),
]


async def main() -> None:
    await init_db()
    async with get_db() as db:
        await db.execute("DELETE FROM transactions")
        await db.execute("DELETE FROM books")
        await db.execute("DELETE FROM sqlite_sequence WHERE name IN ('books','transactions')")
        await db.executemany(
            "INSERT INTO books (judul, penulis, kategori, tahun_terbit, stok) "
            "VALUES (?, ?, ?, ?, ?)",
            BUKU,
        )
        await db.commit()
    print(f"Seed selesai: {len(BUKU)} buku dimasukkan.")


if __name__ == "__main__":
    asyncio.run(main())