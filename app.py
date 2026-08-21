import os
import sys

from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import csrf, db, limiter, login_manager
from models import Admin
from routes.admin import admin_bp
from routes.auth import auth_bp
from routes.public import public_bp


def sync_database_schema(app):
    """Ensure all tables and newly added columns exist in PostgreSQL or SQLite."""
    with app.app_context():
        try:
            # 1. Create any newly added tables (like marksheet)
            db.create_all()

            # 2. Add any newly introduced columns to existing tables dynamically
            with db.engine.connect() as conn:
                dialect = db.engine.dialect.name
                if dialect == 'postgresql':
                    conn.execute(db.text("""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='student' AND column_name='marksheet_number') THEN
                                ALTER TABLE student ADD COLUMN marksheet_number VARCHAR(100);
                                CREATE UNIQUE INDEX IF NOT EXISTS ix_student_marksheet_number ON student (marksheet_number);
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='student' AND column_name='marksheet_issue_date') THEN
                                ALTER TABLE student ADD COLUMN marksheet_issue_date DATE;
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='student' AND column_name='gender') THEN
                                ALTER TABLE student ADD COLUMN gender VARCHAR(30);
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='student' AND column_name='academic_session') THEN
                                ALTER TABLE student ADD COLUMN academic_session VARCHAR(50);
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='student' AND column_name='admission_date') THEN
                                ALTER TABLE student ADD COLUMN admission_date DATE;
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='student' AND column_name='completion_status') THEN
                                ALTER TABLE student ADD COLUMN completion_status VARCHAR(50) DEFAULT 'ongoing';
                            END IF;
                        END $$;
                    """))
                    conn.commit()
                elif dialect == 'sqlite':
                    result = conn.execute(db.text("PRAGMA table_info(student)")).fetchall()
                    existing_cols = [row[1] for row in result]
                    if 'marksheet_number' not in existing_cols:
                        conn.execute(db.text("ALTER TABLE student ADD COLUMN marksheet_number VARCHAR(100)"))
                    if 'marksheet_issue_date' not in existing_cols:
                        conn.execute(db.text("ALTER TABLE student ADD COLUMN marksheet_issue_date DATE"))
                    if 'gender' not in existing_cols:
                        conn.execute(db.text("ALTER TABLE student ADD COLUMN gender VARCHAR(30)"))
                    if 'academic_session' not in existing_cols:
                        conn.execute(db.text("ALTER TABLE student ADD COLUMN academic_session VARCHAR(50)"))
                    if 'admission_date' not in existing_cols:
                        conn.execute(db.text("ALTER TABLE student ADD COLUMN admission_date DATE"))
                    if 'completion_status' not in existing_cols:
                        conn.execute(db.text("ALTER TABLE student ADD COLUMN completion_status VARCHAR(50) DEFAULT 'ongoing'"))
                    conn.commit()
        except Exception as e:
            db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
            if 'postgresql' in db_url:
                print(f"\n[!] Notice during schema sync: {e}")
                print("    Make sure your PostgreSQL Windows Service is started.\n")


def create_app(config_class=Config):
    app = Flask(__name__)
    if config_class:
        app.config.from_object(config_class)

    if not app.config.get('SECRET_KEY') or app.config['SECRET_KEY'] == 'CHANGE_THIS_IN_ENV':
        if not app.config.get('TESTING'):
            raise RuntimeError('Set a strong SECRET_KEY in .env before running SIMTS.')

    os.makedirs(app.instance_path, exist_ok=True)
    if app.config.get('UPLOAD_FOLDER'):
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    if app.config.get('BACKUP_FOLDER'):
        os.makedirs(app.config['BACKUP_FOLDER'], exist_ok=True)

    if app.config.get('TRUST_PROXY'):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(Admin, int(user_id))
        except (ValueError, TypeError):
            return None

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "script-src 'self'; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "object-src 'none'"
        )
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    if not app.config.get('TESTING'):
        sync_database_schema(app)

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = app.config.get('DEBUG', False)
    
    print("\n" + "=" * 60)
    print("  SIMTS Academic & Verification Portal")
    print("=" * 60)
    print(f"  * Public Portal : http://127.0.0.1:{port}")
    print(f"  * Admin Setup   : http://127.0.0.1:{port}/admin/setup")
    print(f"  * Admin Login   : http://127.0.0.1:{port}/admin/login")
    print(f"  * Database      : {app.config.get('SQLALCHEMY_DATABASE_URI', '').split('@')[-1]}")
    print("=" * 60)
    print("  Server is active. Open http://127.0.0.1:5000 in your browser.")
    print("  (Press CTRL+C in this terminal to stop the server)\n")
    sys.stdout.flush()
    
    app.run(host='127.0.0.1', port=port, debug=debug)
