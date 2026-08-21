"""One-time migration of existing local certificate/marksheet PDFs to Vercel Blob.

Run locally after setting DATABASE_URL and BLOB_READ_WRITE_TOKEN.
The local uploads/ directory must contain the PDFs referenced by the database.

Example (PowerShell):
    $env:BLOB_READ_WRITE_TOKEN="your-token"
    python migrate_files_to_blob.py
"""

from pathlib import Path

from app import app
from extensions import db
from models import Certificate, Marksheet
from services.blob_storage import blob_enabled, upload_pdf

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"


def migrate(model, prefix, field_name):
    rows = model.query.order_by(model.id).all()
    migrated = 0
    skipped = 0
    failed = 0

    for row in rows:
        reference = getattr(row, field_name)
        if reference and str(reference).startswith("http"):
            skipped += 1
            continue

        source = UPLOAD_DIR / str(reference)
        if not source.is_file():
            print(f"[MISSING] {model.__name__} #{row.id}: {source}")
            failed += 1
            continue

        try:
            with source.open("rb") as fh:
                class UploadedFile:
                    def __init__(self, stream):
                        self.stream = stream

                    def read(self):
                        return self.stream.read()

                uploaded = UploadedFile(fh)
                new_reference = upload_pdf(
                    uploaded,
                    prefix,
                    source.name,
                )

            setattr(row, field_name, new_reference)
            db.session.commit()
            migrated += 1
            print(f"[OK] {model.__name__} #{row.id} -> {new_reference}")
        except Exception as exc:
            db.session.rollback()
            failed += 1
            print(f"[ERROR] {model.__name__} #{row.id}: {exc}")

    return migrated, skipped, failed


with app.app_context():
    if not blob_enabled():
        raise SystemExit(
            "BLOB_READ_WRITE_TOKEN is required. "
            "Set it before running this migration."
        )

    print("SIMTS local PDF -> Vercel Blob migration")
    print(f"Source folder: {UPLOAD_DIR}")
    print()

    c = migrate(Certificate, "certificates", "file_name")
    m = migrate(Marksheet, "marksheets", "file_name")

    print()
    print(f"Certificates: migrated={c[0]}, skipped={c[1]}, failed={c[2]}")
    print(f"Marksheets:   migrated={m[0]}, skipped={m[1]}, failed={m[2]}")
