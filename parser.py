import ast

def parse_file_structure(file_path: str):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except Exception as e:
        print(f"Ошибка при чтении файла {file_path}: {e}")
        return []

    structure = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            structure.append({
                "type": "function",
                "name": node.name,
                "line": node.lineno,
                "docstring": ast.get_docstring(node) or "No docstring"
            })
        
        elif isinstance(node, ast.ClassDef):
            structure.append({
                "type": "class",
                "name": node.name,
                "line": node.lineno,
                "docstring": ast.get_docstring(node) or "No docstring"
            })
            
    return structure