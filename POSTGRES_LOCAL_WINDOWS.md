# PostgreSQL local setup on Windows

The SIMTS application can run on your PC using PostgreSQL. You need PostgreSQL installed and running first.

## Create the SIMTS database

You can use pgAdmin or SQL Shell (psql).

Example SQL:

CREATE USER simts_user WITH PASSWORD 'CHOOSE_A_STRONG_PASSWORD';
CREATE DATABASE simts OWNER simts_user;

Then put this in `.env`:

DATABASE_URL=postgresql+psycopg://simts_user:CHOOSE_A_STRONG_PASSWORD@127.0.0.1:5432/simts

Do not use the example password in a real installation.
