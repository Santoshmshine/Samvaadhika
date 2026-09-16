"""
Samvaadhika - Database initialization and session management.
Uses SQLite via SQLAlchemy — zero-config, single-file, no DB server needed.
"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + FastAPI
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables and seed the default admin user if not present."""
    from app.models import User, Job, GlossaryEntry, AuditLog  # noqa: F401 — needed for metadata
    Base.metadata.create_all(bind=engine)
    columns = {column["name"] for column in inspect(engine).get_columns("jobs")}
    if "video_output_path" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE jobs ADD COLUMN video_output_path VARCHAR(512)"))
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    if "is_deleted" not in user_columns:
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE users ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0"
            ))
    if "failed_login_attempts" not in user_columns:
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0"
            ))
    _seed_admin()


def _seed_admin():
    """Create the default admin account on first run."""
    from app.models import User
    from app.auth import get_password_hash
    from app.config import DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_EMAIL

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first()
        if not existing:
            admin = User(
                username=DEFAULT_ADMIN_USERNAME,
                email=DEFAULT_ADMIN_EMAIL,
                hashed_password=get_password_hash(DEFAULT_ADMIN_PASSWORD),
                role="admin",
                is_active=True,
                is_approved=True,
                full_name="System Administrator",
            )
            db.add(admin)
            db.commit()
            print(f"[Samvaadhika] Default admin created: {DEFAULT_ADMIN_USERNAME}")
    finally:
        db.close()
