"""Vercel Blob storage helpers for SIMTS.

Certificates and marksheets are sensitive academic documents, so Vercel
Blob is used in private mode when the application is running on Vercel.

Local development continues to use the normal uploads/ directory.

Important Vercel Private Blob detail:
private Blob URLs cannot be opened directly by a browser. They must be
fetched by an authenticated server request using BLOB_READ_WRITE_TOKEN.
This module therefore downloads private blobs through an Authorization
header and stores the response temporarily in /tmp before Flask serves it.
"""

import os
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from werkzeug.utils import secure_filename


class BlobStorageError(RuntimeError):
    """Raised when Vercel Blob storage cannot complete an operation."""


def blob_enabled():
    """Return True when the deployed app should use Vercel Blob."""
    return bool((os.getenv("BLOB_READ_WRITE_TOKEN") or "").strip())


def _client():
    """Create the official Vercel Python Blob client for write/delete operations."""
    if not blob_enabled():
        raise BlobStorageError("Vercel Blob storage is not configured.")

    try:
        from vercel.blob import BlobClient
    except ImportError as exc:
        raise BlobStorageError(
            "The Vercel Python SDK is not installed. Add 'vercel>=0.5.0' to requirements.txt."
        ) from exc

    return BlobClient()


def _blob_token():
    token = (os.getenv("BLOB_READ_WRITE_TOKEN") or "").strip()
    if not token:
        raise BlobStorageError("BLOB_READ_WRITE_TOKEN is missing.")
    return token


def upload_pdf(file_storage, prefix, base_name):
    """Upload a Flask FileStorage object to a private Vercel Blob store.

    Returns the blob URL, which is stored in the existing file_name database
    column. No database schema change is required.
    """
    client = _client()

    filename = secure_filename(base_name)
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

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
    """Download a private Vercel Blob to a temporary local file.

    Vercel Private Blob URLs intentionally return HTTP 403 when opened
    without authentication. The official Vercel documentation supports
    direct authenticated reads using:

        Authorization: Bearer BLOB_READ_WRITE_TOKEN

    We use the documented HTTP interface here instead of relying on the
    SDK's older download_file helper. The PDF is streamed in chunks so the
    entire document is not unnecessarily held in memory.
    """
    if not blob_enabled():
        raise BlobStorageError("Vercel Blob storage is not configured.")

    if not file_reference or not str(file_reference).startswith(("http://", "https://")):
        raise BlobStorageError("Invalid Vercel Blob URL stored for this document.")

    token = _blob_token()
    fd, temp_name = tempfile.mkstemp(prefix="simts_blob_", suffix=".pdf")
    os.close(fd)
    temp_path = Path(temp_name)

    request = Request(
        str(file_reference),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/pdf, application/octet-stream;q=0.9, */*;q=0.1",
            "User-Agent": "SIMTS/3.0 Vercel Blob reader",
        },
        method="GET",
    )

    last_error = None

    # A small retry helps with transient network errors from a serverless
    # function without hiding genuine authentication/permission errors.
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as remote:
                status = getattr(remote, "status", 200)
                if status != 200:
                    raise BlobStorageError(
                        f"Vercel Blob returned HTTP {status} while reading the document."
                    )

                with temp_path.open("wb") as destination:
                    while True:
                        chunk = remote.read(1024 * 1024)
                        if not chunk:
                            break
                        destination.write(chunk)

            if temp_path.stat().st_size == 0:
                raise BlobStorageError("Vercel Blob returned an empty document.")

            return temp_path

        except HTTPError as exc:
            # Do not retry authentication/authorization failures.
            if exc.code in (401, 403, 404):
                temp_path.unlink(missing_ok=True)
                raise BlobStorageError(
                    f"Vercel Blob returned HTTP {exc.code}. Check BLOB_READ_WRITE_TOKEN and blob access."
                ) from exc
            last_error = exc
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
        except BlobStorageError:
            temp_path.unlink(missing_ok=True)
            raise
        except Exception as exc:
            last_error = exc

        if attempt < 2:
            time.sleep(0.25 * (2 ** attempt))

    temp_path.unlink(missing_ok=True)
    raise BlobStorageError(f"Vercel Blob download failed: {last_error}") from last_error
