"""
Аксай Гриль — Flask backend.

Этап 1: перевод статичного сайта на Flask + SQLite.
Контент пока статичный (рендерится из templates/), база заведена,
но ещё не используется. Следующие этапы добавят админку и
редактируемый контент.
"""
import os
from pathlib import Path

from flask import Flask, render_template, send_from_directory
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data.db"

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="assets",
    static_url_path="/assets",
)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 МБ для загрузок

engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)
Base = declarative_base()


def init_db() -> None:
    """Создать таблицы при первом запуске."""
    Base.metadata.create_all(bind=engine)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/privacy.html")
def privacy():
    return render_template("privacy.html")


@app.route("/uploads/<path:filename>")
def uploads(filename: str):
    uploads_dir = BASE_DIR / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    return send_from_directory(uploads_dir, filename)


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
