import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'CHANGE_THIS_IN_ENV')
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///' + str(BASE_DIR / 'instance' / 'simts.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }

    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(BASE_DIR / 'uploads'))
    BACKUP_FOLDER = os.getenv('BACKUP_FOLDER', str(BASE_DIR / 'backups'))
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', '10485760'))

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

    WTF_CSRF_TIME_LIMIT = int(os.getenv('WTF_CSRF_TIME_LIMIT', '3600'))
    RATELIMIT_STORAGE_URI = os.getenv('RATELIMIT_STORAGE_URI', 'memory://')

    DEBUG = env_bool('FLASK_DEBUG', False)
    TESTING = env_bool('FLASK_TESTING', False)
    TRUST_PROXY = env_bool('TRUST_PROXY', False)
    MAX_FORM_MEMORY_SIZE = int(os.getenv('MAX_FORM_MEMORY_SIZE', '500000'))
    MAX_FORM_PARTS = int(os.getenv('MAX_FORM_PARTS', '100'))
