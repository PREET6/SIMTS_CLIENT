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
