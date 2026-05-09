from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import (
    create_engine,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
    func,
    select,
    case,
    event,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    Session,
    sessionmaker,
)

DB_PATH = "code_index.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Включаем WAL-режим для параллельной работы (чтение во время записи)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class File(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    code_elements: Mapped[List["CodeElement"]] = relationship(
        "CodeElement", back_populates="file", cascade="all, delete-orphan"
    )


class CodeElement(Base):
    __tablename__ = "code_elements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    element_type: Mapped[str] = mapped_column(String, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    docstring: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    file: Mapped[File] = relationship("File", back_populates="code_elements")

    __table_args__ = (
        Index("idx_ce_file_id", "file_id"),
        Index("idx_ce_name", "name"),
        Index("idx_ce_type", "element_type"),
        Index(
            "idx_ce_name_lower", func.lower("name")
        ),  # запасной, если FTS не используется
    )


def init_db() -> None:
    """Создаёт все таблицы, включая виртуальную FTS5."""
    Base.metadata.create_all(bind=engine)
    # Создаём FTS5 таблицу, если её нет (выполняем сырой SQL)
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS code_elements_fts USING fts5(
                name,
                docstring,
                content='code_elements',
                content_rowid='id'
            );
        """))
        # Триггеры для автоматической синхронизации FTS с основной таблицей
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS ce_ai AFTER INSERT ON code_elements BEGIN
                INSERT INTO code_elements_fts(rowid, name, docstring)
                VALUES (new.id, new.name, new.docstring);
            END;
        """))
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS ce_ad AFTER DELETE ON code_elements BEGIN
                INSERT INTO code_elements_fts(code_elements_fts, rowid, name, docstring)
                VALUES ('delete', old.id, old.name, old.docstring);
            END;
        """))
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS ce_au AFTER UPDATE ON code_elements BEGIN
                INSERT INTO code_elements_fts(code_elements_fts, rowid, name, docstring)
                VALUES ('delete', old.id, old.name, old.docstring);
                INSERT INTO code_elements_fts(rowid, name, docstring)
                VALUES (new.id, new.name, new.docstring);
            END;
        """))
        conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def clear_all_data(db: Session) -> None:
    """Полная очистка данных (включая FTS)."""
    # Сначала чистим основную таблицу, триггеры обновят FTS
    db.query(CodeElement).delete()
    db.query(File).delete()
    db.commit()
    # Полная перестройка FTS-индекса для чистоты
    db.execute(
        text("INSERT INTO code_elements_fts(code_elements_fts) VALUES('rebuild')")
    )
    db.commit()


def save_file_elements(
    db: Session, file_path: str, elements: List[Dict[str, Any]]
) -> None:
    """
    Сохраняет структуру файла. При повторной индексации старые данные заменяются.
    Используется пакетная вставка для производительности.
    """
    existing = db.query(File).filter(File.path == file_path).first()
    if existing:
        db.delete(existing)  # каскад удалит элементы, триггеры FTS очистят
        db.flush()

    file = File(path=file_path)
    db.add(file)
    db.flush()  # получаем file.id

    if elements:
        # Подготавливаем записи для пакетной вставки
        mappings = [
            {
                "file_id": file.id,
                "name": elem["name"],
                "element_type": elem["element_type"],
                "start_line": elem["start_line"],
                "end_line": elem["end_line"],
                "docstring": elem.get("docstring"),
            }
            for elem in elements
        ]
        # bulk_insert_mappings не поддерживает relationship, но у нас внешний ключ задан явно
        db.execute(CodeElement.__table__.insert(), mappings)
        # Триггеры AFTER INSERT заполнят FTS

    db.commit()


def get_files_list(
    db: Session, limit: Optional[int] = None, offset: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Возвращает список файлов с количеством функций."""
    subq = (
        select(CodeElement.file_id, func.count(CodeElement.id).label("func_count"))
        .where(CodeElement.element_type == "function")
        .group_by(CodeElement.file_id)
        .subquery()
    )

    stmt = (
        select(File.path, func.coalesce(subq.c.func_count, 0).label("function_count"))
        .outerjoin(subq, File.id == subq.c.file_id)
        .order_by(File.path)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    if offset is not None:
        stmt = stmt.offset(offset)

    result = db.execute(stmt).all()
    return [{"path": row.path, "function_count": row.function_count} for row in result]


def get_file_structure(db: Session, file_path: str) -> List[Dict[str, Any]]:
    """Структура конкретного файла — элементы, отсортированные по строкам."""
    file = db.query(File).filter(File.path == file_path).first()
    if not file:
        return []

    elements = (
        db.query(CodeElement)
        .filter(CodeElement.file_id == file.id)
        .order_by(CodeElement.start_line)
        .all()
    )
    return [
        {
            "name": e.name,
            "type": e.element_type,
            "start_line": e.start_line,
            "end_line": e.end_line,
            "docstring": e.docstring,
        }
        for e in elements
    ]


def search_elements(
    db: Session,
    keyword: str,
    element_type: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Полнотекстовый поиск по имени и docstring.
    Используется FTS5, что даёт мгновенный поиск даже на 100k+ записях.
    """
    if not keyword:
        return []

    # FTS5 ищет по словам; для подстроки "keyword*" используем префиксный поиск,
    # но для имитации LIKE '%keyword%' обернём запрос в простой MATCH с двойными кавычками,
    # что даёт точное совпадение фразы. Для приближения к старому поведению ищем слово,
    # содержащее keyword: добавляем '*' в конце.
    # Пример: keyword = "cache" -> "cache*"
    fts_query = f'"{keyword}"*'  # фраза с префиксным завершением

    # Основной запрос: соединяем FTS с code_elements и files
    stmt = (
        select(CodeElement, File.path)
        .join(File, CodeElement.file_id == File.id)
        .join(
            text("code_elements_fts ON code_elements.id = code_elements_fts.rowid"),
        )
        .where(func.code_elements_fts.code_elements_fts.match(fts_query))
    )

    if element_type in ("function", "class"):
        stmt = stmt.where(CodeElement.element_type == element_type)

    stmt = stmt.order_by(CodeElement.name)
    if limit is not None:
        stmt = stmt.limit(limit)
    if offset is not None:
        stmt = stmt.offset(offset)

    result = db.execute(stmt).all()

    return [
        {
            "file": row.path,
            "name": row.CodeElement.name,
            "type": row.CodeElement.element_type,
            "start_line": row.CodeElement.start_line,
            "end_line": row.CodeElement.end_line,
            "docstring": row.CodeElement.docstring,
        }
        for row in result
    ]


def get_stats(db: Session) -> Dict[str, int]:
    """
    Один запрос на получение всей статистики вместо трёх.
    """
    stmt = (
        select(
            func.count(File.id.distinct()).label("total_files"),
            func.sum(case((CodeElement.element_type == "function", 1), else_=0)).label(
                "total_functions"
            ),
            func.sum(case((CodeElement.element_type == "class", 1), else_=0)).label(
                "total_classes"
            ),
        )
        .select_from(File)
        .outerjoin(CodeElement, File.id == CodeElement.file_id)
    )

    row = db.execute(stmt).one()
    return {
        "total_files": row.total_files,
        "total_functions": row.total_functions or 0,
        "total_classes": row.total_classes or 0,
    }
