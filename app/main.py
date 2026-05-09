import os
from typing import Dict, List

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import (
    clear_all_data,
    get_db,
    get_file_structure,
    get_files_list,
    init_db,
    save_file_elements,
    search_elements,
    SessionLocal,
)
from app.parser import scan_directory

app = FastAPI(title="Code Indexer Service")
INDEX_ROOT = os.getenv("INDEX_PATH", ".")


def rebuild_index(path: str = INDEX_ROOT) -> None:
    init_db()
    indexed_files = scan_directory(path)

    db = SessionLocal()
    try:
        clear_all_data(db)
        for file_path, items in indexed_files.items():
            if items:
                save_file_elements(db, file_path, items)
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    rebuild_index(INDEX_ROOT)


@app.get("/api/files")
def list_files(db: Session = Depends(get_db)):
    return get_files_list(db)


@app.get("/api/files/{file_path:path}/structure")
def read_file_structure(file_path: str, db: Session = Depends(get_db)):
    structure = get_file_structure(db, file_path)
    if not structure:
        raise HTTPException(status_code=404, detail="File not found")
    return structure


@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1),
    type: str | None = None,
    db: Session = Depends(get_db),
):
    return search_elements(db, q, element_type=type)


@app.post("/api/reindex")
def reindex(path: str = Query(INDEX_ROOT, description="Directory to scan")):
    rebuild_index(path)
    return {"status": "ok", "indexed_path": path}


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    rebuild_index(INDEX_ROOT)
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
