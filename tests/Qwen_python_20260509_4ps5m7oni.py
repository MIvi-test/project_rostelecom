"""
==============================================================================
Система Умного Дома и Энергоменеджмента (Smart Home & Energy Manager - SHEM)
==============================================================================
Описание:
    Полноценная объектно-ориентированная симуляция системы управления умным домом.
    Демонстрирует работу с иерархией устройств, правилами автоматизации,
    сбором телеметрии, учётом энергопотребления и централизованным контроллером.

Архитектура:
    - Базовые абстракции устройств и сенсоров
    - Композиция комнат и хабов
    - Движок правил автоматизации (Event-Condition-Action)
    - Аналитический модуль энергобаланса
    - Кастомные исключения, перечисления, дата-классы
    - Строгая типизация и подробная документация

Автор: Qwen3.6
Дата: 2026-05-09
Версия: 2.1.0
==============================================================================
"""

import logging
import uuid
import math
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Tuple, Union, Any
from enum import Enum, auto
from dataclasses import dataclass, field
from collections import defaultdict

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("SHEM_Core")


# ==============================================================================
# КАСТОМНЫЕ ИСКЛЮЧЕНИЯ
# ==============================================================================
class SHEMBaseError(Exception):
    """Базовое исключение для всей системы."""
    pass


class DeviceOfflineError(SHEMBaseError):
    """Вызывается при попытке управлять недоступным устройством."""
    pass


class InvalidThresholdError(SHEMBaseError):
    """Вызывается при некорректных пороговых значениях в правилах."""
    pass


class AutomationConflictError(SHEMBaseError):
    """Вызывается при конфликте одновременных правил автоматизации."""
    pass


class HubSyncError(SHEMBaseError):
    """Ошибка синхронизации состояния хаба с физическими устройствами."""
    pass


# ==============================================================================
# ПЕРЕЧИСЛЕНИЯ И КОНСТАНТЫ
# ==============================================================================
class DeviceState(Enum):
    """Состояния устройств."""
    OFFLINE = auto()
    STANDBY = auto()
    ACTIVE = auto()
    FAULT = auto()


class PowerMode(Enum):
    """Режимы энергопотребления."""
    ECO = "eco"
    NORMAL = "normal"
    BOOST = "boost"


class TriggerType(Enum):
    """Типы триггеров для автоматизации."""
    SCHEDULE = "schedule"
    SENSOR_VALUE = "sensor_value"
    STATE_CHANGE = "state_change"
    MANUAL = "manual"


MAX_DEVICES_PER_ROOM = 25
DEFAULT_TEMP_TOLERANCE = 0.5  # °C
ENERGY_PRICE_PER_KWH = 5.80  # руб.


# ==============================================================================
# БАЗОВЫЕ КЛАССЫ И ДАТА-КЛАССЫ
# ==============================================================================
@dataclass
class TelemetryRecord:
    """
    Запись телеметрии от устройства.

    Атрибуты:
        device_id: Идентификатор устройства-источника
        metric_name: Название метрики (power, temp, humidity и т.д.)
        value: Числовое значение
        timestamp: Момент фиксации
        unit: Единица измерения
    """
    device_id: str
    metric_name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    unit: str = ""

    @property
    def is_anomalous(self) -> bool:
        """Простая эвристика: значение > 100 считается аномальным."""
        return abs(self.value) > 100.0


@dataclass
class AutomationRule:
    """
    Правило автоматизации.

    Атрибуты:
        rule_id: Уникальный идентификатор правила
        name: Человекочитаемое название
        trigger_type: Тип срабатывания
        condition: Lambda/Callable, возвращающая bool
        action: Lambda/Callable, выполняющая действие
        is_active: Флаг включённости правила
        last_executed: Время последнего срабатывания
    """
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Unnamed Rule"
    trigger_type: TriggerType = TriggerType.MANUAL
    condition: Optional[Callable] = None
    action: Optional[Callable] = None
    is_active: bool = True
    last_executed: Optional[datetime] = None


class BaseEntity:
    """
    Базовый класс для всех объектов системы с автогенерацией ID и логированием.
    """
    def __init__(self, name: str) -> None:
        self.entity_id: str = str(uuid.uuid4())[:8]
        self.name: str = name
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()
        self.telemetry_log: List[TelemetryRecord] = []

    def _touch(self) -> None:
        """Обновляет метку времени последнего изменения."""
        self.updated_at = datetime.now()

    def _log_telemetry(self, metric: str, value: float, unit: str = "") -> None:
        """Добавляет запись в лог телеметрии."""
        record = TelemetryRecord(self.entity_id, metric, value, unit=unit)
        self.telemetry_log.append(record)
        if record.is_anomalous:
            logger.warning(f"[{self.entity_id}] Аномальное значение: {metric}={value}{unit}")

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} '{self.name}' | ID: {self.entity_id}>"


# ==============================================================================
# КЛАССЫ УСТРОЙСТВ (ИЕРАРХИЯ)
# ==============================================================================
class SmartDevice(BaseEntity):
    """
    Абстрактный базовый класс умного устройства.

    Определяет общий интерфейс: вкл/выкл, статус, энергопотребление, диагностика.
    """

    def __init__(self, name: str, max_power_w: float) -> None:
        super().__init__(name)
        self.max_power_w = max_power_w
        self.state: DeviceState = DeviceState.STANDBY
        self.power_mode: PowerMode = PowerMode.NORMAL
        self._current_power_w: float = 0.0

    @property
    def is_online(self) -> bool:
        """Проверяет, доступно ли устройство."""
        return self.state != DeviceState.OFFLINE

    @property
    def current_consumption_kwh(self) -> float:
        """Возвращает текущее потребление в кВт·ч (упрощённо)."""
        return self._current_power_w / 1000.0

    @staticmethod
    def validate_power(watts: float) -> bool:
        """Валидация мощности устройства."""
        return 0.0 <= watts <= 10000.0

    def turn_on(self, mode: PowerMode = PowerMode.NORMAL) -> None:
        """Включает устройство и устанавливает режим."""
        if self.state == DeviceState.OFFLINE:
            raise DeviceOfflineError(f"Устройство {self.name} оффлайн.")
        self.state = DeviceState.ACTIVE
        self.power_mode = mode
        self._current_power_w = self.max_power_w * {
            PowerMode.ECO: 0.5,
            PowerMode.NORMAL: 0.8,
            PowerMode.BOOST: 1.0
        }[mode]
        self._touch()
        self._log_telemetry("power", self._current_power_w, "W")
        logger.info(f"✅ {self.name} включён в режиме {mode.value} ({self._current_power_w:.1f}W)")

    def turn_off(self) -> None:
        """Выключает устройство."""
        self.state = DeviceState.STANDBY
        self._current_power_w = 0.0
        self._touch()
        self._log_telemetry("power", 0.0, "W")
        logger.info(f"🔌 {self.name} выключен.")

    def diagnostics(self) -> Dict[str, Any]:
        """Возвращает диагностическую информацию."""
        return {
            "id": self.entity_id,
            "name": self.name,
            "state": self.state.name,
            "power_w": self._current_power_w,
            "mode": self.power_mode.value,
            "telemetry_count": len(self.telemetry_log)
        }

    def __repr__(self) -> str:
        return f"<Device '{self.name}' | {self.state.name} | {self._current_power_w}W>"


class SmartLight(SmartDevice):
    """Умная лампа с регулировкой яркости."""
    def __init__(self, name: str, max_power_w: float = 15.0) -> None:
        super().__init__(name, max_power_w)
        self.brightness_pct: int = 100

    def set_brightness(self, pct: int) -> None:
        """Устанавливает яркость (0-100%)."""
        if not (0 <= pct <= 100):
            raise ValueError("Яркость должна быть в диапазоне 0-100%.")
        self.brightness_pct = pct
        self._current_power_w = self.max_power_w * (pct / 100.0)
        self._log_telemetry("brightness", pct, "%")
        self._touch()


class SmartThermostat(SmartDevice):
    """Умный термостат с целевой температурой."""
    def __init__(self, name: str, max_power_w: float = 2000.0) -> None:
        super().__init__(name, max_power_w)
        self.target_temp_c: float = 22.0
        self.current_temp_c: float = 20.5

    @classmethod
    def from_preset(cls, preset: str) -> "SmartThermostat":
        """Создаёт термостат из готового пресета."""
        presets = {
            "winter": ("Обогрев Зимний", 24.0),
            "summer": ("Охлаждение Летний", 21.0),
            "eco": ("Эконом", 18.0)
        }
        name, temp = presets.get(preset, ("Кастомный", 22.0))
        obj = cls(name)
        obj.target_temp_c = temp
        return obj

    def adjust_temperature(self, delta: float) -> None:
        """Изменяет целевую температуру."""
        self.target_temp_c += delta
        self._log_telemetry("target_temp", self.target_temp_c, "°C")
        self._touch()
        logger.info(f"🌡️ {self.name}: целевая температура -> {self.target_temp_c}°C")


# ==============================================================================
# КОМНАТА И АГРЕГАТОР ДАННЫХ
# ==============================================================================
class Room(BaseEntity):
    """
    Логическая группировка устройств и сенсоров в помещении.

    Поддерживает мониторинг общей нагрузки, температуры и управление сценариями.
    """
    def __init__(self, name: str, area_sqm: float) -> None:
        super().__init__(name)
        self.area_sqm = area_sqm
        self.devices: Dict[str, SmartDevice] = {}
        self.sensors: Dict[str, Dict[str, float]] = {}

    @property
    def total_active_load_w(self) -> float:
        """Суммарная активная нагрузка комнаты."""
        return sum(d.current_consumption_kwh * 1000 for d in self.devices.values() if d.state == DeviceState.ACTIVE)

    @property
    def is_overloaded(self) -> bool:
        """Проверка перегрузки (> 3.5 кВт на комнату)."""
        return self.total_active_load_w > 3500.0

    def add_device(self, device: SmartDevice) -> None:
        """Добавляет устройство в комнату."""
        if len(self.devices) >= MAX_DEVICES_PER_ROOM:
            raise HubSyncError(f"Комната '{self.name}' достигла лимита устройств.")
        self.devices[device.entity_id] = device
        logger.info(f"📦 Устройство '{device.name}' добавлено в комнату '{self.name}'")

    def update_sensor(self, sensor_type: str, value: float) -> None:
        """Обновляет показания виртуального сенсора."""
        self.sensors[sensor_type] = {"value": value, "updated_at": datetime.now()}
        self._log_telemetry(sensor_type, value)

    def get_energy_report(self) -> str:
        """Формирует краткий отчёт по комнате."""
        active = sum(1 for d in self.devices.values() if d.state == DeviceState.ACTIVE)
        load = self.total_active_load_w
        status = "⚠️ ПЕРЕГРУЗКА" if self.is_overloaded else "✅ Норма"
        return (
            f"📊 Комната: {self.name} ({self.area_sqm}м²)\n"
            f"   Активных устройств: {active}/{len(self.devices)}\n"
            f"   Суммарная нагрузка: {load:.1f}W {status}"
        )

    def __len__(self) -> int:
        return len(self.devices)


# ==============================================================================
# ДВИЖОК АВТОМАТИЗАЦИИ
# ==============================================================================
class AutomationEngine:
    """
    Движок обработки правил автоматизации.

    Хранит правила, проверяет условия и выполняет действия при срабатывании.
    """
    def __init__(self) -> None:
        self.rules: List[AutomationRule] = []
        self.execution_log: List[Dict[str, Any]] = []

    def add_rule(self, rule: AutomationRule) -> None:
        """Регистрирует новое правило."""
        if not rule.condition or not rule.action:
            raise ValueError("Правило должно содержать condition и action.")
        self.rules.append(rule)
        logger.info(f"📜 Добавлено правило: {rule.name} (ID: {rule.rule_id})")

    def evaluate_all(self, context: Dict[str, Any]) -> None:
        """
        Проверяет все активные правила в переданном контексте.

        Args:
            context: Словарь с текущими данными (температура, время, статусы и т.д.)
        """
        triggered = 0
        for rule in self.rules:
            if not rule.is_active:
                continue
            try:
                if rule.condition(context):
                    rule.action(context)
                    rule.last_executed = datetime.now()
                    self.execution_log.append({
                        "rule_id": rule.rule_id,
                        "timestamp": rule.last_executed,
                        "context_snapshot": {k: v for k, v in context.items() if isinstance(v, (int, float, str))}
                    })
                    triggered += 1
            except Exception as e:
                logger.error(f"Ошибка выполнения правила {rule.name}: {e}")
        if triggered > 0:
            logger.info(f"⚡ Сработало правил: {triggered}")

    @staticmethod
    def create_temp_rule(target: float, tolerance: float) -> AutomationRule:
        """Фабричный метод для создания правила поддержания температуры."""
        if tolerance <= 0:
            raise InvalidThresholdError("Допуск должен быть положительным.")

        def condition(ctx: Dict) -> bool:
            current = ctx.get("current_temp", 0.0)
            return abs(current - target) > tolerance

        def action(ctx: Dict) -> None:
            dev = ctx.get("thermostat")
            if dev and isinstance(dev, SmartThermostat):
                if ctx["current_temp"] < target:
                    dev.turn_on(PowerMode.BOOST)
                else:
                    dev.turn_off()

        return AutomationRule(
            name=f"Термостат: поддержание {target}°C",
            trigger_type=TriggerType.SENSOR_VALUE,
            condition=condition,
            action=action
        )


# ==============================================================================
# ЦЕНТРАЛЬНЫЙ КОНТРОЛЛЕР (ХАБ)
# ==============================================================================
class SmartHomeHub:
    """
    Главный контроллер умного дома.

    Управляет комнатами, устройствами, автоматизацией и энергобалансом.
    """
    def __init__(self, hub_name: str) -> None:
        self.hub_id: str = str(uuid.uuid4())[:6]
        self.name: str = hub_name
        self.rooms: Dict[str, Room] = {}
        self.automation: AutomationEngine = AutomationEngine()
        self.start_time: datetime = datetime.now()
        self._total_energy_consumed_kwh: float = 0.0
        self._last_update: datetime = datetime.now()

    def add_room(self, room: Room) -> None:
        """Регистрирует комнату в системе."""
        self.rooms[room.entity_id] = room
        logger.info(f"🏠 Комната '{room.name}' добавлена в хаб '{self.name}'")

    def sync_all_states(self) -> None:
        """Синхронизирует состояние всех устройств и обновляет метрики."""
        now = datetime.now()
        delta_hours = max((now - self._last_update).total_seconds() / 3600, 0.001)
        self._last_update = now

        for room in self.rooms.values():
            for device in room.devices.values():
                if device.state == DeviceState.ACTIVE:
                    self._total_energy_consumed_kwh += device.current_consumption_kwh * delta_hours
                if device.state == DeviceState.ACTIVE and device.diagnostics()["power_w"] > device.max_power_w:
                    logger.warning(f"⚠️ {device.name} превысил номинальную мощность!")

    def run_automation_cycle(self) -> None:
        """Запускает цикл проверки правил автоматизации."""
        ctx = {
            "timestamp": datetime.now(),
            "total_load_w": sum(r.total_active_load_w for r in self.rooms.values()),
            "rooms_count": len(self.rooms)
        }
        # Собираем данные сенсоров в контекст
        for room in self.rooms.values():
            for sensor_name, data in room.sensors.items():
                ctx[sensor_name] = data["value"]
                if "thermostat" in room.devices:
                    ctx["thermostat"] = next(d for d in room.devices.values() if isinstance(d, SmartThermostat))

        self.automation.evaluate_all(ctx)

    @property
    def estimated_cost_rub(self) -> float:
        """Ориентировочная стоимость потреблённой энергии."""
        return round(self._total_energy_consumed_kwh * ENERGY_PRICE_PER_KWH, 2)

    def generate_dashboard(self) -> str:
        """Формирует сводную панель управления."""
        lines = [
            f"🖥️ ДАШБОРД: {self.name}",
            f"   Запущен: {self.start_time.strftime('%Y-%m-%d %H:%M')}",
            f"   Комнат: {len(self.rooms)}",
            f"   Потреблено: {self._total_energy_consumed_kwh:.3f} кВт·ч",
            f"   Расход: {self.estimated_cost_rub} ₽",
            "   ────────────────────────"
        ]
        for room in self.rooms.values():
            lines.append(f"   {room.get_energy_report()}")
            for dev in room.devices.values():
                lines.append(f"     • {dev.name}: {dev.state.name} ({dev.current_consumption_kwh:.2f} kWh)")
        lines.append("   ════════════════════════")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<Hub '{self.name}' | Rooms: {len(self.rooms)} | Energy: {self._total_energy_consumed_kwh:.2f}kWh>"


# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ И УТИЛИТЫ
# ==============================================================================
def calculate_rolling_average(values: List[float], window: int = 5) -> float:
    """
    Вычисляет скользящее среднее для сглаживания телеметрии.

    Args:
        values: Список исторических значений
        window: Размер окна усреднения

    Returns:
        Среднее значение или 0.0
    """
    if not values:
        return 0.0
    subset = values[-window:]
    return round(sum(subset) / len(subset), 3)


def format_power_watts(watts: float) -> str:
    """Форматирует мощность в человекочитаемый вид."""
    if watts >= 1000:
        return f"{watts / 1000:.2f} kW"
    return f"{watts:.1f} W"


def export_hump_report(hub: SmartHomeHub, filename: str = "hub_report.md") -> None:
    """Экспортирует отчёт хаба в Markdown."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Отчёт: {hub.name}\n\n")
        f.write(f"**Дата генерации:** {datetime.now().isoformat()}\n\n")
        f.write("## Сводка\n")
        f.write(f"- Комнат: {len(hub.rooms)}\n")
        f.write(f"- Потребление: {hub._total_energy_consumed_kwh:.3f} кВт·ч\n")
        f.write(f"- Стоимость: {hub.estimated_cost_rub} ₽\n\n")
        f.write("## Лог автоматизации\n")
        for entry in hub.automation.execution_log[-10:]:
            f.write(f"- `{entry['rule_id']}` в {entry['timestamp'].strftime('%H:%M:%S')}\n")
    logger.info(f"📄 Отчёт сохранён в {filename}")


# ==============================================================================
# ДЕМО-СЦЕНАРИЙ
# ==============================================================================
def run_smart_home_demo() -> None:
    """Запускает демонстрацию работы всей системы умного дома."""
    print("🏠 Инициализация системы Smart Home & Energy Manager...\n")

    # 1. Создание хаба и комнат
    hub = SmartHomeHub("MainHouse_Controller")
    living_room = Room("Гостиная", 28.5)
    bedroom = Room("Спальня", 18.0)

    # 2. Наполнение устройствами
    light1 = SmartLight("Люстра Гостиная", 45.0)
    light2 = SmartLight("Ночник Спальня", 5.0)
    thermo1 = SmartThermostat("Климат Гостиная", 2200.0)
    plug1 = SmartDevice("Обогреватель", 1500.0)

    light1.set_brightness(75)
    living_room.add_device(light1)
    living_room.add_device(thermo1)
    bedroom.add_device(light2)
    bedroom.add_device(plug1)

    hub.add_room(living_room)
    hub.add_room(bedroom)

    # 3. Настройка автоматизации
    auto_rule = AutomationEngine.create_temp_rule(target=22.0, tolerance=1.0)
    hub.automation.add_rule(auto_rule)

    # 4. Симуляция работы
    print("⚡ Запуск цикла управления...\n")
    thermo1.current_temp_c = 19.5  # Холодно -> должен включиться
    living_room.update_sensor("current_temp", 19.5)
    hub.run_automation_cycle()

    print("\n📊 Промежуточный дашборд:")
    print(hub.generate_dashboard())

    # 5. Изменение состояния и пересчёт
    light1.turn_off()
    plug1.turn_on(PowerMode.BOOST)
    thermo1.current_temp_c = 23.5  # Жарко -> должен выключиться
    living_room.update_sensor("current_temp", 23.5)

    hub.sync_all_states()
    hub.run_automation_cycle()

    print("\n📈 Финальный отчёт:")
    print(hub.generate_dashboard())

    # 6. Экспорт
    export_hump_report(hub)
    print("\n✅ Демонстрация завершена.")


if __name__ == "__main__":
    """
    Точка входа. Запускает симуляцию при прямом выполнении скрипта.
    Обрабатывает прерывания и критические ошибки.
    """
    try:
        run_smart_home_demo()
    except KeyboardInterrupt:
        logger.info("🛑 Работа остановлена пользователем.")
    except (SHEMBaseError, ValueError) as e:
        logger.error(f"❌ Ошибка конфигурации: {e}")
    except Exception as e:
        logger.critical(f"💥 Необработанное исключение: {e}", exc_info=True)