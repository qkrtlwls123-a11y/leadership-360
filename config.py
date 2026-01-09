import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "Zmfflr19!@")
    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = os.environ.get("DB_PORT", "3306")
    DB_NAME = os.environ.get("DB_NAME", "test")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FORMS_CONFIG_PATH = os.environ.get(
        "FORMS_CONFIG_PATH", os.path.join(BASE_DIR, "forms_config.json")
    )
    GOOGLE_SERVICE_ACCOUNT = os.environ.get(
        "GOOGLE_SERVICE_ACCOUNT", os.path.join(BASE_DIR, "service_account.json")
    )
