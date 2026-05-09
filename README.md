# Code Archive API

REST-сервис для навигации по кодовой базе Python.

## API Endpoints

### GET /api/files
Список всех файлов с количеством функций/классов

### GET /api/files/{file_path}/structure
Структура конкретного файла

### GET /api/search?q={keyword}&type={type}
Поиск по имени или docstring (регистронезависимо)

## Запуск с Docker Compose

```bash
# Обычный запуск (использует существующую БД)
docker-compose up -d

# Запуск с переиндексацией
REBUILD_INDEX=true docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Переиндексация работающего сервиса
curl -X POST http://localhost:8000/api/reindex

# Остановка
docker-compose down

# Полная очистка (удаление БД)
docker-compose down -v