import os
import logging
from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session

from app.db import (
    init_db,
    get_db,
    get_files_list,
    get_file_structure,
    search_elements,
    save_file_elements,
    clear_all_data,
)
from app.parser import scan_directory

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Code Archive API",
    description="API для навигации по кодовой базе",
    version="1.0.0",
)

# Переменные окружения
INDEX_PATH = os.getenv("INDEX_PATH", "/code")
REBUILD_INDEX = os.getenv("REBUILD_INDEX", "false").lower() == "true"


def rebuild_index(db: Session, path: str, force: bool = False):
    """Перестраивает индекс"""
    if force:
        logger.info("Force rebuild enabled. Clearing existing data...")
        clear_all_data(db)

    # Проверяем, нужно ли индексировать
    from app.db import File

    files_count = db.query(File).count()

    if files_count == 0 or force:
        logger.info(f"Indexing directory: {path}")
        indexed_files = scan_directory(path)

        for file_path, elements in indexed_files.items():
            if elements:
                save_file_elements(db, file_path, elements)
                logger.info(f"Indexed {file_path} ({len(elements)} elements)")

        logger.info(f"Indexing completed. Processed {len(indexed_files)} files.")
    else:
        logger.info(
            f"Database already contains {files_count} files. Using existing index."
        )
        logger.info("To force rebuild, set REBUILD_INDEX=true environment variable")


@app.on_event("startup")
def startup_event():
    """Инициализация при запуске"""
    logger.info("Starting Code Archive API")
    logger.info(f"INDEX_PATH: {INDEX_PATH}")
    logger.info(f"REBUILD_INDEX: {REBUILD_INDEX}")
    logger.info(f"DB_PATH: {os.getenv('DB_PATH', 'code_index.db')}")

    logger.info("Initializing database...")
    init_db()

    # Получаем сессию БД
    db = next(get_db())
    try:
        rebuild_index(db, INDEX_PATH, force=REBUILD_INDEX)
    finally:
        db.close()

    logger.info("Application startup complete")


# ============== ТРИ ОСНОВНЫХ ЭНДПОИНТА ==============


@app.get("/api/files")
def list_files(db: Session = Depends(get_db)):
    """
    GET /api/files
    Возвращает список всех проиндексированных файлов
    с количеством функций/классов в каждом
    """
    logger.info("Request: GET /api/files")
    result = get_files_list(db)
    logger.info(f"Response: {len(result)} files")
    return result


@app.get("/api/files/{file_path:path}/structure")
def file_structure(file_path: str, db: Session = Depends(get_db)):
    """
    GET /api/files/{file_path}/structure
    Возвращает структуру файла: все функции и классы
    с номерами строк и docstring
    """
    logger.info(f"Request: GET /api/files/{file_path}/structure")
    result = get_file_structure(db, file_path)
    logger.info(f"Response: {len(result)} elements in file")
    return result


@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1, description="Поисковый запрос"),
    type: str = Query(None, description="Фильтр по типу (function или class)"),
    db: Session = Depends(get_db),
):
    """
    GET /api/search?q={keyword}&type={type}
    Ищет функции и классы по имени или docstring (регистронезависимо)
    """
    logger.info(f"Request: GET /api/search?q={q}&type={type}")
    results = search_elements(db, q, element_type=type)
    logger.info(f"Response: {len(results)} results found")
    return results


# Дополнительный эндпоинт для переиндексации
@app.post("/api/reindex")
def reindex(db: Session = Depends(get_db)):
    """POST /api/reindex - принудительная переиндексация"""
    logger.info("Request: POST /api/reindex")
    rebuild_index(db, INDEX_PATH, force=True)
    logger.info("Reindex completed")
    return {"status": "ok", "message": "Index rebuilt successfully"}
