from datetime import datetime
from typing import List, Dict, Any, Optional
import re

from sqlalchemy import (
    Column,
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
    Table,
    MetaData,
    event,
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

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
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
        Index("idx_ce_name_lower", func.lower(name)),
    )


_fts_metadata = MetaData()
code_elements_fts = Table(
    "code_elements_fts",
    _fts_metadata,
    Column("rowid", Integer, primary_key=True),
    Column("name", String),
    Column("docstring", Text),
)

MAX_LIST_LIMIT = 1000
MAX_SEARCH_LIMIT = 1000


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    setup_fts()


def setup_fts() -> None:
    with engine.connect() as conn:
        conn.exec_driver_sql(
            "CREATE VIRTUAL TABLE IF NOT EXISTS code_elements_fts USING fts5("
            "    name, docstring, content='code_elements', content_rowid='id'"
            ")"
        )
        conn.exec_driver_sql(
            "CREATE TRIGGER IF NOT EXISTS ce_ai AFTER INSERT ON code_elements BEGIN "
            "INSERT INTO code_elements_fts(rowid, name, docstring) "
            "VALUES (new.id, new.name, new.docstring); END;"
        )
        conn.exec_driver_sql(
            "CREATE TRIGGER IF NOT EXISTS ce_ad AFTER DELETE ON code_elements BEGIN "
            "INSERT INTO code_elements_fts(code_elements_fts, rowid, name, docstring) "
            "VALUES ('delete', old.id, old.name, old.docstring); END;"
        )
        conn.exec_driver_sql(
            "CREATE TRIGGER IF NOT EXISTS ce_au AFTER UPDATE ON code_elements BEGIN "
            "INSERT INTO code_elements_fts(code_elements_fts, rowid, name, docstring) "
            "VALUES ('delete', old.id, old.name, old.docstring); "
            "INSERT INTO code_elements_fts(rowid, name, docstring) "
            "VALUES (new.id, new.name, new.docstring); END;"
        )
        conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def sanitize_fts_query(keyword: str) -> str:
    clean = re.sub(r"[^\w\s]", "", keyword)
    clean = " ".join(clean.split())
    if not clean:
        return ""
    escaped = clean.replace('"', '""')
    return f'"{escaped}"*'


def clear_all_data(db: Session) -> None:
    db.query(CodeElement).delete()
    db.query(File).delete()
    db.commit()


def save_file_elements(
    db: Session, file_path: str, elements: List[Dict[str, Any]]
) -> None:
    try:
        with db.begin_nested():
            db.query(File).filter(File.path == file_path).delete()
            file = File(path=file_path)
            db.add(file)
            db.flush()

            if elements:
                mappings = [
                    {
                        "file_id": file.id,
                        "name": e["name"],
                        "element_type": e["element_type"],
                        "start_line": e["start_line"],
                        "end_line": e["end_line"],
                        "docstring": e.get("docstring"),
                    }
                    for e in elements
                ]
                db.bulk_insert_mappings(CodeElement.__mapper__, mappings)
        db.commit()
    except Exception:
        db.rollback()
        raise


def get_files_list(
    db: Session, limit: int = 100, offset: int = 0
) -> List[Dict[str, Any]]:
    if limit < 1 or limit > MAX_LIST_LIMIT:
        limit = min(max(limit, 1), MAX_LIST_LIMIT)

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
        .limit(limit)
        .offset(offset)
    )

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
    fts_phrase = sanitize_fts_query(keyword)
    if not fts_phrase:
        return []

    safe_limit = limit if limit is not None else 100
    safe_offset = offset if offset is not None else 0
    safe_limit = min(max(safe_limit, 1), MAX_SEARCH_LIMIT)

    stmt = (
        select(CodeElement, File.path)
        .join(File, CodeElement.file_id == File.id)
        .join(code_elements_fts, CodeElement.id == code_elements_fts.c.rowid)
        .where(code_elements_fts.c.code_elements_fts.match(fts_phrase))
    )

    if element_type in ("function", "class"):
        stmt = stmt.where(CodeElement.element_type == element_type)

    stmt = stmt.order_by(CodeElement.name).limit(safe_limit).offset(safe_offset)

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
