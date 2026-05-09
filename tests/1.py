"""
==============================================================================
Библиотечная Система Управления (Library Management System - LMS)
==============================================================================
Описание:
    Полноценная объектно-ориентированная симуляция библиотечной системы,
    демонстрирующая работу с классами, наследованием, композицией,
    методами классов, статическими методами, свойствами, обработкой
    исключений и подробной документацией.

Особенности:
    - Строгая типизация (type hints)
    - Кастомные исключения и перечисления
    - Дата-классы и стандартные классы
    - Логирование и форматирование вывода
    - Аналитический движок для статистики
    - Примеры использования в блоке __main__

Автор: Qwen3.6
Дата создания: 2026-05-09
Версия: 1.0.0
==============================================================================
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Union
from enum import Enum, auto
from dataclasses import dataclass, field

# Настройка базового логгера
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("LMS_Core")


# ==============================================================================
# КАСТОМНЫЕ ИСКЛЮЧЕНИЯ
# ==============================================================================
class LMSBaseException(Exception):
    """Базовый класс для всех исключений библиотечной системы."""
    pass


class ResourceNotFoundError(LMSBaseException):
    """Вызывается, когда запрашиваемый ресурс не найден в базе."""
    pass


class PermissionDeniedError(LMSBaseException):
    """Вызывается при попытке выполнить действие без необходимых прав."""
    pass


class ResourceAlreadyBorrowedError(LMSBaseException):
    """Вызывается при попытке выдать ресурс, который уже находится у читателя."""
    pass


class InvalidReturnDateError(LMSBaseException):
    """Вызывается при некорректной дате возврата или нарушении сроков."""
    pass


# ==============================================================================
# ПЕРЕЧИСЛЕНИЯ И КОНСТАНТЫ
# ==============================================================================
class ItemStatus(Enum):
    """Статусы физического или цифрового ресурса."""
    AVAILABLE = auto()
    BORROWED = auto()
    RESERVED = auto()
    MAINTENANCE = auto()
    ARCHIVED = auto()


class UserRole(Enum):
    """Роли пользователей системы."""
    READER = "reader"
    LIBRARIAN = "librarian"
    ADMIN = "admin"


class ResourceType(Enum):
    """Типы ресурсов в библиотеке."""
    PHYSICAL_BOOK = "book"
    E_BOOK = "ebook"
    AUDIOBOOK = "audio"
    JOURNAL = "journal"


MAX_BORROW_LIMIT = 5
DEFAULT_LOAN_DAYS = 14
LATE_FEE_PER_DAY = 15.0  # в рублях


# ==============================================================================
# БАЗОВЫЕ КЛАССЫ
# ==============================================================================
@dataclass
class BaseEntity:
    """
    Базовый дата-класс для всех сущностей системы.

    Атрибуты:
        entity_id: Уникальный идентификатор (генерируется автоматически)
        created_at: Дата и время создания записи
        updated_at: Дата последнего обновления
    """
    entity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def touch(self) -> None:
        """Обновляет метку времени last_modified."""
        self.updated_at = datetime.now()

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(ID: {self.entity_id[:8]}...)"


class Item(BaseEntity):
    """
    Абстрактный базовый класс для всех библиотечных ресурсов.

    Определяет общий интерфейс для работы с книгами, журналами и цифровыми материалами.
    """

    def __init__(self, title: str, author: str, resource_type: ResourceType) -> None:
        super().__init__()
        self.title = title
        self.author = author
        self.resource_type = resource_type
        self.status = ItemStatus.AVAILABLE
        self.borrowed_by: Optional[str] = None
        self.due_date: Optional[datetime] = None
        self.borrow_history: List[Dict[str, datetime]] = []

    @property
    def is_available(self) -> bool:
        """Проверяет, доступен ли ресурс для выдачи."""
        return self.status == ItemStatus.AVAILABLE

    def _log_action(self, action: str) -> None:
        """Внутренний метод для логирования действий с ресурсом."""
        logger.info(f"[{self.entity_id[:8]}] {action} | Статус: {self.status.name}")

    def borrow(self, user_id: str, loan_days: int = DEFAULT_LOAN_DAYS) -> None:
        """
        Оформляет выдачу ресурса пользователю.

        Args:
            user_id: Идентификатор пользователя
            loan_days: Количество дней, на которые выдается ресурс

        Raises:
            ResourceAlreadyBorrowedError: Если ресурс уже выдан
        """
        if not self.is_available:
            raise ResourceAlreadyBorrowedError(f"Ресурс '{self.title}' недоступен для выдачи.")

        self.status = ItemStatus.BORROWED
        self.borrowed_by = user_id
        self.due_date = datetime.now() + timedelta(days=loan_days)
        self.borrow_history.append({
            "user_id": user_id,
            "borrowed_at": datetime.now(),
            "due_at": self.due_date
        })
        self.touch()
        self._log_action(f"Выдан пользователю {user_id} до {self.due_date.strftime('%Y-%m-%d')}")

    def return_item(self) -> Tuple[float, str]:
        """
        Возвращает ресурс в библиотеку.

        Returns:
            Кортеж (штраф, сообщение о статусе)
        """
        if self.status != ItemStatus.BORROWED:
            raise ResourceNotFoundError("Ресурс не находится в статусе 'выдан'.")

        late_days = 0
        fine = 0.0
        if self.due_date and datetime.now() > self.due_date:
            late_days = (datetime.now() - self.due_date).days
            fine = late_days * LATE_FEE_PER_DAY

        self.status = ItemStatus.AVAILABLE
        self.borrowed_by = None
        self.due_date = None
        self.touch()
        self._log_action(f"Возвращен. Просрочка: {late_days} дн., Штраф: {fine:.2f} руб.")
        return fine, "Возврат успешно обработан."

    def __repr__(self) -> str:
        return (f"<{self.__class__.__name__} '{self.title}' by {self.author} | "
                f"Status: {self.status.name} | ID: {self.entity_id[:8]}>")


# ==============================================================================
# НАСЛЕДУЕМЫЕ КЛАССЫ РЕСУРСОВ
# ==============================================================================
class PhysicalBook(Item):
    """
    Класс для физических книг.

    Добавляет поля: isbn, pages, publisher.
    """

    def __init__(self, title: str, author: str, isbn: str, pages: int, publisher: str) -> None:
        super().__init__(title, author, ResourceType.PHYSICAL_BOOK)
        self.isbn = isbn
        self.pages = pages
        self.publisher = publisher

    def get_catalog_entry(self) -> str:
        """Формирует строку для каталога."""
        return f"[КНИГА] {self.title} / {self.author}. — {self.publisher}, {self.pages} стр. (ISBN: {self.isbn})"


class DigitalResource(Item):
    """
    Класс для цифровых ресурсов (электронные книги, аудио).

    Добавляет поля: file_format, size_mb, download_link.
    """

    def __init__(self, title: str, author: str, file_format: str, size_mb: float, link: str) -> None:
        res_type = ResourceType.AUDIOBOOK if file_format in ("mp3", "wav", "flac") else ResourceType.E_BOOK
        super().__init__(title, author, res_type)
        self.file_format = file_format
        self.size_mb = size_mb
        self.download_link = link

    def generate_access_token(self) -> str:
        """Генерирует временный токен доступа для скачивания."""
        token = uuid.uuid4().hex[:16]
        logger.info(f"[DIGITAL] Сгенерирован токен доступа: {token} для {self.title}")
        return token

    def __str__(self) -> str:
        return f"[{self.resource_type.value.upper()}] {self.title} ({self.file_format.upper()})"


# ==============================================================================
# КЛАССЫ ПОЛЬЗОВАТЕЛЕЙ
# ==============================================================================
class User(BaseEntity):
    """
    Базовый класс пользователя библиотеки.

    Определяет общие поля и методы для всех ролей.
    """

    def __init__(self, username: str, email: str, role: UserRole) -> None:
        super().__init__()
        self.username = username
        self.email = email
        self.role = role
        self.active_borrows: List[str] = []
        self.total_fines: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "User":
        """
        Альтернативный конструктор для создания пользователя из словаря.

        Args:
            data: Словарь с ключами 'username', 'email', 'role'

        Returns:
            Экземпляр класса User
        """
        role_map = {v.value: v for v in UserRole}
        role = role_map.get(data.get("role", "reader"), UserRole.READER)
        return cls(
            username=data["username"],
            email=data["email"],
            role=role
        )

    @staticmethod
    def validate_email(email: str) -> bool:
        """Простая валидация email-адреса."""
        return "@" in email and "." in email.split("@")[-1]

    def borrow_item(self, item: Item) -> None:
        """Добавляет ID ресурса в список активных выдач пользователя."""
        if len(self.active_borrows) >= MAX_BORROW_LIMIT:
            raise PermissionDeniedError("Превышен лимит одновременных выдач.")
        self.active_borrows.append(item.entity_id)
        self.touch()

    def return_item(self, item_id: str) -> None:
        """Удаляет ID ресурса из списка активных выдач."""
        if item_id in self.active_borrows:
            self.active_borrows.remove(item_id)
            self.touch()

    def __str__(self) -> str:
        return f"User({self.username} | {self.role.value} | {len(self.active_borrows)} выдач)"


class Reader(User):
    """Обычный читатель с ограниченным доступом к функциям."""
    def __init__(self, username: str, email: str) -> None:
        super().__init__(username, email, UserRole.READER)


class Librarian(User):
    """Сотрудник библиотеки с расширенными правами."""
    def __init__(self, username: str, email: str, department: str = "General") -> None:
        super().__init__(username, email, UserRole.LIBRARIAN)
        self.department = department

    def add_item_to_catalog(self, library: "Library", item: Item) -> None:
        """Добавляет новый ресурс в каталог библиотеки."""
        library.catalog[item.entity_id] = item
        logger.info(f"[LIBRARIAN] {self.username} добавил '{item.title}' в каталог.")


# ==============================================================================
# ОСНОВНОЙ МЕНЕДЖЕР БИБЛИОТЕКИ
# ==============================================================================
class Library:
    """
    Центральный класс управления библиотекой.

    Отвечает за каталог, выдачу, возврат, поиск ресурсов и управление пользователями.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.catalog: Dict[str, Item] = {}
        self.users: Dict[str, User] = {}
        self.transaction_log: List[Dict] = []
        self._initialize_sample_data()

    def _initialize_sample_data(self) -> None:
        """Создает тестовые данные для демонстрации."""
        # Книги
        b1 = PhysicalBook("Война и мир", "Лев Толстой", "978-5-17-090000-1", 1225, "АСТ")
        b2 = PhysicalBook("Мастер и Маргарита", "Михаил Булгаков", "978-5-17-091111-2", 480, "Эксмо")
        # Цифровые
        d1 = DigitalResource("1984", "Джордж Оруэлл", "pdf", 4.2, "https://lib.internal/1984.pdf")
        d2 = DigitalResource("Аудиокнига: Преступление и наказание", "Ф. Достоевский", "mp3", 850.0, "https://lib.internal/pn.mp3")

        for item in [b1, b2, d1, d2]:
            self.catalog[item.entity_id] = item

        # Пользователи
        u1 = Reader("ivan_petrov", "ivan@example.com")
        u2 = Librarian("anna_k", "anna@library.org", "Cataloging Dept.")
        for user in [u1, u2]:
            self.users[user.entity_id] = user

    @classmethod
    def create_from_config(cls, name: str, config_path: str) -> "Library":
        """
        Фабричный метод для создания библиотеки из конфигурационного файла.
        (В реальном проекте здесь был бы парсинг JSON/YAML)
        """
        logger.info(f"Загрузка конфигурации библиотеки '{name}' из {config_path}")
        return cls(name)

    def find_items(self, query: str) -> List[Item]:
        """
        Поиск ресурсов по названию или автору (регистронезависимо).

        Args:
            query: Строка поиска

        Returns:
            Список найденных ресурсов
        """
        query_lower = query.lower()
        results = [
            item for item in self.catalog.values()
            if query_lower in item.title.lower() or query_lower in item.author.lower()
        ]
        logger.info(f"Поиск '{query}' вернул {len(results)} результатов.")
        return results

    def process_borrow(self, user_id: str, item_id: str) -> bool:
        """
        Оформляет выдачу ресурса пользователю.

        Выполняет проверки прав, доступности и лимитов.

        Returns:
            True если выдача успешна, иначе False
        """
        user = self.users.get(user_id)
        item = self.catalog.get(item_id)

        if not user or not item:
            logger.error("Пользователь или ресурс не найден.")
            return False

        if not isinstance(user, Reader) and not isinstance(user, Librarian):
            logger.error("Неподдерживаемая роль пользователя.")
            return False

        try:
            item.borrow(user_id)
            user.borrow_item(item)
            self._log_transaction("BORROW", user_id, item_id)
            return True
        except LMSBaseException as e:
            logger.warning(f"Ошибка выдачи: {e}")
            return False

    def process_return(self, user_id: str, item_id: str) -> float:
        """
        Обрабатывает возврат ресурса.

        Returns:
            Размер штрафа (если есть)
        """
        user = self.users.get(user_id)
        item = self.catalog.get(item_id)

        if not user or not item:
            raise ResourceNotFoundError("Запись не найдена.")

        fine, msg = item.return_item()
        user.total_fines += fine
        user.return_item(item_id)
        self._log_transaction("RETURN", user_id, item_id, fine=fine)
        return fine

    def get_user_report(self, user_id: str) -> Dict[str, Union[str, int, float]]:
        """Формирует краткую статистику по пользователю."""
        user = self.users.get(user_id)
        if not user:
            raise ResourceNotFoundError(f"Пользователь {user_id} не найден.")

        return {
            "username": user.username,
            "role": user.role.value,
            "active_borrows": len(user.active_borrows),
            "total_fines": user.total_fines,
            "last_active": user.updated_at.isoformat()
        }

    def _log_transaction(self, action: str, user_id: str, item_id: str, **kwargs) -> None:
        """Внутренний метод логирования транзакций."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user_id": user_id,
            "item_id": item_id,
            **kwargs
        }
        self.transaction_log.append(record)

    def __repr__(self) -> str:
        return f"<Library '{self.name}' | Catalog: {len(self.catalog)} | Users: {len(self.users)}>"


# ==============================================================================
# АНАЛИТИЧЕСКИЙ ДВИЖОК
# ==============================================================================
class AnalyticsEngine:
    """
    Класс для генерации отчетов и статистики по данным библиотеки.

    Использует композицию: принимает объект Library и анализирует его состояние.
    """

    def __init__(self, library: Library) -> None:
        self.library = library

    @property
    def catalog_size(self) -> int:
        """Возвращает общее количество ресурсов."""
        return len(self.library.catalog)

    def calculate_availability_rate(self) -> float:
        """Вычисляет процент доступных ресурсов."""
        if not self.library.catalog:
            return 0.0
        available = sum(1 for item in self.library.catalog.values() if item.is_available)
        return round((available / self.catalog_size) * 100, 2)

    def get_popular_authors(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """
        Возвращает список самых популярных авторов по количеству ресурсов.

        Args:
            top_n: Количество топ-авторов

        Returns:
            Список кортежей (автор, количество книг)
        """
        author_counts: Dict[str, int] = {}
        for item in self.library.catalog.values():
            author_counts[item.author] = author_counts.get(item.author, 0) + 1

        sorted_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_authors[:top_n]

    def generate_monthly_report(self) -> str:
        """Генерирует текстовый отчет за текущий месяц."""
        rate = self.calculate_availability_rate()
        top_authors = self.get_popular_authors(3)
        report = (
            f"=== Отчет библиотеки '{self.library.name}' ===\n"
            f"Всего ресурсов: {self.catalog_size}\n"
            f"Доступность: {rate}%\n"
            f"Топ авторы: {', '.join(f'{a} ({c})' for a, c in top_authors)}\n"
            f"Транзакций за сессию: {len(self.library.transaction_log)}\n"
            f"============================================"
        )
        return report

    @staticmethod
    def format_percentage(value: float) -> str:
        """Утилита для форматирования процентов."""
        return f"{value:.1f}%"


# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (МОДУЛЬНЫЙ УРОВЕНЬ)
# ==============================================================================
def calculate_late_fee(days_overdue: int, base_rate: float = LATE_FEE_PER_DAY) -> float:
    """
    Рассчитывает штраф за просрочку.

    Args:
        days_overdue: Количество просроченных дней
        base_rate: Ставка за день

    Returns:
        Сумма штрафа
    """
    if days_overdue <= 0:
        return 0.0
    return round(days_overdue * base_rate, 2)


def validate_user_input(field_name: str, value: str) -> bool:
    """
    Проводит базовую валидацию пользовательского ввода.

    Args:
        field_name: Название поля для логирования
        value: Значение для проверки

    Returns:
        True если валидно, False иначе
    """
    if not isinstance(value, str) or not value.strip():
        logger.warning(f"Некорректный ввод для '{field_name}': пустое значение.")
        return False
    return True


def export_catalog_to_text(library: Library, filename: str = "catalog.txt") -> None:
    """
    Экспортирует каталог в текстовый файл.

    Args:
        library: Объект библиотеки
        filename: Имя файла для сохранения
    """
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Каталог библиотеки: {library.name}\n")
        f.write("=" * 50 + "\n")
        for item in library.catalog.values():
            f.write(f"{item.get_catalog_entry() if isinstance(item, PhysicalBook) else str(item)}\n")
    logger.info(f"Каталог экспортирован в {filename}")


# ==============================================================================
# ДЕМО-СЦЕНАРИЙ ИСПОЛЬЗОВАНИЯ
# ==============================================================================
def run_demo() -> None:
    """Запускает демонстрацию работы всей системы."""
    print("🚀 Запуск демонстрации Библиотечной Системы...\n")

    # 1. Инициализация
    lib = Library("Центральная Городская Библиотека")
    analytics = AnalyticsEngine(lib)

    # 2. Поиск
    print("🔍 Поиск книг по запросу 'мастер':")
    found = lib.find_items("мастер")
    for item in found:
        print(f"  ✓ {item}")

    # 3. Выдача ресурсов
    reader_id = next(uid for uid, u in lib.users.items() if isinstance(u, Reader))
    item_id = found[0].entity_id if found else next(iter(lib.catalog))

    print("\n📖 Оформление выдачи:")
    success = lib.process_borrow(reader_id, item_id)
    print(f"  Выдача успешна: {success}")

    # 4. Возврат с задержкой (симуляция)
    print("\n🔄 Возврат ресурса:")
    fine = lib.process_return(reader_id, item_id)
    print(f"  Штраф: {fine:.2f} руб.")

    # 5. Аналитика
    print("\n📊 Аналитический отчет:")
    print(analytics.generate_monthly_report())

    # 6. Экспорт
    print("\n💾 Экспорт каталога:")
    export_catalog_to_text(lib)

    print("\n✅ Демонстрация завершена успешно.")


if __name__ == "__main__":
    """
    Точка входа в программу.
    Запускает демонстрационный сценарий при прямом вызове скрипта.
    """
    try:
        run_demo()
    except KeyboardInterrupt:
        logger.info("Программа прервана пользователем.")
    except Exception as e:
        logger.critical(f"Необработанная ошибка: {e}", exc_info=True)
