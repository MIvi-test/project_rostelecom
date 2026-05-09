import ast
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def parse_file(file_path: str) -> List[Dict[str, Any]]:
    """Парсит Python файл и извлекает функции и классы"""
    if not os.path.exists(file_path):
        logger.warning(f"File does not exist: {file_path}")
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content)

        elements = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                elements.append(
                    {
                        "element_type": "function",
                        "name": node.name,
                        "start_line": node.lineno,
                        "end_line": getattr(node, "end_lineno", node.lineno),
                        "docstring": ast.get_docstring(node) or "",
                    }
                )
            elif isinstance(node, ast.ClassDef):
                elements.append(
                    {
                        "element_type": "class",
                        "name": node.name,
                        "start_line": node.lineno,
                        "end_line": getattr(node, "end_lineno", node.lineno),
                        "docstring": ast.get_docstring(node) or "",
                    }
                )

        logger.debug(f"Parsed {len(elements)} elements from {file_path}")
        return elements
    except Exception as e:
        logger.error(f"Error parsing {file_path}: {e}")
        return []


def scan_directory(directory_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """Сканирует директорию и парсит все Python файлы"""
    if not os.path.exists(directory_path):
        logger.error(f"Directory does not exist: {directory_path}")
        return {}

    indexed_data = {}
    files_processed = 0

    for root, dirs, files in os.walk(directory_path):
        # Игнорируем служебные директории
        dirs[:] = [
            d
            for d in dirs
            if d not in {".git", "__pycache__", ".venv", "venv", "env", "myenv"}
        ]

        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, directory_path)
                elements = parse_file(full_path)
                if elements:
                    indexed_data[rel_path] = elements
                    files_processed += 1

    logger.info(
        f"Scanned directory {directory_path}: found {files_processed} Python files"
    )
    return indexed_data
