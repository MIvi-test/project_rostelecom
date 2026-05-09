"""
==============================================================================
Agile Task & Sprint Manager (ATSM)
==============================================================================
Описание:
    Корпоративная система управления задачами, спринтами и командной работой.
    Демонстрирует продвинутые паттерны ООП: конечные автоматы состояний,
    композицию, фабрики, цепочки ответственности, аналитические агрегаторы
    и строгую типизацию.

Архитектура:
    - Иерархия пользователей с ролевой моделью (RBAC)
    - Система задач с валидацией переходов состояний (State Machine)
    - Спринты с тайм-боксами и метриками velocity/burndown
    - Движок уведомлений и аналитики
    - Центральный оркестратор рабочего пространства
    - Утилиты экспорта, форматирования и валидации

Автор: Qwen3.6
Дата: 2026-05-09
Версия: 3.2.0
==============================================================================
"""

import logging
import uuid
import math
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Callable, Tuple, Any
from enum import Enum, auto
from dataclasses import dataclass, field
from collections import defaultdict

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ATSM_Core")


# ==============================================================================
# КАСТОМНЫЕ ИСКЛЮЧЕНИЯ
# ==============================================================================
class ATSMBaseError(Exception):
    """Базовое исключение для всех ошибок системы."""
    pass


class InvalidStateTransitionError(ATSMBaseError):
    """Вызывается при попытке недопустимого перехода задачи."""
    pass


class SprintClosedError(ATSMBaseError):
    """Вызывается при попытке изменить задачи в закрытом спринте."""
    pass


class PermissionDeniedError(ATSMBaseError):
    """Вызывается при недостаточных правах пользователя."""
    pass


class TimeTrackingError(ATSMBaseError):
    """Вызывается при ошибках учёта рабочего времени."""
    pass


# ==============================================================================
# ПЕРЕЧИСЛЕНИЯ И КОНСТАНТЫ
# ==============================================================================
class TaskPriority(Enum):
    """Приоритеты задач."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(Enum):
    """Состояния задачи (конечный автомат)."""
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    BLOCKED = "blocked"


class UserRole(Enum):
    """Роли в команде."""
    DEVELOPER = "dev"
    QA = "qa"
    MANAGER = "mgr"
    ADMIN = "admin"


class SprintState(Enum):
    """Состояние спринта."""
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"
    ABORTED = "aborted"


MAX_SPRINT_DAYS = 28
DEFAULT_ESTIMATE_HOURS = 4.0
VELOCITY_HISTORY_WINDOW = 6


# ==============================================================================
# БАЗОВЫЕ КЛАССЫ И ДАТА-КЛАССЫ
# ==============================================================================
@dataclass
class TimeEntry:
    """
    Запись учёта рабочего времени.

    Атрибуты:
        user_id: Идентификатор сотрудника
        task_id: Идентификатор задачи
        hours_spent: Затраченные часы
        description: Краткое описание работы
        logged_at: Время фиксации
    """
    user_id: str
    task_id: str
    hours_spent: float
    description: str = ""
    logged_at: datetime = field(default_factory=datetime.now)

    @property
    def is_valid(self) -> bool:
        """Проверяет корректность записи (часы > 0 и <= 24)."""
        return 0.0 < self.hours_spent <= 24.0


@dataclass
class Comment:
    """Комментарий к задаче."""
    author_id: str
    text: str
    created_at: datetime = field(default_factory=datetime.now)
    is_edited: bool = False


class BaseEntity:
    """
    Базовый класс для всех сущностей системы.

    Обеспечивает уникальные ID, временные метки и базовое логирование.
    """
    def __init__(self, name: str) -> None:
        self.entity_id: str = str(uuid.uuid4())[:8]
        self.name: str = name
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()

    def _touch(self) -> None:
        """Обновляет метку времени последнего изменения."""
        self.updated_at = datetime.now()

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} '{self.name}' | ID: {self.entity_id}>"


# ==============================================================================
# КЛАССЫ ПОЛЬЗОВАТЕЛЕЙ (ROLES & RBAC)
# ==============================================================================
class User(BaseEntity):
    """
    Базовый класс пользователя с ролевой моделью.

    Поддерживает проверку прав, учёт нагрузки и историю действий.
    """
    def __init__(self, username: str, email: str, role: UserRole) -> None:
        super().__init__(username)
        self.email = email
        self.role = role
        self.assigned_tasks: Set[str] = set()
        self.time_log: List[TimeEntry] = []

    @classmethod
    def create_from_csv_row(cls, row: List[str]) -> "User":
        """Фабричный метод для импорта из CSV-строки."""
        username, email, role_str = row
        role_map = {v.value: v for v in UserRole}
        role = role_map.get(role_str.strip(), UserRole.DEVELOPER)
        return cls(username.strip(), email.strip(), role)

    @staticmethod
    def has_permission(role: UserRole, action: str) -> bool:
        """
        Статический метод проверки прав.

        Args:
            role: Роль пользователя
            action: Название действия ('close_sprint', 'delete_task', 'edit_task')

        Returns:
            True если действие разрешено
        """
        permissions = {
            UserRole.ADMIN: {"close_sprint", "delete_task", "edit_task", "manage_users"},
            UserRole.MANAGER: {"close_sprint", "edit_task", "assign_task"},
            UserRole.DEVELOPER: {"edit_task", "log_time"},
            UserRole.QA: {"edit_task", "log_time", "change_status"}
        }
        return action in permissions.get(role, set())

    def add_time_entry(self, task_id: str, hours: float, desc: str = "") -> TimeEntry:
        """Регистрирует затраченное время."""
        if not (0.1 <= hours <= 10.0):
            raise TimeTrackingError("Часы должны быть в диапазоне 0.1 - 10.0")
        entry = TimeEntry(self.entity_id, task_id, hours, desc)
        self.time_log.append(entry)
        self._touch()
        return entry

    def __repr__(self) -> str:
        return f"<User {self.name} ({self.role.value}) | Tasks: {len(self.assigned_tasks)}>"


# ==============================================================================
# КЛАССЫ ЗАДАЧ (STATE MACHINE)
# ==============================================================================
class Task(BaseEntity):
    """
    Базовый класс задачи с валидацией переходов состояний.

    Реализует паттерн State Machine для строгих бизнес-правил.
    """
    # Определение допустимых переходов
    VALID_TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
        TaskStatus.BACKLOG: {TaskStatus.TODO, TaskStatus.BLOCKED},
        TaskStatus.TODO: {TaskStatus.IN_PROGRESS, TaskStatus.BACKLOG, TaskStatus.BLOCKED},
        TaskStatus.IN_PROGRESS: {TaskStatus.REVIEW, TaskStatus.BLOCKED, TaskStatus.TODO},
        TaskStatus.REVIEW: {TaskStatus.DONE, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED},
        TaskStatus.DONE: {TaskStatus.IN_PROGRESS},  # Только для возврата
        TaskStatus.BLOCKED: {TaskStatus.IN_PROGRESS, TaskStatus.BACKLOG}
    }

    def __init__(self, title: str, description: str, priority: TaskPriority = TaskPriority.MEDIUM, estimate: float = DEFAULT_ESTIMATE_HOURS) -> None:
        super().__init__(title)
        self.description = description
        self.priority = priority
        self.estimate_hours = estimate
        self.status = TaskStatus.BACKLOG
        self.assignee_id: Optional[str] = None
        self.comments: List[Comment] = []
        self.tags: List[str] = []

    def change_status(self, new_status: TaskStatus) -> None:
        """
        Изменяет статус задачи с проверкой допустимости перехода.

        Raises:
            InvalidStateTransitionError: Если переход запрещён бизнес-логикой
        """
        allowed = self.VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise InvalidStateTransitionError(
                f"Переход {self.status.value} -> {new_status.value} запрещён."
            )
        self.status = new_status
        self._touch()
        logger.info(f"📌 Задача '{self.name}' перешла в {self.status.value}")

    def add_comment(self, author_id: str, text: str) -> None:
        """Добавляет комментарий к задаче."""
        self.comments.append(Comment(author_id, text))
        self._touch()

    def calculate_remaining_effort(self) -> float:
        """Оценивает оставшиеся часы (упрощённая логика)."""
        if self.status == TaskStatus.DONE:
            return 0.0
        if self.status == TaskStatus.IN_PROGRESS:
            return self.estimate_hours * 0.5
        return self.estimate_hours

    def __repr__(self) -> str:
        return f"<Task '{self.name}' | {self.status.value} | ⏱️ {self.estimate_hours}h>"


class BugTask(Task):
    """Задача-баг с полями severity и steps_to_reproduce."""
    def __init__(self, title: str, severity: str, steps: str) -> None:
        super().__init__(title, f"Severity: {severity}\nSteps: {steps}", priority=TaskPriority.HIGH)
        self.severity = severity
        self.is_regression = False


class FeatureTask(Task):
    """Задача-фича с полями story_points и acceptance_criteria."""
    def __init__(self, title: str, story_points: int, criteria: str) -> None:
        priority = TaskPriority.HIGH if story_points >= 8 else TaskPriority.MEDIUM
        super().__init__(title, f"Criteria: {criteria}", priority=priority, estimate=story_points * 1.5)
        self.story_points = story_points


# ==============================================================================
# СПРИНТ И ПРОЕКТ
# ==============================================================================
class Sprint(BaseEntity):
    """
    Итерация разработки с тайм-боксом и метриками.

    Управляет задачами спринта, статусом и генерацией отчётов.
    """
    def __init__(self, name: str, duration_days: int = 14) -> None:
        super().__init__(name)
        self.duration_days = min(duration_days, MAX_SPRINT_DAYS)
        self.state = SprintState.PLANNING
        self.tasks: Dict[str, Task] = {}
        self.start_date: Optional[datetime] = None
        self.end_date: Optional[datetime] = None
        self.velocity_points: List[int] = []

    @classmethod
    def create_from_template(cls, template_name: str) -> "Sprint":
        """Создаёт спринт из готового шаблона."""
        templates = {"standard": 14, "quick": 7, "marathon": 21}
        days = templates.get(template_name, 14)
        return cls(f"Спринт_{template_name.capitalize()}", days)

    def add_task(self, task: Task) -> None:
        """Добавляет задачу в спринт (только в режиме планирования)."""
        if self.state != SprintState.PLANNING:
            raise SprintClosedError("Нельзя добавлять задачи в активный/закрытый спринт.")
        self.tasks[task.entity_id] = task
        self._touch()

    def start(self) -> None:
        """Активирует спринт и фиксирует даты."""
        if self.state != SprintState.PLANNING:
            raise SprintClosedError("Спринт уже запущен или закрыт.")
        self.start_date = datetime.now()
        self.end_date = self.start_date + timedelta(days=self.duration_days)
        self.state = SprintState.ACTIVE
        self._touch()
        logger.info(f"🚀 Спринт '{self.name}' запущен. Финиш: {self.end_date.strftime('%Y-%m-%d')}")

    def close(self) -> Dict[str, float]:
        """Завершает спринт и возвращает метрики."""
        if self.state != SprintState.ACTIVE:
            raise SprintClosedError("Спринт не в активном состоянии.")
        self.state = SprintState.COMPLETED
        self._touch()

        done_points = sum(t.story_points for t in self.tasks.values() if isinstance(t, FeatureTask) and t.status == TaskStatus.DONE)
        self.velocity_points.append(done_points)

        total = len(self.tasks)
        done = sum(1 for t in self.tasks.values() if t.status == TaskStatus.DONE)
        logger.info(f"✅ Спринт '{self.name}' закрыт. Выполнено: {done}/{total} ({done_points} SP)")

        return {"done_tasks": done, "total_tasks": total, "velocity": done_points}

    def get_burndown_data(self) -> List[Tuple[str, float]]:
        """Формирует данные для графика сгорания задач (упрощённо)."""
        if not self.start_date or not self.end_date:
            return []
        days_passed = max((datetime.now() - self.start_date).days, 0)
        total_effort = sum(t.estimate_hours for t in self.tasks.values())
        remaining = total_effort * max(1 - (days_passed / self.duration_days), 0)
        return [("Day 0", total_effort), (f"Day {days_passed}", remaining)]


# ==============================================================================
# ДВИЖКИ: УВЕДОМЛЕНИЯ И АНАЛИТИКА
# ==============================================================================
class NotificationEngine:
    """Централизованная отправка и фильтрация уведомлений."""
    def __init__(self) -> None:
        self.queue: List[Dict[str, Any]] = []
        self.subscribers: Dict[str, List[str]] = defaultdict(list)

    def subscribe(self, user_id: str, event_type: str) -> None:
        """Подписывает пользователя на тип событий."""
        self.subscribers[event_type].append(user_id)

    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Публикует событие в очередь."""
        for user_id in self.subscribers.get(event_type, []):
            self.queue.append({"to": user_id, "type": event_type, "data": payload})
        logger.debug(f"📡 Опубликовано событие '{event_type}' для {len(self.subscribers[event_type])} получателей")

    def get_pending(self, user_id: str) -> List[Dict[str, Any]]:
        """Возвращает непрочитанные уведомления для пользователя."""
        pending = [n for n in self.queue if n["to"] == user_id]
        self.queue = [n for n in self.queue if n["to"] != user_id]
        return pending


class AnalyticsModule:
    """
    Модуль бизнес-аналитики.

    Рассчитывает velocity, загрузку команды, среднее время выполнения.
    """
    def __init__(self) -> None:
        self.historical_data: List[Dict] = []

    def calculate_average_velocity(self, sprints: List[Sprint]) -> float:
        """Средняя скорость команды за последние спринты."""
        if not sprints:
            return 0.0
        recent = sprints[-VELOCITY_HISTORY_WINDOW:]
        return sum(s.velocity_points[-1] if s.velocity_points else 0 for s in recent) / len(recent)

    def generate_team_load_report(self, users: List[User], tasks: List[Task]) -> str:
        """Формирует отчёт по загрузке участников."""
        load_map: Dict[str, float] = defaultdict(float)
        for t in tasks:
            if t.assignee_id:
                load_map[t.assignee_id] += t.calculate_remaining_effort()

        report = "👥 ЗАГРУЗКА КОМАНДЫ (часы)\n"
        for u in users:
            hours = load_map.get(u.entity_id, 0.0)
            bar = "█" * int(hours) + "░" * max(0, 20 - int(hours))
            report += f"  {u.name:<12} | [{bar:<20}] {hours:.1f}h\n"
        return report


# ==============================================================================
# ЦЕНТРАЛЬНЫЙ ОРКЕСТРАТОР
# ==============================================================================
class AgileWorkspace:
    """
    Главный контроллер рабочего пространства.

    Координирует пользователей, спринты, задачи, аналитику и уведомления.
    """
    def __init__(self, workspace_name: str) -> None:
        self.name = workspace_name
        self.users: Dict[str, User] = {}
        self.backlog: Dict[str, Task] = {}
        self.active_sprints: List[Sprint] = []
        self.notifications = NotificationEngine()
        self.analytics = AnalyticsModule()
        self._setup_default_subs()

    def _setup_default_subs(self) -> None:
        """Настраивает подписки на события по умолчанию."""
        self.notifications.subscribe("ALL", "status_change")
        self.notifications.subscribe("ALL", "sprint_start")

    def add_user(self, user: User) -> None:
        """Регистрирует пользователя в пространстве."""
        self.users[user.entity_id] = user
        logger.info(f"👤 Пользователь '{user.name}' добавлен в {self.name}")

    def create_sprint(self, name: str, days: int = 14) -> Sprint:
        """Создаёт и регистрирует новый спринт."""
        sprint = Sprint(name, days)
        self.active_sprints.append(sprint)
        return sprint

    def assign_task(self, task_id: str, user_id: str) -> None:
        """Назначает задачу пользователю с проверкой прав."""
        if user_id not in self.users:
            raise PermissionDeniedError("Пользователь не найден в пространстве.")
        task = self.backlog.get(task_id)
        if not task:
            for s in self.active_sprints:
                if task_id in s.tasks:
                    task = s.tasks[task_id]
                    break
        if not task:
            raise PermissionDeniedError("Задача не найдена.")

        user = self.users[user_id]
        if task.assignee_id:
            logger.info(f"🔄 Задача переназначена с {task.assignee_id} на {user_id}")
        task.assignee_id = user_id
        user.assigned_tasks.add(task_id)
        self.notifications.publish("status_change", {"task": task.name, "assignee": user.name})
        logger.info(f"🎯 Задача '{task.name}' назначена на {user.name}")

    def get_dashboard(self) -> str:
        """Формирует сводную панель управления."""
        lines = [
            f"🖥️ WORKSPACE: {self.name}",
            f"   Участников: {len(self.users)}",
            f"   Бэклог: {len(self.backlog)} задач",
            f"   Активных спринтов: {len(self.active_sprints)}",
            f"   ────────────────────────"
        ]
        for s in self.active_sprints:
            lines.append(f"   📅 {s.name} [{s.state.value}] ({s.start_date.strftime('%d.%m') if s.start_date else 'не запущен'})")
        return "\n".join(lines)


# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================
def format_duration(hours: float) -> str:
    """Форматирует часы в человекочитаемый вид."""
    if hours >= 1.0:
        return f"{hours:.1f}ч"
    return f"{int(hours * 60)}м"


def validate_task_title(title: str) -> bool:
    """Проверяет корректность названия задачи."""
    if not title or len(title) < 3:
        logger.warning("Название задачи слишком короткое.")
        return False
    if any(c in title for c in ["<", ">", "&", '"']):
        logger.warning("Название содержит запрещённые символы.")
        return False
    return True


def export_sprint_summary(sprint: Sprint, filename: str = "sprint_report.txt") -> None:
    """Экспортирует итоговый отчёт спринта в файл."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Отчёт спринта: {sprint.name}\n")
        f.write(f"Статус: {sprint.state.value}\n")
        f.write(f"Период: {sprint.start_date} -> {sprint.end_date}\n\n")
        f.write("ЗАДАЧИ:\n")
        for t in sprint.tasks.values():
            f.write(f"  [ {t.status.value.upper():10} ] {t.name} ({t.estimate_hours}h)\n")
    logger.info(f"📄 Отчёт сохранён в {filename}")


# ==============================================================================
# ДЕМО-СЦЕНАРИЙ
# ==============================================================================
def run_demo() -> None:
    """Запускает демонстрацию полного цикла работы Agile-системы."""
    print("🚀 Инициализация Agile Task & Sprint Manager...\n")

    # 1. Создание рабочего пространства и команды
    ws = AgileWorkspace("AlphaTeam_ProjectX")
    dev1 = User("alex_dev", "alex@dev.co", UserRole.DEVELOPER)
    dev2 = User("maria_qa", "maria@dev.co", UserRole.QA)
    mgr = User("ivan_mgr", "ivan@dev.co", UserRole.MANAGER)
    for u in [dev1, dev2, mgr]:
        ws.add_user(u)

    # 2. Наполнение бэклога
    t1 = FeatureTask("Реализовать авторизацию JWT", 5, "Токен валидируется middleware")
    t2 = BugTask("Кривой рендер на iOS 15", "High", "Открыть Safari -> нажать профиль")
    t3 = FeatureTask("Добавить кэширование Redis", 8, "TTL 300s, invalidation по ключу")
    for t in [t1, t2, t3]:
        if validate_task_title(t.name):
            ws.backlog[t.entity_id] = t

    # 3. Создание и запуск спринта
    sprint = ws.create_sprint("Sprint_14_May", 14)
    sprint.add_task(t1)
    sprint.add_task(t2)
    sprint.assign_task(t1.entity_id, dev1.entity_id)
    sprint.start()

    # 4. Симуляция работы
    print("⚡ Выполнение задач...\n")
    t1.change_status(TaskStatus.IN_PROGRESS)
    dev1.add_time_entry(t1.entity_id, 3.5, "Написал middleware")
    t1.change_status(TaskStatus.REVIEW)
    t2.change_status(TaskStatus.TODO)
    t2.change_status(TaskStatus.IN_PROGRESS)

    # 5. Панель и аналитика
    print("📊 Текущее состояние:")
    print(ws.get_dashboard())
    print("\n📈 Загрузка команды:")
    print(ws.analytics.generate_team_load_report([dev1, dev2], list(ws.backlog.values())))

    # 6. Закрытие спринта
    t1.change_status(TaskStatus.DONE)
    sprint.close()
    export_sprint_summary(sprint)

    print("\n✅ Демонстрация завершена успешно.")


if __name__ == "__main__":
    """
    Точка входа. Запускает симуляцию при прямом выполнении.
    Обрабатывает пользовательские и системные исключения.
    """
    try:
        run_demo()
    except KeyboardInterrupt:
        logger.info("🛑 Выполнение прервано.")
    except (ATSMBaseError, ValueError) as e:
        logger.error(f"❌ Бизнес-ошибка: {e}")
    except Exception as e:
        logger.critical(f"💥 Критическая ошибка: {e}", exc_info=True)