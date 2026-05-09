FROM python:3.14-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY app/ ./app/
COPY main.py .

# Создаём директории для БД и кода
RUN mkdir -p /data /code

# Переменные окружения
ENV DB_PATH=/data/code_index.db
ENV INDEX_PATH=/code
ENV REBUILD_INDEX=true
ENV PYTHONUNBUFFERED=1

# Открываем порт
EXPOSE 8000

# Запускаем приложение
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]