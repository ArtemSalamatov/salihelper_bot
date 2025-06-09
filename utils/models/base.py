import logging
import utils.logger # noqa: F401
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import DATABASE_PATH


logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

engine = create_engine(DATABASE_PATH, echo=False)
SessionLocal = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)

def init_db():
    Base.metadata.create_all(bind=engine)
    logger.info("[init_db] Все таблицы созданы (если не существовали)")
