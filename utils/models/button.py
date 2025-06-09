from sqlalchemy import Column, String
from utils.models.base import Base

class Button(Base):
    """
    ORM-модель для таблицы 'ru_buttons'.
    Поля:
      - key   : PK VARCHAR
      - label : VARCHAR, not null
    """
    __tablename__ = "ru_buttons"

    key   = Column(String, primary_key=True, index=True)
    label = Column(String, nullable=False)
