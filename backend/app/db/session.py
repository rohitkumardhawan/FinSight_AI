import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

logger = logging.getLogger("finsight.db")

db_url = settings.get_sqlalchemy_database_url()

# SQLAlchemy 2.x Engine with Neon-tailored connection pooling
# pool_pre_ping: Ensures connections are tested before checkout (vital when Neon suspends/resumes compute)
# pool_recycle: Recycles connections before timeouts occur
if db_url:
    engine = create_engine(
        db_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    logger.warning("DATABASE_URL is not set. Engine initialized in offline mode.")
    engine = None
    SessionLocal = None

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session and safely closes it
    upon request completion.
    """
    if SessionLocal is None:
        raise RuntimeError("Database session factory is not configured. Check DATABASE_URL.")
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_connection() -> dict:
    """
    Executes a lightweight query to verify the live database health and latency.
    """
    if engine is None:
        return {"status": "unconfigured", "error": "DATABASE_URL is not configured"}

    import time
    start_time = time.time()
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT NOW() as current_time, current_database() as db_name, version() as pg_version")
            ).fetchone()
            latency_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "status": "healthy",
                "database": result[1],
                "version": result[2].split(",")[0],
                "server_time": str(result[0]),
                "latency_ms": latency_ms,
                "branch": settings.NEON_BRANCH,
            }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        # Do not expose raw credentials or sensitive stack traces in the response
        safe_msg = str(e).split("\n")[0]
        return {
            "status": "unhealthy",
            "error": safe_msg,
            "branch": settings.NEON_BRANCH,
        }
