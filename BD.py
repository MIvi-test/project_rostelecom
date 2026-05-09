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

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
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
        Index("idx_ce_name_lower", func.lower("name")),
    )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def clear_all_data(db: Session) -> None:
    db.query(CodeElement).delete()
    db.query(File).delete()
    db.commit()


def save_file_elements(
    db: Session, file_path: str, elements: List[Dict[str, Any]]
) -> None:
    existing = db.query(File).filter(File.path == file_path).first()
    if existing:
        db.delete(existing)
        db.flush()

    file = File(path=file_path)
    db.add(file)
    db.flush()

    for elem in elements:
        code_elem = CodeElement(
            file_id=file.id,
            name=elem["name"],
            element_type=elem["element_type"],
            start_line=elem["start_line"],
            end_line=elem["end_line"],
            docstring=elem.get("docstring"),
        )
        db.add(code_elem)

    db.commit()


def get_files_list(
    db: Session, limit: Optional[int] = None, offset: Optional[int] = None
) -> List[Dict[str, Any]]:

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
    if not keyword:
        return []

    keyword_lower = f"%{keyword.lower()}%"
    name_condition = func.lower(CodeElement.name).like(keyword_lower)
    docstring_condition = CodeElement.docstring.isnot(None) & func.lower(
        CodeElement.docstring
    ).like(keyword_lower)
    condition = name_condition | docstring_condition

    stmt = (
        select(CodeElement, File.path)
        .join(File, CodeElement.file_id == File.id)
        .where(condition)
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
    total_files = db.query(File).count()
    total_functions = (
        db.query(CodeElement).filter(CodeElement.element_type == "function").count()
    )
    total_classes = (
        db.query(CodeElement).filter(CodeElement.element_type == "class").count()
    )
    return {
        "total_files": total_files,
        "total_functions": total_functions,
        "total_classes": total_classes,
    }
