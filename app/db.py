from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    relationship,
    sessionmaker,
)

DB_PATH = "code_index.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    path = Column(String, nullable=False, unique=True)

    elements = relationship("CodeElement", back_populates="file")


class CodeElement(Base):
    __tablename__ = "code_elements"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    name = Column(String, nullable=False)
    element_type = Column(String, nullable=False)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    docstring = Column(Text, nullable=True)

    file = relationship("File", back_populates="elements")

    __table_args__ = (
        Index("idx_file_id", "file_id"),
        Index("idx_name", "name"),
        Index("idx_type", "element_type"),
    )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_file_elements(
    db: Session, file_path: str, elements: List[Dict[str, Any]]
) -> None:
    db.query(File).filter(File.path == file_path).delete()

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


def get_files_list(db: Session) -> List[Dict[str, Any]]:
    files = db.query(File).all()
    result = []
    for file in files:
        func_count = (
            db.query(CodeElement)
            .filter(
                CodeElement.file_id == file.id, CodeElement.element_type == "function"
            )
            .count()
        )
        result.append({"path": file.path, "function_count": func_count})
    return result


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
) -> List[Dict[str, Any]]:
    query = db.query(CodeElement).filter(
        (CodeElement.name.like(f"%{keyword}%"))
        | (CodeElement.docstring.like(f"%{keyword}%"))
    )

    if element_type:
        query = query.filter(CodeElement.element_type == element_type)

    elements = query.all()

    return [
        {
            "file": e.file.path,
            "name": e.name,
            "type": e.element_type,
            "start_line": e.start_line,
            "end_line": e.end_line,
            "docstring": e.docstring,
        }
        for e in elements
    ]


def clear_all_data(db: Session) -> None:
    db.query(CodeElement).delete()
    db.query(File).delete()
    db.commit()
