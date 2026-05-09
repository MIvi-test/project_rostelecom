import logging
import os
from typing import List, Dict, Any, Optional
from sqlalchemy import Column, Integer, String, Text, ForeignKey, create_engine, Index
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Настройка логгера
logger = logging.getLogger(__name__)

# Настройка БД
DB_PATH = os.getenv("DB_PATH", "code_index.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    path = Column(String, unique=True, nullable=False)

    # Отношение к элементам кода
    elements = relationship(
        "CodeElement", back_populates="file", cascade="all, delete-orphan"
    )


class CodeElement(Base):
    __tablename__ = "code_elements"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    name = Column(String, nullable=False)
    element_type = Column(String, nullable=False)  # 'function' или 'class'
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    docstring = Column(Text, default="")

    # Отношение к файлу
    file = relationship("File", back_populates="elements")

    # Индексы для оптимизации поиска
    __table_args__ = (
        Index("idx_name", "name"),
        Index("idx_element_type", "element_type"),
        Index("idx_file_id", "file_id"),
    )


def init_db():
    """Инициализация базы данных"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")


def get_db():
    """Генератор сессии БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_file_elements(db, file_path: str, elements: List[Dict[str, Any]]):
    """Сохраняет элементы файла в БД (с перезаписью)"""
    # Удаляем старые данные
    file = db.query(File).filter(File.path == file_path).first()
    if file:
        db.delete(file)
        db.flush()
        logger.debug(f"Removed old data for file: {file_path}")

    # Создаём новый файл
    file = File(path=file_path)
    db.add(file)
    db.flush()

    # Добавляем элементы
    for elem in elements:
        code_elem = CodeElement(
            file_id=file.id,
            name=elem["name"],
            element_type=elem["element_type"],
            start_line=elem["start_line"],
            end_line=elem["end_line"],
            docstring=elem.get("docstring", ""),
        )
        db.add(code_elem)

    db.commit()
    logger.info(f"Saved {len(elements)} elements from file: {file_path}")


def get_files_list(db) -> List[Dict[str, Any]]:
    """Возвращает список всех файлов с количеством элементов"""
    files = db.query(File).all()

    result = []
    for file in files:
        elements_count = (
            db.query(CodeElement).filter(CodeElement.file_id == file.id).count()
        )
        result.append({"path": file.path, "function_count": elements_count})

    logger.debug(f"Returned {len(result)} files")
    return result


def get_file_structure(db, file_path: str) -> List[Dict[str, Any]]:
    """Возвращает структуру файла"""
    file = db.query(File).filter(File.path == file_path).first()
    if not file:
        logger.debug(f"File not found: {file_path}")
        return []

    elements = (
        db.query(CodeElement)
        .filter(CodeElement.file_id == file.id)
        .order_by(CodeElement.start_line)
        .all()
    )

    logger.debug(f"Returned structure for {file_path} with {len(elements)} elements")
    return [
        {
            "name": elem.name,
            "type": elem.element_type,
            "start_line": elem.start_line,
            "end_line": elem.end_line,
            "docstring": elem.docstring,
        }
        for elem in elements
    ]


def search_elements(
    db, keyword: str, element_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Поиск элементов по ключевому слову (регистронезависимо)"""
    query = (
        db.query(CodeElement)
        .join(File)
        .filter(
            (CodeElement.name.ilike(f"%{keyword}%"))
            | (CodeElement.docstring.ilike(f"%{keyword}%"))
        )
    )

    if element_type:
        query = query.filter(CodeElement.element_type == element_type)
        logger.debug(f"Searching for '{keyword}' with type filter: {element_type}")
    else:
        logger.debug(f"Searching for '{keyword}'")

    elements = query.all()

    logger.info(f"Found {len(elements)} results for keyword '{keyword}'")
    return [
        {
            "file": elem.file.path,
            "name": elem.name,
            "type": elem.element_type,
            "start_line": elem.start_line,
            "end_line": elem.end_line,
            "docstring": elem.docstring,
        }
        for elem in elements
    ]


def clear_all_data(db):
    """Очищает все данные"""
    elements_count = db.query(CodeElement).delete()
    files_count = db.query(File).delete()
    db.commit()
    logger.info(f"Cleared all data: {elements_count} elements, {files_count} files")
