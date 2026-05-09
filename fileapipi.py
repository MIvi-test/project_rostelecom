import uvicorn
from fastapi import FastAPI, Query

from parser import scan_directory

app = FastAPI(title="Code Indexer Service")

db = {}

@app.get("/api/files")
async def list_files():
    return [
        {"name": filename, "functions_count": len([i for i in items if i["type"] == "function"])}
        for filename, items in db.items()
    ]

@app.get("/api/files/{name}/structure")
async def get_structure(name: str):
    return db.get(name, [])

@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    keyword = q.lower()
    results = []
    for filename, items in db.items():
        for item in items:
            if keyword in item["name"].lower() or keyword in item["docstring"].lower():
                res = item.copy()
                res["file"] = filename
                results.append(res)
    return results

if __name__ == "__main__":
    db = scan_directory(".") 

    uvicorn.run(app, host="127.0.0.1", port=8000)
