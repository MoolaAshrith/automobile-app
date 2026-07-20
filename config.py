import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True

    DB_USER = os.environ.get("DB_USER", "automobile_user")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "automobile_pass")
    DB_HOST = os.environ.get("DB_HOST", "automobile-db")
    DB_PORT = os.environ.get("DB_PORT", "3306")
    DB_NAME = os.environ.get("DB_NAME", "automobile_db")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{os.environ.get('DB_USER', 'automobile_user')}"
        f":{os.environ.get('DB_PASSWORD', 'automobile_pass')}"
        f"@{os.environ.get('DB_HOST', 'automobile-db')}"
        f":{os.environ.get('DB_PORT', '3306')}"
        f"/{os.environ.get('DB_NAME', 'automobile_db')}"
    )


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
