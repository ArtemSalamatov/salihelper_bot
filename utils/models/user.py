import logging
import utils.logger # noqa: F401
from sqlalchemy import Column, Integer, String, Boolean, JSON
from utils.models.base import Base, SessionLocal
from typing import Optional

logger = logging.getLogger(__name__)

class User(Base):
    """
    ORM-модель для таблицы 'users'.
      - user_id            : PK, INTEGER
      - name               : TEXT, not null
      - role               : TEXT, not null
      - state              : TEXT, nullable
      - last_message_id    : INTEGER, nullable
      - is_workday         : BOOLEAN, not null, default=False
      - daily_report_draft : JSON, nullable, default=dict
    """
    __tablename__ = "users"

    user_id            = Column(Integer, primary_key=True, index=True)
    name               = Column(String, nullable=False)
    role               = Column(String, nullable=False)
    state              = Column(String, nullable=True)
    last_message_id    = Column(Integer, nullable=True)
    is_workday         = Column(Boolean, nullable=False, default=False)
    daily_report_draft = Column(JSON, nullable=False, default=dict)

    @classmethod
    def create(cls, user_id: int, role: str, state: str, first_name: str,
               last_name: str | None = None, last_message_id: int | None = None,
               daily_report_draft: dict | None = None
               ) -> "User":
        name = f"{first_name} {last_name[0]}." if last_name else first_name
        if not daily_report_draft:
            daily_report_draft = {
                "date": None,
                "author": f"{name}({user_id})",
                "wolt": None,
                "bolt": None,
                "yandex": None,
                "temp": None,
                "weather_label": None,
                "overwrite": False
            }
        with SessionLocal.begin() as session:
                existing = session.get(User, user_id)
                if existing:
                    return existing
                new_user = User(
                    user_id=user_id,
                    name=name,
                    role=role,
                    state=state,
                    last_message_id=last_message_id,
                    daily_report_draft=daily_report_draft
                )
                session.add(new_user)
                return new_user
    @classmethod
    def get(cls, user_id: int) -> Optional["User"]:
        with SessionLocal() as session:
            return session.get(User, user_id)

    def set_state(self, state: str):
        try:
            with SessionLocal.begin() as session:
                old_state = self.state
                self.state = state
                session.merge(self)
                logger.info(f"[User.set_state] Обновлено состояние пользователя {self.name}({self.user_id}): "
                            f"'{old_state}' → '{state}'")
        except Exception as e:
            logger.exception(f"[User.set_state] Ошибка при обновлении состояния пользователя "
                             f"{self.name}({self.user_id}): {e}")

    def set_role(self, role: str):
        try:
            with SessionLocal.begin() as session:
                old_role = self.role
                self.role = role
                session.merge(self)
                logger.info(f"[User.set_state] Обновлена роль пользователя "
                            f"{self.name}({self.user_id}): '{old_role}' → '{role}'")
        except Exception as e:
            logger.exception(f"[User.set_state] Ошибка при обновлении роли пользователя "
                             f"{self.name}({self.user_id}): {e}")

    def toggle_workday(self, flag: bool):
        try:
            with SessionLocal.begin() as session:
                old_toggle = "Да" if self.is_workday else "Нет"
                self.is_workday = flag
                session.merge(self)
                new_toogle = "Да" if self.is_workday else "Нет"
                logger.info(f"[User.set_state] Обновлён тумблер 'Рабочий день' пользователя "
                            f"{self.name}({self.user_id}): '{old_toggle}' → '{new_toogle}'")
        except Exception as e:
            logger.exception(f"[User.set_state] Ошибка при обновлении тумблера 'Рабочий день' "
                             f"пользователя {self.name}({self.user_id}): {e}")

    def set_last_message_id(self, message_id: int) -> None:
        try:
            with SessionLocal.begin() as session:
                old_msg_id = self.last_message_id
                self.last_message_id = message_id
                session.merge(self)
                logger.info(
                    f"[User.set_last_message_id] Обновлён message_id для пользователя {self.name}({self.user_id}): "
                    f"{old_msg_id} → {message_id}"
                )
        except Exception as e:
            logger.exception(
                f"[User.set_last_message_id] Ошибка при сохранении message_id пользователя "
                f"{self.name}({self.user_id}): {e}"
            )

    def write_to_draft(self, **kwargs) -> None:
        try:
            with SessionLocal.begin() as session:
                self.daily_report_draft.update(kwargs)
                session.merge(self)
                logger.info(
                    f"[User.write_to_draft] Обновлён черновик пользователя {self.name}({self.user_id}): {kwargs}"
                )
        except Exception as e:
            logger.exception(
                f"[User.write_to_draft] Ошибка при обновлении черновика пользователя {self.name}({self.user_id}): {e}"
            )

    def clear_draft(self) -> None:
        """
        Очищает поля черновика daily_report_draft, оставляя только актуальные ключи со значениями по умолчанию.
        """
        try:
            with SessionLocal.begin() as session:
                self.daily_report_draft.update({
                    "date": None,
                    "wolt": None,
                    "bolt": None,
                    "yandex": None,
                    "temp": None,
                    "weather_label": None,
                    "overwrite": False
                })
                session.merge(self)
                logger.info(f"[User.clear_draft] Черновик пользователя {self.name}({self.user_id}) очищен")
        except Exception as e:
            logger.exception(
                f"[User.clear_draft] Ошибка при очистке черновика пользователя {self.name}({self.user_id}): {e}"
            )