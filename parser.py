import ast
import os
from typing import List, Dict

def parse_file(file_path: str) -> List[Dict]:
    if not os.path.exists(file_path):
        return []
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        
        file_structure = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                file_structure.append({
                    "type": "function" if isinstance(node, ast.FunctionDef) else "class",
                    "name": node.name,
                    "line": node.lineno,
                    "docstring": ast.get_docstring(node) or "No docstring"
                })
        return file_structure
    except Exception as e:
        return []

def scan_directory(path: str = ".") -> Dict[str, List[Dict]]:

    indexed_data = {}
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                indexed_data[file] = parse_file(full_path)
    return indexed_data