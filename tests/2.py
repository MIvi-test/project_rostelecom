"""
Система управления библиотекой

Данный модуль реализует объектно-ориентированную модель для управления
библиотечным фондом, пользователями и операциями выдачи/возврата книг.
Содержит классы Book, User, Library, Transaction, а также кастомные
исключения для обработки ошибок. Демонстрационная функция main() показывает
основные сценарии использования системы.

Версия: 1.0
"""

import datetime
import re
from typing import List, Optional, Dict, Any


class BookNotAvailable(Exception):
    """Исключение, выбрасываемое при попытке взять недоступную книгу."""

    def __init__(self, isbn: str, message: str = "Книга недоступна для выдачи."):
        self.isbn = isbn
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"BookNotAvailable(ISBN: {self.isbn}): {self.message}"


class UserNotFound(Exception):
    """Исключение, выбрасываемое при обращении к несуществующему пользователю."""

    def __init__(self, user_id: str, message: str = "Пользователь не найден."):
        self.user_id = user_id
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"UserNotFound(ID: {self.user_id}): {self.message}"


class MaxBorrowLimitExceeded(Exception):
    """Исключение, выбрасываемое при превышении лимита книг у пользователя."""

    def __init__(self, user_id: str, limit: int, message: str = "Превышен лимит выданных книг."):
        self.user_id = user_id
        self.limit = limit
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"MaxBorrowLimitExceeded(ID: {self.user_id}, лимит: {self.limit}): {self.message}"


class Book:
    """
    Класс, представляющий книгу в библиотеке.

    Атрибуты:
        title (str): Название книги.
        author (str): Автор книги.
        isbn (str): Международный стандартный книжный номер (уникальный).
        year (int): Год издания.
        genre (str): Жанр книги.
        total_copies (int): Общее количество экземпляров.
        available_copies (int): Количество доступных экземпляров.
    """

    def __init__(self, title: str, author: str, isbn: str, year: int, genre: str, total_copies: int = 1):
        """
        Инициализация объекта книги.

        Параметры:
            title (str): Название.
            author (str): Автор.
            isbn (str): ISBN (должен быть валидным).
            year (int): Год издания.
            genre (str): Жанр.
            total_copies (int): Общее количество копий (по умолчанию 1).

        Исключения:
            ValueError: Если isbn не проходит валидацию.
        """
        if not self._validate_isbn(isbn):
            raise ValueError(f"Некорректный ISBN: {isbn}")
        self.title = title
        self.author = author
        self.isbn = isbn
        self.year = year
        self.genre = genre
        self.total_copies = total_copies
        self.available_copies = total_copies  # изначально все доступны

    @staticmethod
    def _validate_isbn(isbn: str) -> bool:
        """
        Проверяет корректность ISBN-10 или ISBN-13 (упрощённая проверка).

        Параметры:
            isbn (str): Строка ISBN для проверки.

        Возвращает:
            bool: True, если формат соответствует цифровому ISBN-10 или ISBN-13,
                  иначе False.
        """
        clean_isbn = isbn.replace("-", "").replace(" ", "")
        if len(clean_isbn) == 10:
            return clean_isbn[:-1].isdigit() and (clean_isbn[-1].isdigit() or clean_isbn[-1].upper() == 'X')
        elif len(clean_isbn) == 13:
            return clean_isbn.isdigit()
        return False

    def borrow(self) -> bool:
        """
        Попытка выдачи книги (уменьшение количества доступных экземпляров).

        Возвращает:
            bool: True, если выдача успешна.

        Исключения:
            BookNotAvailable: Если нет доступных экземпляров.
        """
        if self.available_copies > 0:
            self.available_copies -= 1
            return True
        else:
            raise BookNotAvailable(self.isbn, "Нет доступных экземпляров.")

    def return_book(self) -> None:
        """
        Возврат книги в библиотеку (увеличение доступных экземпляров).
        Не позволяет превысить общее количество копий.
        """
        if self.available_copies < self.total_copies:
            self.available_copies += 1

    def update_info(self, title: Optional[str] = None, author: Optional[str] = None,
                    year: Optional[int] = None, genre: Optional[str] = None,
                    total_copies: Optional[int] = None) -> None:
        """
        Обновление информации о книге. Изменяются только переданные поля.

        Параметры:
            title (Optional[str]): Новое название.
            author (Optional[str]): Новый автор.
            year (Optional[int]): Новый год издания.
            genre (Optional[str]): Новый жанр.
            total_copies (Optional[int]): Новое общее количество копий.
                Если значение меньше текущего available_copies, вызывается ValueError.
        """
        if title is not None:
            self.title = title
        if author is not None:
            self.author = author
        if year is not None:
            self.year = year
        if genre is not None:
            self.genre = genre
        if total_copies is not None:
            if total_copies < self.total_copies - self.available_copies:
                raise ValueError("Нельзя уменьшить общее количество ниже числа выданных экземпляров.")
            diff = total_copies - self.total_copies
            self.total_copies = total_copies
            self.available_copies += diff
            if self.available_copies > self.total_copies:
                self.available_copies = self.total_copies

    def __str__(self) -> str:
        """
        Строковое представление книги для удобного вывода.

        Возвращает:
            str: Информация о книге в формате 'Название (Автор, год), ISBN, жанр, доступно/всего'.
        """
        return (f"'{self.title}' — {self.author} ({self.year}), "
                f"ISBN: {self.isbn}, {self.genre}, "
                f"Доступно: {self.available_copies}/{self.total_copies}")

    def __repr__(self) -> str:
        """
        Официальное строковое представление объекта Book.

        Возвращает:
            str: Строка, показывающая конструктор объекта.
        """
        return (f"Book(title={self.title!r}, author={self.author!r}, isbn={self.isbn!r}, "
                f"year={self.year!r}, genre={self.genre!r}, total_copies={self.total_copies!r})")

    def to_dict(self) -> Dict[str, Any]:
        """
        Сериализация книги в словарь.

        Возвращает:
            dict: Словарь с полями книги.
        """
        return {
            "title": self.title,
            "author": self.author,
            "isbn": self.isbn,
            "year": self.year,
            "genre": self.genre,
            "total_copies": self.total_copies,
            "available_copies": self.available_copies
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Book':
        """
        Создание объекта Book из словаря.

        Параметры:
            data (dict): Словарь, содержащий ключи, соответствующие полям книги.

        Возвращает:
            Book: Новый объект книги.
        """
        book = cls(
            title=data["title"],
            author=data["author"],
            isbn=data["isbn"],
            year=data["year"],
            genre=data["genre"],
            total_copies=data.get("total_copies", 1)
        )
        book.available_copies = data.get("available_copies", book.total_copies)
        return book


class User:
    """
    Класс, представляющий пользователя библиотеки.

    Атрибуты:
        user_id (str): Уникальный идентификатор пользователя.
        name (str): Имя пользователя.
        _email (str): Адрес электронной почты (приватный).
        _borrowed_isbns (List[str]): Список ISBN взятых книг.
        MAX_BORROW_LIMIT (int): Максимальное количество одновременно взятых книг.
    """

    MAX_BORROW_LIMIT = 5  # лимит книг на пользователя

    def __init__(self, user_id: str, name: str, email: str):
        """
        Инициализация объекта пользователя.

        Параметры:
            user_id (str): Уникальный ID.
            name (str): Имя.
            email (str): Email (должен быть валидным).

        Исключения:
            ValueError: При некорректном email.
        """
        self.user_id = user_id
        self.name = name
        self.email = email  # вызовет сеттер с валидацией
        self._borrowed_isbns: List[str] = []

    @property
    def email(self) -> str:
        """Возвращает текущий email пользователя."""
        return self._email

    @email.setter
    def email(self, value: str) -> None:
        """
        Устанавливает email с базовой валидацией.

        Параметры:
            value (str): Новый email.

        Исключения:
            ValueError: Если email не соответствует шаблону.
        """
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", value):
            raise ValueError(f"Некорректный email: {value}")
        self._email = value

    @property
    def borrowed_books(self) -> List[str]:
        """Возвращает список ISBN взятых книг."""
        return self._borrowed_isbns.copy()

    def borrow_book(self, isbn: str) -> None:
        """
        Добавляет книгу в список взятых пользователем.

        Параметры:
            isbn (str): ISBN книги.

        Исключения:
            MaxBorrowLimitExceeded: Если достигнут лимит выдачи.
        """
        if len(self._borrowed_isbns) >= self.MAX_BORROW_LIMIT:
            raise MaxBorrowLimitExceeded(self.user_id, self.MAX_BORROW_LIMIT)
        self._borrowed_isbns.append(isbn)

    def return_book(self, isbn: str) -> None:
        """
        Удаляет книгу из списка взятых пользователем.

        Параметры:
            isbn (str): ISBN книги.

        Исключения:
            ValueError: Если книга отсутствует в списке.
        """
        try:
            self._borrowed_isbns.remove(isbn)
        except ValueError:
            raise ValueError(f"У пользователя {self.user_id} нет книги {isbn}")

    def has_book(self, isbn: str) -> bool:
        """
        Проверяет, взял ли пользователь книгу с данным ISBN.

        Параметры:
            isbn (str): ISBN для проверки.

        Возвращает:
            bool: True, если книга есть в списке.
        """
        return isbn in self._borrowed_isbns

    def __str__(self) -> str:
        """
        Строковое представление пользователя.

        Возвращает:
            str: ID, имя, email и количество взятых книг.
        """
        return (f"User(ID: {self.user_id}, Name: {self.name}, "
                f"Email: {self.email}, Books borrowed: {len(self._borrowed_isbns)})")

    def to_dict(self) -> Dict[str, Any]:
        """
        Сериализация пользователя в словарь.

        Возвращает:
            dict: Словарь с полями пользователя.
        """
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "borrowed_isbns": self._borrowed_isbns
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """
        Создание объекта User из словаря.

        Параметры:
            data (dict): Словарь с полями пользователя.

        Возвращает:
            User: Новый объект пользователя.
        """
        user = cls(data["user_id"], data["name"], data["email"])
        user._borrowed_isbns = data.get("borrowed_isbns", [])
        return user


class Transaction:
    """
    Класс для записи операций выдачи и возврата книг.

    Атрибуты:
        timestamp (datetime.datetime): Дата и время операции.
        user_id (str): Идентификатор пользователя.
        isbn (str): ISBN книги.
        action (str): Тип операции ('borrow' или 'return').
    """

    def __init__(self, user_id: str, isbn: str, action: str):
        """
        Инициализация записи о транзакции.

        Параметры:
            user_id (str): ID пользователя.
            isbn (str): ISBN книги.
            action (str): Тип операции (допустимы 'borrow' или 'return').

        Исключения:
            ValueError: При недопустимом действии.
        """
        if action not in ("borrow", "return"):
            raise ValueError("Допустимые действия: 'borrow', 'return'")
        self.timestamp = datetime.datetime.now()
        self.user_id = user_id
        self.isbn = isbn
        self.action = action

    def __str__(self) -> str:
        """
        Строковое представление транзакции.

        Возвращает:
            str: Отформатированная запись с датой, пользователем, ISBN и действием.
        """
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] User {self.user_id} {self.action} ISBN {self.isbn}"


class Library:
    """
    Главный класс, управляющий книгами, пользователями и операциями.

    Хранит коллекции книг и пользователей, а также историю транзакций.
    Предоставляет методы для добавления/удаления книг и пользователей,
    выдачи и возврата, поиска и генерации отчётов.
    """

    def __init__(self, name: str = "Central Library"):
        """
        Инициализация библиотеки.

        Параметры:
            name (str): Название библиотеки.
        """
        self.name = name
        self.books: Dict[str, Book] = {}     # ключ - ISBN
        self.users: Dict[str, User] = {}     # ключ - user_id
        self.transactions: List[Transaction] = []

    def add_book(self, book: Book) -> None:
        """
        Добавляет книгу в библиотечный фонд. Если ISBN уже существует,
        увеличивает общее количество копий.

        Параметры:
            book (Book): Объект книги.
        """
        if book.isbn in self.books:
            existing = self.books[book.isbn]
            existing.total_copies += book.total_copies
            existing.available_copies += book.total_copies
        else:
            self.books[book.isbn] = book

    def remove_book(self, isbn: str) -> bool:
        """
        Удаляет книгу из библиотеки.

        Параметры:
            isbn (str): ISBN книги для удаления.

        Возвращает:
            bool: True, если книга удалена, иначе False (если не найдена).
        """
        if isbn in self.books:
            del self.books[isbn]
            return True
        return False

    def register_user(self, user: User) -> None:
        """
        Регистрирует нового пользователя.

        Параметры:
            user (User): Объект пользователя.

        Исключения:
            ValueError: Если пользователь с таким ID уже существует.
        """
        if user.user_id in self.users:
            raise ValueError(f"Пользователь с ID {user.user_id} уже существует.")
        self.users[user.user_id] = user

    def remove_user(self, user_id: str) -> bool:
        """
        Удаляет пользователя из системы.

        Параметры:
            user_id (str): ID пользователя.

        Возвращает:
            bool: True в случае успеха, False если пользователь не найден.

        Исключения:
            ValueError: Если у пользователя есть невозвращённые книги.
        """
        user = self.users.get(user_id)
        if not user:
            return False
        if user.borrowed_books:
            raise ValueError(f"Пользователь {user_id} имеет невозвращённые книги.")
        del self.users[user_id]
        return True

    def borrow_book(self, user_id: str, isbn: str) -> Transaction:
        """
        Выдача книги пользователю. Проверяет доступность книги и лимиты,
        обновляет состояние книги и пользователя.

        Параметры:
            user_id (str): ID пользователя.
            isbn (str): ISBN книги.

        Возвращает:
            Transaction: Запись о транзакции выдачи.

        Исключения:
            UserNotFound: Если пользователь не найден.
            BookNotAvailable: Если книга отсутствует или недоступна.
            MaxBorrowLimitExceeded: Если превышен лимит пользователя.
        """
        user = self.users.get(user_id)
        if not user:
            raise UserNotFound(user_id)
        book = self.books.get(isbn)
        if not book:
            raise BookNotAvailable(isbn, "Книга не найдена в фонде.")
        if user.has_book(isbn):
            raise ValueError(f"Пользователь уже имеет эту книгу (ISBN {isbn}).")

        # Валидация лимита и доступности происходит внутри методов
        book.borrow()
        try:
            user.borrow_book(isbn)
        except MaxBorrowLimitExceeded:
            # Откатываем выдачу книги
            book.return_book()
            raise

        transaction = Transaction(user_id, isbn, "borrow")
        self.transactions.append(transaction)
        return transaction

    def return_book(self, user_id: str, isbn: str) -> Transaction:
        """
        Возврат книги пользователем.

        Параметры:
            user_id (str): ID пользователя.
            isbn (str): ISBN книги.

        Возвращает:
            Transaction: Запись о транзакции возврата.

        Исключения:
            UserNotFound: Если пользователь не найден.
            ValueError: Если у пользователя нет этой книги.
        """
        user = self.users.get(user_id)
        if not user:
            raise UserNotFound(user_id)
        book = self.books.get(isbn)
        if not book:
            raise ValueError(f"Книга ISBN {isbn} не найдена в библиотеке.")

        user.return_book(isbn)
        book.return_book()

        transaction = Transaction(user_id, isbn, "return")
        self.transactions.append(transaction)
        return transaction

    def search_books(self, by: str = "title", value: str = "") -> List[Book]:
        """
        Поиск книг по заданному критерию (название, автор, жанр).

        Параметры:
            by (str): Критерий поиска ('title', 'author', 'genre').
            value (str): Значение для поиска (регистронезависимое частичное совпадение).

        Возвращает:
            List[Book]: Список найденных книг.
        """
        result = []
        value_lower = value.lower()
        for book in self.books.values():
            if by == "title" and value_lower in book.title.lower():
                result.append(book)
            elif by == "author" and value_lower in book.author.lower():
                result.append(book)
            elif by == "genre" and value_lower in book.genre.lower():
                result.append(book)
        return result

    def get_user_borrowed_books(self, user_id: str) -> List[Book]:
        """
        Возвращает список книг, взятых пользователем.

        Параметры:
            user_id (str): ID пользователя.

        Возвращает:
            List[Book]: Список объектов Book, которые на руках у пользователя.

        Исключения:
            UserNotFound: Если пользователь не найден.
        """
        user = self.users.get(user_id)
        if not user:
            raise UserNotFound(user_id)
        return [self.books[isbn] for isbn in user.borrowed_books if isbn in self.books]

    def generate_inventory_report(self) -> str:
        """
        Генерация текстового отчёта по инвентаризации фонда.

        Возвращает:
            str: Отформатированный отчёт с перечислением всех книг и их доступностью.
        """
        lines = [f"=== Inventory Report for {self.name} ===", f"Date: {datetime.date.today()}"]
        total_books = sum(b.total_copies for b in self.books.values())
        total_available = sum(b.available_copies for b in self.books.values())
        lines.append(f"Total distinct titles: {len(self.books)}")
        lines.append(f"Total copies: {total_books}, Available: {total_available}")
        lines.append("")
        for isbn, book in self.books.items():
            lines.append(str(book))
        return "\n".join(lines)

    def generate_user_report(self) -> str:
        """
        Генерация отчёта по пользователям и их задолженностям.

        Возвращает:
            str: Отчёт по каждому пользователю с перечнем взятых книг.
        """
        lines = [f"=== User Report for {self.name} ==="]
        for user in self.users.values():
            lines.append(str(user))
            for isbn in user.borrowed_books:
                book = self.books.get(isbn)
                if book:
                    lines.append(f"\t- {book.title} (ISBN: {isbn})")
        return "\n".join(lines)

    def get_most_popular_books(self, top_n: int = 5) -> List[tuple]:
        """
        Возвращает список самых популярных книг на основе истории транзакций выдачи.

        Параметры:
            top_n (int): Количество возвращаемых позиций.

        Возвращает:
            List[tuple]: Список кортежей (Book, count), отсортированный по убыванию.
        """
        borrow_counts: Dict[str, int] = {}
        for tr in self.transactions:
            if tr.action == "borrow":
                borrow_counts[tr.isbn] = borrow_counts.get(tr.isbn, 0) + 1
        # Сортировка по количеству
        sorted_isbns = sorted(borrow_counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return [(self.books[isbn], count) for isbn, count in sorted_isbns if isbn in self.books]

    @classmethod
    def load_from_data(cls, name: str, books_data: List[Dict], users_data: List[Dict]) -> 'Library':
        """
        Альтернативный конструктор: создаёт библиотеку из готовых списков словарей.

        Параметры:
            name (str): Название библиотеки.
            books_data (List[Dict]): Список словарей с данными книг.
            users_data (List[Dict]): Список словарей с данными пользователей.

        Возвращает:
            Library: Сконструированный объект библиотеки.
        """
        lib = cls(name)
        for bd in books_data:
            lib.add_book(Book.from_dict(bd))
        for ud in users_data:
            lib.register_user(User.from_dict(ud))
        return lib


# ----------------------------------------------------------------------
# Демонстрационная функция
# ----------------------------------------------------------------------
def main():
    """
    Демонстрация работы системы управления библиотекой.
    Создаёт несколько книг и пользователей, выполняет операции выдачи/возврата,
    генерирует отчёты и выводит результаты в консоль.
    """
    # Создаём библиотеку
    lib = Library("Городская библиотека №42")

    # Добавляем книги
    books_to_add = [
        Book("Война и мир", "Лев Толстой", "978-5-389-01718-6", 1869, "Роман", 3),
        Book("Преступление и наказание", "Фёдор Достоевский", "978-5-389-01187-3", 1866, "Роман", 2),
        Book("Мастер и Маргарита", "Михаил Булгаков", "978-5-389-01653-7", 1967, "Мистика", 4),
        Book("Тихий Дон", "Михаил Шолохов", "978-5-17-024966-6", 1928, "Роман-эпопея", 2),
        Book("Евгений Онегин", "Александр Пушкин", "978-5-389-00623-2", 1833, "Поэзия", 5),
        Book("Анна Каренина", "Лев Толстой", "978-5-389-01283-7", 1877, "Роман", 3),
        Book("Отцы и дети", "Иван Тургенев", "978-5-389-01968-5", 1862, "Роман", 2),
    ]
    for b in books_to_add:
        lib.add_book(b)

    # Регистрируем пользователей
    users_to_register = [
        User("U001", "Иван Иванов", "ivanov@example.com"),
        User("U002", "Петр Петров", "petrov@example.com"),
        User("U003", "Светлана Светлова", "svetlova@example.com"),
    ]
    for u in users_to_register:
        try:
            lib.register_user(u)
        except ValueError as e:
            print(f"Ошибка регистрации: {e}")

    # Выдача книг
    try:
        lib.borrow_book("U001", "978-5-389-01718-6")  # Война и мир
        lib.borrow_book("U001", "978-5-389-01187-3")  # Преступление и наказание
        lib.borrow_book("U002", "978-5-389-01653-7")  # Мастер и Маргарита
        lib.borrow_book("U003", "978-5-389-01718-6")  # Война и мир (второй экземпляр)
        lib.borrow_book("U003", "978-5-17-024966-6")  # Тихий Дон
    except (BookNotAvailable, MaxBorrowLimitExceeded, UserNotFound) as e:
        print(f"Ошибка при выдаче: {e}")

    # Попытка повторной выдачи той же книги тому же пользователю
    try:
        lib.borrow_book("U001", "978-5-389-01718-6")
    except ValueError as e:
        print(f"Ожидаемая ошибка: {e}")

    # Возврат книги
    lib.return_book("U001", "978-5-389-01187-3")

    # Поиск книг
    print("\n--- Поиск книг по автору 'Толстой': ---")
    for book in lib.search_books("author", "Толстой"):
        print(book)

    print("\n--- Поиск книг по жанру 'Роман': ---")
    for book in lib.search_books("genre", "Роман"):
        print(book)

    # Отчёты
    print("\n" + lib.generate_inventory_report())
    print("\n" + lib.generate_user_report())

    # Самые популярные книги
    print("\n--- Самые популярные книги (топ-3): ---")
    for book, count in lib.get_most_popular_books(3):
        print(f"{book.title} — выдана {count} раз(а)")

    # Демонстрация работы с пользовательским email и его сеттером
    user1 = lib.users.get("U001")
    if user1:
        print(f"\nТекущий email {user1.name}: {user1.email}")
        user1.email = "new_ivanov@example.com"
        print(f"Обновлённый email: {user1.email}")

    # Попытка установить некорректный email
    try:
        user2 = lib.users.get("U002")
        if user2:
            user2.email = "bad-email"
    except ValueError as e:
        print(f"Ошибка валидации email: {e}")

    # Сохранение состояния в словари и создание новой библиотеки через classmethod
    books_dicts = [book.to_dict() for book in lib.books.values()]
    users_dicts = [user.to_dict() for user in lib.users.values()]
    new_lib = Library.load_from_data("Филиал №1", books_dicts, users_dicts)
    print(f"\nСоздана новая библиотека: {new_lib.name}")
    print(f"Книг: {len(new_lib.books)}, Пользователей: {len(new_lib.users)}")

    print("\n=== Демонстрация завершена ===")


if __name__ == "__main__":
    main()
