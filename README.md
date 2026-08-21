# SIMTS Production V3 — PostgreSQL First

This is the Phase 2 production-preparation build of SIMTS. PostgreSQL is the recommended and default database configuration. SQLite is retained only as a fallback for legacy/local recovery; it is not the recommended production database.

## Run on your Windows PC with PostgreSQL

1. Install PostgreSQL and make sure the PostgreSQL service is running.
2. Create a database and user, for example:
   - database: `simts`
   - user: `simts_user`
   - password: choose your own strong password
3. Copy `.env.example` to `.env`.
4. Edit `.env` and replace `YOUR_PASSWORD` in `DATABASE_URL` and replace `REPLACE_WITH_A_LONG_RANDOM_SECRET` with a long random secret.
5. Create the virtual environment:
   `python -m venv venv`
6. Activate it:
   `venv\\Scripts\\Activate.ps1`
7. Install dependencies:
   `pip install -r requirements.txt`
8. Start the app:
   `python app.py`
9. Open:
   `http://127.0.0.1:5000/admin/setup`
10. Create your administrator account.

The application creates its PostgreSQL tables automatically on first start.

## Existing SQLite data

Do NOT delete your working SQLite database. Back it up first. Then migrate it into an EMPTY PostgreSQL database:

PowerShell:
`$env:SOURCE_DATABASE_URL='sqlite:///instance/simts.db'`
`$env:TARGET_DATABASE_URL='postgresql+psycopg://simts_user:YOUR_PASSWORD@127.0.0.1:5432/simts'`
`python migrate_sqlite_to_postgres.py`

Uploaded certificate files are stored outside the database and must be copied separately.

## Important

- Never commit `.env`.
- Never use a production database password in source code.
- Keep PostgreSQL reachable only from the application/server where possible.
- Use HTTPS before enabling `SESSION_COOKIE_SECURE=1`.
- Use a production WSGI server when hosting publicly; do not use Flask's development server as the production server.
- No web application can honestly be called 100% secure. Security must be maintained through updates, backups, access control, monitoring and deployment configuration.

## Vercel + Neon + Vercel Blob deployment

This version supports persistent certificate and marksheet PDF storage on Vercel using a **private Vercel Blob store**. The existing `Certificate.file_name` and `Marksheet.file_name` database columns are reused: locally they contain filenames, while on Vercel they contain the private Blob URL returned after upload.

### 1. Create a private Blob store

In the Vercel project, open **Storage → Create Database → Blob**, choose **Private**, and create the store. Vercel adds `BLOB_READ_WRITE_TOKEN` to the project when the store is connected to that project. Private Blob storage is recommended for sensitive documents because reads require authentication. See the official Vercel documentation: https://vercel.com/docs/vercel-blob/private-storage

### 2. Required Vercel environment variables

Set these in **Project → Settings → Environment Variables**:

- `DATABASE_URL` — your Neon PostgreSQL connection string
- `SECRET_KEY` — a long random application secret
- `BLOB_READ_WRITE_TOKEN` — the token from the private Vercel Blob store

The numeric settings are optional because `config.py` provides safe defaults. Do not create them with empty values.

### 3. Important upload limit

Vercel Functions have a request payload limit. This project therefore uses a 4 MB default `MAX_CONTENT_LENGTH` on Vercel. Keep certificate/marksheet uploads below that size when using the admin form. Vercel documents a 4.5 MB function payload limit and recommends direct client uploads for larger files.

### 4. Existing local PDFs

If Neon already contains certificate/marksheet records whose `file_name` values refer to files in the old local `uploads/` directory, run the included one-time migration script before deleting the local PDFs:

```powershell
$env:DATABASE_URL="your-neon-url"
$env:BLOB_READ_WRITE_TOKEN="your-vercel-blob-token"
python migrate_files_to_blob.py
```

The script uploads the existing PDFs and updates the existing database rows with their Blob URLs.

### 5. Local development

Without `BLOB_READ_WRITE_TOKEN`, local development continues to use the normal `uploads/` directory. The same application can therefore be run locally and on Vercel without changing the verification URLs.

### 6. Deployment

Commit and push the updated files to GitHub. Vercel will automatically create a new deployment from the connected repository. After deployment, test:

- Public certificate verification
- Public marksheet verification
- Admin certificate upload
- Admin marksheet upload
- View certificate PDF
- View marksheet PDF
- Edit/delete certificate and marksheet

Private Blob files are delivered through the Flask function rather than exposing their storage URL directly to visitors.

### Private Blob viewing fix

The certificate and marksheet view routes download private Blob objects server-side with the `BLOB_READ_WRITE_TOKEN` Authorization header and then stream the temporary PDF through Flask. A private Blob URL must not be redirected directly to the browser; direct unauthenticated access returns HTTP 403.
