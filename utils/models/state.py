from sqlalchemy import Column, String, Text
from utils.models.base import Base

class State(Base):
    """
    ORM-модель для таблицы 'states'.
    Поля:
      - state_key            : PK VARCHAR
      - comment          : TEXT, nullable
      - parse_mode       : VARCHAR, nullable
      - phrase_admin     : TEXT, not null
      - phrase_manager   : TEXT, not null
      - phrase_user      : TEXT, not null
      - buttons_admin    : TEXT, nullable
      - buttons_manager  : TEXT, nullable
      - buttons_user     : TEXT, nullable
    """
    __tablename__ = "states"

    state_key = Column(String, primary_key=True, index=True)
    comment = Column(Text, nullable=True)
    phrase_admin = Column(Text, nullable=False)
    phrase_manager = Column(Text, nullable=False)
    phrase_user = Column(Text, nullable=False)
    buttons_admin = Column(Text, nullable=True)
    buttons_manager = Column(Text, nullable=True)
    buttons_user = Column(Text, nullable=True)
