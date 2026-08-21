"""Vercel Blob storage helpers for SIMTS.

Certificates and marksheets are sensitive academic documents, so Vercel Blob
is used in private mode when the application is running on Vercel.

Local development continues to use the normal uploads/ directory.
"""

import os
import tempfile
from pathlib import Path

from werkzeug.utils import secure_filename


class BlobStorageError(RuntimeError):
    """Raised when Vercel Blob storage cannot complete an operation."""


def blob_enabled():
    """Return True when the deployed app should use Vercel Blob."""
    return bool(os.getenv("BLOB_READ_WRITE_TOKEN"))


def _client():
    if not blob_enabled():
        raise BlobStorageError("Vercel Blob storage is not configured.")

    try:
        from vercel.blob import BlobClient
    except ImportError as exc:
        raise BlobStorageError(
            "The Vercel Python SDK is not installed. Add 'vercel>=0.5.0' to requirements.txt."
        ) from exc

    return BlobClient()


def upload_pdf(file_storage, prefix, base_name):
    """Upload a Flask FileStorage object to a private Vercel Blob store.

    Returns the blob URL, which is stored in the existing file_name database
    column. No database schema change is required.
    """
    client = _client()

    filename = secure_filename(base_name)
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    # Random suffix prevents collisions and makes the stored object immutable.
    pathname = f"simts/{prefix}/{filename}"
    body = file_storage.read()
    file_storage.stream.seek(0)

    try:
        uploaded = client.put(
            pathname,
            body,
            access="private",
            content_type="application/pdf",
            add_random_suffix=True,
            multipart=len(body) >= 5 * 1024 * 1024,
        )
        return uploaded.url
    except Exception as exc:
        raise BlobStorageError(f"Vercel Blob upload failed: {exc}") from exc


def delete_file(file_reference):
    """Delete a Vercel Blob URL/reference. Local files are ignored here."""
    if not file_reference or not blob_enabled():
        return

    if not str(file_reference).startswith("http"):
        return

    client = _client()
    try:
        client.delete([file_reference])
    except Exception as exc:
        raise BlobStorageError(f"Vercel Blob delete failed: {exc}") from exc


def download_to_temp(file_reference):
    """Download a private Vercel Blob into /tmp and return its path."""
    if not blob_enabled():
        raise BlobStorageError("Vercel Blob storage is not configured.")

    client = _client()
    suffix = ".pdf"
    fd, temp_name = tempfile.mkstemp(prefix="simts_", suffix=suffix)
    os.close(fd)
    temp_path = Path(temp_name)

    try:
        client.download_file(
            file_reference,
            str(temp_path),
            overwrite=True,
        )
        return temp_path
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise BlobStorageError(f"Vercel Blob download failed: {exc}") from exc
