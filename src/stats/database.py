from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.stats.models import Base

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    Base.metadata.create_all(engine)
