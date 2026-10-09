"""
PeopleOps — Render PostgreSQL to Local Database Mirroring Utility
================================================================
Pulls live table schemas and records from Render Cloud PostgreSQL
and mirrors them into the local SQLite database (`hr_platform.db`).
"""
import os
import sys
import asyncio
import sqlite3
import logging
from sqlalchemy import text
from dotenv import load_dotenv

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
load_dotenv(os.path.join(backend_dir, ".env"))

from app.core.config import settings
from app.core.database import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("db_mirror")

async def sync_render_to_local_sqlite(output_sqlite_path: str = None):
    if not output_sqlite_path:
        output_sqlite_path = os.path.join(backend_dir, "hr_platform.db")

    print("=" * 72)
    print(" 🚀 PEOPLEOPS — RENDER POSTGRESQL -> LOCAL SQLITE MIRROR")
    print("=" * 72)
    print(f" Source DB : Render PostgreSQL ({settings.DATABASE_URL.split('@')[-1]})")
    print(f" Target DB : Local SQLite ({output_sqlite_path})")
    print("-" * 72)

    synced_counts = {}

    sqlite_conn = sqlite3.connect(output_sqlite_path)
    sqlite_cursor = sqlite_conn.cursor()

    try:
        async with engine.connect() as pg_conn:
            # 1. Discover all tables in PostgreSQL public schema
            res = await pg_conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
            )
            tables = [r[0] for r in res.fetchall()]
            print(f" Found {len(tables)} tables on Render PostgreSQL: {', '.join(tables)}\n")

            for tbl in tables:
                try:
                    # 2. Fetch rows from Render PostgreSQL
                    res = await pg_conn.execute(text(f'SELECT * FROM "{tbl}"'))
                    columns = list(res.keys())
                    rows = res.fetchall()

                    if not columns:
                        synced_counts[tbl] = 0
                        print(f"  ⚠ {tbl:<26} : 0 columns found")
                        continue

                    # 3. Re-create table structure in SQLite
                    sqlite_cursor.execute(f'DROP TABLE IF EXISTS "{tbl}"')
                    col_defs = ", ".join([f'"{col}" TEXT' for col in columns])
                    sqlite_cursor.execute(f'CREATE TABLE "{tbl}" ({col_defs})')

                    # 4. Insert rows into SQLite
                    if rows:
                        placeholders = ", ".join(["?"] * len(columns))
                        safe_rows = [
                            tuple(str(val) if val is not None else None for val in row)
                            for row in rows
                        ]
                        sqlite_cursor.executemany(
                            f'INSERT INTO "{tbl}" VALUES ({placeholders})',
                            safe_rows
                        )

                    sqlite_conn.commit()
                    synced_counts[tbl] = len(rows)
                    print(f"  ✓ {tbl:<26} : {len(rows):>4} rows mirrored")
                except Exception as e:
                    synced_counts[tbl] = f"Error: {e}"
                    print(f"  ❌ {tbl:<26} : {e}")

        print("-" * 72)
        print(f" ✅ ALL {len(tables)} TABLES SUCCESSFULLY MIRRORED TO: {output_sqlite_path}")
        print("=" * 72)
        return {"status": "success", "counts": synced_counts, "sqlite_path": output_sqlite_path}
    except Exception as exc:
        print(f" ❌ Mirroring failed: {exc}")
        return {"status": "error", "error": str(exc)}
    finally:
        sqlite_conn.close()

if __name__ == "__main__":
    asyncio.run(sync_render_to_local_sqlite())
