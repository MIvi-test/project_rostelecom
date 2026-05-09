import ast
import os
from typing import Any, Dict, List


def parse_file(file_path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        file_structure: List[Dict[str, Any]] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                file_structure.append(
                    {
                        "element_type": (
                            "function"
                            if not isinstance(node, ast.ClassDef)
                            else "class"
                        ),
                        "name": node.name,
                        "start_line": node.lineno,
                        "end_line": getattr(node, "end_lineno", node.lineno),
                        "docstring": ast.get_docstring(node) or "",
                    }
                )
        return file_structure
    except Exception as e:
        print(f"Ошибка при парсинге {file_path}: {e}")
        return []


def scan_directory(path: str = ".") -> Dict[str, List[Dict[str, Any]]]:
    indexed_data: Dict[str, List[Dict[str, Any]]] = {}

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in {".git", ".venv", "__pycache__"}]

        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, path)
                indexed_data[rel_path] = parse_file(full_path)

    return indexed_data
