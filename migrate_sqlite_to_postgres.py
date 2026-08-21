"""One-time migration helper: copy a SIMTS SQLite database into PostgreSQL.

Usage (PowerShell):
  $env:SOURCE_DATABASE_URL='sqlite:///instance/simts.db'
  $env:TARGET_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/SIMTS_DB'
  python migrate_sqlite_to_postgres.py

Run this only against a new/empty PostgreSQL database. Uploaded certificate & marksheet files
are copied separately by the deployment process; this script migrates database rows.
"""
import os
import sys

from sqlalchemy import create_engine, insert, select

from models import Admin, AuditLog, Certificate, ContactMessage, Course, Marksheet, Student, db

SOURCE = os.getenv('SOURCE_DATABASE_URL', 'sqlite:///instance/simts.db')
TARGET = os.getenv('TARGET_DATABASE_URL')

if not TARGET:
    print('ERROR: Set TARGET_DATABASE_URL first.')
    sys.exit(1)

source_engine = create_engine(SOURCE)
target_engine = create_engine(TARGET, pool_pre_ping=True)

# Create the current SIMTS schema in PostgreSQL.
db.metadata.create_all(target_engine)

# Parent tables first, then dependent tables.
models_in_order = [Admin, Course, Student, Certificate, Marksheet, ContactMessage, AuditLog]

with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
    for model in models_in_order:
        table = model.__table__
        rows = source_conn.execute(select(table)).mappings().all()
        if not rows:
            print(f'{table.name}: 0 rows')
            continue

        # Do not silently overwrite an existing target table.
        existing = target_conn.execute(select(table).limit(1)).first()
        if existing is not None:
            raise RuntimeError(
                f'Target table {table.name} is not empty. Stop and use an empty database.'
            )

        target_conn.execute(insert(table), [dict(row) for row in rows])
        print(f'{table.name}: {len(rows)} rows migrated')

print('Migration completed successfully.')
print('Copy your uploads/ directory separately and verify documents before going live.')
