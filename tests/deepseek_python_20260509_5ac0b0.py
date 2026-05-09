"""
Система управления интернет-магазином

Данный модуль реализует модель электронной коммерции с поддержкой каталога товаров,
корзины покупателя, оформления заказов, системы скидок и управления складом.
Включает классы Product, User, Cart, Order, Discount (и его подклассы),
а также кастомные исключения для обработки ошибок бизнес-логики.

Версия: 1.0
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional, Any
import uuid


# Пользовательские исключения
class OutOfStockError(Exception):
    """Исключение при попытке добавить в корзину отсутствующий на складе товар."""

    def __init__(self, product_id: str, requested: int, available: int):
        self.product_id = product_id
        self.requested = requested
        self.available = available
        super().__init__(f"Недостаточно товара {product_id}. Запрошено: {requested}, в наличии: {available}")

    def __str__(self):
        return f"OutOfStockError(товар {self.product_id}, запрошено {self.requested}, доступно {self.available})"


class EmptyCartError(Exception):
    """Исключение при попытке оформить заказ с пустой корзиной."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"Корзина пользователя {user_id} пуста")

    def __str__(self):
        return f"EmptyCartError(пользователь {self.user_id})"


class InvalidDiscountError(Exception):
    """Исключение при применении недействительной скидки."""

    def __init__(self, code: str, reason: str = "Неизвестная причина"):
        self.code = code
        self.reason = reason
        super().__init__(f"Скидка {code} недействительна: {reason}")

    def __str__(self):
        return f"InvalidDiscountError(код {self.code}, причина: {self.reason})"


class Product:
    """
    Класс, описывающий товар в каталоге интернет-магазина.

    Атрибуты:
        product_id (str): Уникальный идентификатор товара.
        name (str): Наименование.
        category (str): Категория товара.
        price (float): Цена за единицу.
        stock (int): Остаток на складе.
        description (str): Описание.
    """

    def __init__(self, product_id: str, name: str, category: str, price: float, stock: int, description: str = ""):
        """
        Инициализация товара.

        Параметры:
            product_id (str): Уникальный код товара.
            name (str): Название.
            category (str): Категория (например, 'электроника', 'книги').
            price (float): Цена (должна быть >= 0).
            stock (int): Количество на складе (>= 0).
            description (str): Текстовое описание.

        Исключения:
            ValueError: При отрицательных цене или остатке.
        """
        if price < 0:
            raise ValueError("Цена не может быть отрицательной")
        if stock < 0:
            raise ValueError("Остаток не может быть отрицательным")
        self.product_id = product_id
        self.name = name
        self.category = category
        self.price = price
        self.stock = stock
        self.description = description

    def reduce_stock(self, quantity: int) -> bool:
        """
        Уменьшает складской остаток на указанное количество.

        Параметры:
            quantity (int): Сколько единиц списать.

        Возвращает:
            bool: True, если списание успешно.

        Исключения:
            OutOfStockError: Если запрашивается больше, чем есть на складе.
        """
        if quantity > self.stock:
            raise OutOfStockError(self.product_id, quantity, self.stock)
        self.stock -= quantity
        return True

    def increase_stock(self, quantity: int) -> None:
        """
        Увеличивает остаток (например, при возврате товара).

        Параметры:
            quantity (int): Количество для добавления.
        """
        if quantity <= 0:
            raise ValueError("Количество должно быть положительным")
        self.stock += quantity

    def __str__(self) -> str:
        """
        Удобочитаемое строковое представление.

        Возвращает:
            str: 'название (категория) — цена руб. [остаток]'
        """
        return f"{self.name} ({self.category}) — {self.price:.2f} руб. [остаток: {self.stock}]"

    def __repr__(self) -> str:
        """
        Официальное строковое представление для отладки.

        Возвращает:
            str: Представление, пригодное для воссоздания объекта.
        """
        return (f"Product(product_id={self.product_id!r}, name={self.name!r}, "
                f"category={self.category!r}, price={self.price!r}, stock={self.stock!r}, "
                f"description={self.description!r})")

    def to_dict(self) -> Dict[str, Any]:
        """
        Сериализация товара в словарь.

        Возвращает:
            dict: Данные товара.
        """
        return {
            "product_id": self.product_id,
            "name": self.name,
            "category": self.category,
            "price": self.price,
            "stock": self.stock,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Product":
        """
        Десериализация товара из словаря.

        Параметры:
            data (dict): Словарь с полями товара.

        Возвращает:
            Product: Восстановленный объект.
        """
        return cls(
            product_id=data["product_id"],
            name=data["name"],
            category=data["category"],
            price=data["price"],
            stock=data.get("stock", 0),
            description=data.get("description", "")
        )


class CartItem:
    """
    Элемент корзины: связывает товар и запрошенное количество.

    Атрибуты:
        product (Product): Товар.
        quantity (int): Количество.
    """

    def __init__(self, product: Product, quantity: int):
        """
        Инициализация элемента корзины.

        Параметры:
            product (Product): Ссылка на товар.
            quantity (int): Количество (должно быть > 0).

        Исключения:
            ValueError: При количестве <= 0.
        """
        if quantity <= 0:
            raise ValueError("Количество должно быть положительным")
        self.product = product
        self.quantity = quantity

    @property
    def total_price(self) -> float:
        """Общая стоимость позиции без учёта скидок."""
        return self.product.price * self.quantity

    def __str__(self) -> str:
        return f"{self.product.name} x{self.quantity} = {self.total_price:.2f} руб."


class User:
    """
    Пользователь интернет-магазина.

    Атрибуты:
        user_id (str): Уникальный идентификатор.
        name (str): Имя.
        email (str): Адрес электронной почты.
        address (str): Адрес доставки.
        cart (Cart): Корзина пользователя.
    """

    def __init__(self, user_id: str, name: str, email: str, address: str = ""):
        """
        Инициализация пользователя.

        Параметры:
            user_id (str): Логин или ID.
            name (str): Полное имя.
            email (str): Email.
            address (str): Адрес доставки (по умолчанию пустая строка).
        """
        self.user_id = user_id
        self.name = name
        self.email = email
        self.address = address
        self.cart = Cart(self)

    def __str__(self) -> str:
        return f"Пользователь {self.name} (ID: {self.user_id})"


class Cart:
    """
    Корзина покупок, привязанная к пользователю.

    Хранит список CartItem и предоставляет методы для добавления, удаления,
    изменения количества и расчёта общей стоимости.
    """

    def __init__(self, owner: User):
        """
        Инициализация корзины.

        Параметры:
            owner (User): Владелец корзины.
        """
        self.owner = owner
        self.items: List[CartItem] = []

    def add_item(self, product: Product, quantity: int = 1) -> None:
        """
        Добавляет товар в корзину. Если товар уже есть, увеличивает количество.

        Параметры:
            product (Product): Товар для добавления.
            quantity (int): Количество.

        Исключения:
            OutOfStockError: Если запрашиваемое количество превышает склад.
        """
        if quantity > product.stock:
            raise OutOfStockError(product.product_id, quantity, product.stock)

        for item in self.items:
            if item.product.product_id == product.product_id:
                new_qty = item.quantity + quantity
                if new_qty > product.stock:
                    raise OutOfStockError(product.product_id, new_qty, product.stock)
                item.quantity = new_qty
                return
        # Новый товар
        self.items.append(CartItem(product, quantity))

    def remove_item(self, product_id: str) -> bool:
        """
        Удаляет товар из корзины полностью.

        Параметры:
            product_id (str): ID товара.

        Возвращает:
            bool: True, если товар был удалён.
        """
        for i, item in enumerate(self.items):
            if item.product.product_id == product_id:
                del self.items[i]
                return True
        return False

    def update_quantity(self, product_id: str, new_quantity: int) -> None:
        """
        Изменяет количество единиц товара в корзине.

        Параметры:
            product_id (str): ID товара.
            new_quantity (int): Новое количество.

        Исключения:
            ValueError: Если товар не найден в корзине.
            OutOfStockError: Если новое количество превышает остаток.
        """
        if new_quantity <= 0:
            self.remove_item(product_id)
            return

        for item in self.items:
            if item.product.product_id == product_id:
                if new_quantity > item.product.stock:
                    raise OutOfStockError(product_id, new_quantity, item.product.stock)
                item.quantity = new_quantity
                return
        raise ValueError(f"Товар {product_id} не найден в корзине")

    def clear(self) -> None:
        """Очищает корзину полностью."""
        self.items.clear()

    @property
    def total_items(self) -> int:
        """Общее количество единиц товаров в корзине."""
        return sum(item.quantity for item in self.items)

    @property
    def subtotal(self) -> float:
        """Сумма стоимостей всех позиций без скидок."""
        return sum(item.total_price for item in self.items)

    def is_empty(self) -> bool:
        """Проверяет, пуста ли корзина."""
        return len(self.items) == 0

    def __str__(self) -> str:
        if self.is_empty():
            return "Корзина пуста"
        lines = [f"Корзина пользователя {self.owner.user_id}:"]
        for item in self.items:
            lines.append(f"  {item}")
        lines.append(f"Итого: {self.subtotal:.2f} руб.")
        return "\n".join(lines)


class Discount(ABC):
    """
    Абстрактный базовый класс для скидок.

    Подклассы должны реализовать метод apply, возвращающий сумму скидки
    на основе переданного заказа или корзины.
    """

    def __init__(self, code: str, description: str = ""):
        """
        Инициализация скидки.

        Параметры:
            code (str): Уникальный промокод.
            description (str): Описание.
        """
        self.code = code
        self.description = description

    @abstractmethod
    def apply(self, cart: Cart) -> float:
        """
        Рассчитывает абсолютную сумму скидки для данной корзины.

        Параметры:
            cart (Cart): Корзина, к которой применяется скидка.

        Возвращает:
            float: Размер скидки в денежных единицах.
        """
        pass

    def __str__(self) -> str:
        return f"Скидка '{self.code}': {self.description}"


class PercentageDiscount(Discount):
    """
    Процентная скидка от суммы корзины.

    Атрибуты:
        percent (float): Процент скидки (от 0 до 100).
        max_discount (float): Максимальная сумма скидки (опционально).
    """

    def __init__(self, code: str, percent: float, max_discount: float = float('inf'), description: str = ""):
        """
        Инициализация процентной скидки.

        Параметры:
            code (str): Промокод.
            percent (float): Процент.
            max_discount (float): Лимит скидки.
            description (str): Описание.

        Исключения:
            ValueError: Если процент вне диапазона [0, 100].
        """
        super().__init__(code, description)
        if not 0 <= percent <= 100:
            raise ValueError("Процент должен быть от 0 до 100")
        self.percent = percent
        self.max_discount = max_discount

    def apply(self, cart: Cart) -> float:
        """
        Рассчитывает процентную скидку от подытога корзины.

        Параметры:
            cart (Cart): Корзина покупателя.

        Возвращает:
            float: Размер скидки.
        """
        discount = cart.subtotal * (self.percent / 100)
        return min(discount, self.max_discount)


class FixedDiscount(Discount):
    """
    Фиксированная скидка на сумму корзины (например, 500 руб. при заказе от 3000).

    Атрибуты:
        amount (float): Размер фиксированной скидки.
        min_subtotal (float): Минимальная сумма корзины для применения.
    """

    def __init__(self, code: str, amount: float, min_subtotal: float = 0.0, description: str = ""):
        """
        Инициализация фиксированной скидки.

        Параметры:
            code (str): Промокод.
            amount (float): Сумма скидки.
            min_subtotal (float): Порог активации.
            description (str): Описание.
        """
        super().__init__(code, description)
        if amount <= 0:
            raise ValueError("Сумма скидки должна быть положительной")
        self.amount = amount
        self.min_subtotal = min_subtotal

    def apply(self, cart: Cart) -> float:
        """
        Применяет фиксированную скидку, если подытог корзины >= порога.

        Параметры:
            cart (Cart): Корзина покупателя.

        Возвращает:
            float: Сумма скидки (0, если условие не выполнено).
        """
        if cart.subtotal >= self.min_subtotal:
            return self.amount
        return 0.0


class Order:
    """
    Заказ, создаваемый после оформления покупки.

    Атрибуты:
        order_id (str): Уникальный номер заказа.
        user (User): Покупатель.
        items (List[CartItem]): Копия позиций корзины на момент заказа.
        discount_applied (float): Применённая скидка.
        total (float): Итоговая стоимость.
        status (str): Статус заказа (created, paid, shipped, delivered, cancelled).
        created_at (datetime): Дата и время создания.
    """

    VALID_STATUSES = ("created", "paid", "shipped", "delivered", "cancelled")

    def __init__(self, order_id: str, user: User, cart: Cart, discount: float = 0.0):
        """
        Инициализация заказа на основе корзины.

        Параметры:
            order_id (str): ID заказа.
            user (User): Пользователь.
            cart (Cart): Корзина с товарами.
            discount (float): Сумма скидки.

        Исключения:
            EmptyCartError: Если корзина пуста.
        """
        if cart.is_empty():
            raise EmptyCartError(user.user_id)
        self.order_id = order_id
        self.user = user
        # Создаём копии позиций, чтобы зафиксировать состояние
        self.items = [CartItem(item.product, item.quantity) for item in cart.items]
        self.discount_applied = discount
        self.total = max(0.0, cart.subtotal - discount)
        self.status = "created"
        self.created_at = datetime.now()

    def update_status(self, new_status: str) -> None:
        """
        Изменяет статус заказа с проверкой допустимости перехода.

        Параметры:
            new_status (str): Целевой статус.

        Исключения:
            ValueError: Если статус недопустим или переход невозможен.
        """
        if new_status not in self.VALID_STATUSES:
            raise ValueError(f"Недопустимый статус: {new_status}. Допустимые: {self.VALID_STATUSES}")
        # Пример логики переходов
        allowed_transitions = {
            "created": ["paid", "cancelled"],
            "paid": ["shipped", "cancelled"],
            "shipped": ["delivered"],
            "delivered": [],  # конечный
            "cancelled": []  # конечный
        }
        if new_status in allowed_transitions.get(self.status, []):
            self.status = new_status
        else:
            raise ValueError(f"Недопустимый переход из '{self.status}' в '{new_status}'")

    def __str__(self) -> str:
        """Строковое представление заказа."""
        items_str = ", ".join(f"{item.product.name} x{item.quantity}" for item in self.items)
        return (f"Заказ #{self.order_id} ({self.status}), {self.created_at:%Y-%m-%d %H:%M}, "
                f"Товары: {items_str}, Скидка: {self.discount_applied:.2f}, Итого: {self.total:.2f} руб.")

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация заказа в словарь."""
        return {
            "order_id": self.order_id,
            "user_id": self.user.user_id,
            "items": [{"product_id": item.product.product_id, "quantity": item.quantity} for item in self.items],
            "discount_applied": self.discount_applied,
            "total": self.total,
            "status": self.status,
            "created_at": self.created_at.isoformat()
        }


class Store:
    """
    Центральный класс интернет-магазина.

    Управляет каталогом товаров, пользователями, скидками и заказами.
    Предоставляет высокоуровневые методы для покупок.
    """

    def __init__(self, name: str = "Мой Магазин"):
        """
        Инициализация магазина.

        Параметры:
            name (str): Название магазина.
        """
        self.name = name
        self.products: Dict[str, Product] = {}
        self.users: Dict[str, User] = {}
        self.orders: List[Order] = []
        self.discounts: Dict[str, Discount] = {}

    def add_product(self, product: Product) -> None:
        """
        Добавляет товар в каталог. Если товар с таким ID уже есть, обновляет остаток.

        Параметры:
            product (Product): Товар.
        """
        if product.product_id in self.products:
            existing = self.products[product.product_id]
            existing.stock += product.stock
            # Можно решить, обновлять ли цену и другие поля
        else:
            self.products[product.product_id] = product

    def register_user(self, user: User) -> None:
        """
        Регистрирует нового пользователя.

        Параметры:
            user (User): Пользователь.

        Исключения:
            ValueError: Если пользователь уже существует.
        """
        if user.user_id in self.users:
            raise ValueError(f"Пользователь {user.user_id} уже зарегистрирован")
        self.users[user.user_id] = user

    def add_discount(self, discount: Discount) -> None:
        """
        Добавляет скидочный промокод.

        Параметры:
            discount (Discount): Объект скидки.

        Исключения:
            ValueError: Если код уже используется.
        """
        if discount.code in self.discounts:
            raise ValueError(f"Промокод '{discount.code}' уже существует")
        self.discounts[discount.code] = discount

    def apply_discount_code(self, user_id: str, code: str) -> float:
        """
        Применяет промокод к корзине пользователя и возвращает сумму скидки.

        Параметры:
            user_id (str): ID пользователя.
            code (str): Промокод.

        Возвращает:
            float: Размер скидки.

        Исключения:
            UserNotFoundError, InvalidDiscountError.
        """
        user = self.users.get(user_id)
        if not user:
            raise ValueError(f"Пользователь {user_id} не найден")
        discount = self.discounts.get(code)
        if not discount:
            raise InvalidDiscountError(code, "Промокод не существует")
        cart = user.cart
        if cart.is_empty():
            raise InvalidDiscountError(code, "Корзина пуста")
        return discount.apply(cart)

    def checkout(self, user_id: str, discount_code: Optional[str] = None) -> Order:
        """
        Оформление заказа: списывает товары со склада, применяет скидку,
        очищает корзину и создаёт заказ.

        Параметры:
            user_id (str): ID пользователя.
            discount_code (Optional[str]): Промокод (если есть).

        Возвращает:
            Order: Созданный заказ.

        Исключения:
            ValueError: Если пользователь не найден.
            EmptyCartError: Если корзина пуста.
            OutOfStockError: Если для какого-то товара недостаточно остатка.
            InvalidDiscountError: Если промокод недействителен.
        """
        user = self.users.get(user_id)
        if not user:
            raise ValueError(f"Пользователь {user_id} не найден")
        cart = user.cart
        if cart.is_empty():
            raise EmptyCartError(user_id)

        # Валидация наличия всех товаров в требуемом количестве
        for item in cart.items:
            product = self.products.get(item.product.product_id)
            if not product or product.stock < item.quantity:
                raise OutOfStockError(item.product.product_id, item.quantity,
                                      product.stock if product else 0)

        # Применение скидки
        discount_amount = 0.0
        if discount_code:
            discount_amount = self.apply_discount_code(user_id, discount_code)

        # Списание со склада
        for item in cart.items:
            product = self.products[item.product.product_id]
            product.reduce_stock(item.quantity)

        # Создание заказа
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        order = Order(order_id, user, cart, discount_amount)
        self.orders.append(order)

        # Очистка корзины
        cart.clear()
        return order

    def get_orders_by_user(self, user_id: str) -> List[Order]:
        """
        Возвращает все заказы указанного пользователя.

        Параметры:
            user_id (str): ID пользователя.

        Возвращает:
            List[Order]: Список заказов.
        """
        return [o for o in self.orders if o.user.user_id == user_id]

    def inventory_report(self) -> str:
        """
        Генерирует отчёт по товарным запасам.

        Возвращает:
            str: Текстовый отчёт.
        """
        lines = [f"=== Инвентаризация магазина '{self.name}' ===", f"Дата: {datetime.now():%Y-%m-%d %H:%M}"]
        total_value = 0.0
        for prod in self.products.values():
            lines.append(f"{prod}")
            total_value += prod.price * prod.stock
        lines.append(f"Общая стоимость остатков: {total_value:.2f} руб.")
        return "\n".join(lines)

    def sales_report(self) -> str:
        """
        Генерирует отчёт по продажам.

        Возвращает:
            str: Текстовый отчёт с суммой продаж и количеством заказов.
        """
        total_revenue = sum(order.total for order in self.orders if order.status != "cancelled")
        order_count = len(self.orders)
        completed = sum(1 for o in self.orders if o.status == "delivered")
        lines = [
            f"=== Отчёт о продажах '{self.name}' ===",
            f"Всего заказов: {order_count}",
            f"Выполненных заказов: {completed}",
            f"Общая выручка: {total_revenue:.2f} руб."
        ]
        return "\n".join(lines)


# ----------------------------------------------------------------------
# Демонстрационная функция
# ----------------------------------------------------------------------
def main():
    """Демонстрация работы интернет-магазина."""
    store = Store("ТехноМаркет")

    # Наполнение каталога
    products_data = [
        Product("P100", "Ноутбук", "Электроника", 55000.0, 10, "Мощный игровой ноутбук"),
        Product("P200", "Смартфон", "Электроника", 32000.0, 25, "Флагманский смартфон"),
        Product("P300", "Наушники", "Аксессуары", 3500.0, 50, "Беспроводные наушники"),
        Product("P400", "Книга Python", "Книги", 1200.0, 100, "Учебник по Python"),
        Product("P500", "Кофемашина", "Техника", 15000.0, 5, "Автоматическая кофемашина"),
    ]
    for p in products_data:
        store.add_product(p)

    # Регистрация пользователей
    alice = User("alice", "Алиса Иванова", "alice@example.com", "ул. Ленина, д.1")
    bob = User("bob", "Боб Петров", "bob@example.com", "пр. Мира, д.42")
    store.register_user(alice)
    store.register_user(bob)

    # Добавление скидочных промокодов
    store.add_discount(PercentageDiscount("SALE10", 10, max_discount=2000, description="10% скидка, макс 2000 руб."))
    store.add_discount(FixedDiscount("WELCOME500", 500, min_subtotal=5000, description="500 руб. при заказе от 5000"))

    # Работа с корзиной Алисы
    alice.cart.add_item(store.products["P100"], 1)  # Ноутбук
    alice.cart.add_item(store.products["P300"], 2)  # Наушники x2
    print(alice.cart)

    # Применение промокода
    try:
        discount = store.apply_discount_code("alice", "SALE10")
        print(f"Применена скидка: {discount:.2f} руб.")
    except (InvalidDiscountError, ValueError) as e:
        print(f"Ошибка скидки: {e}")

    # Оформление заказа
    try:
        order1 = store.checkout("alice", "SALE10")
        print("=== Создан заказ ===")
        print(order1)
    except Exception as e:
        print(f"Не удалось оформить заказ: {e}")

    # Работа с Бобом: добавим товары и попробуем оформить с фиксированной скидкой
    bob.cart.add_item(store.products["P200"], 1)
    bob.cart.add_item(store.products["P400"], 5)
    bob.cart.add_item(store.products["P500"], 1)  # Итого должно быть больше 5000
    print("\n" + str(bob.cart))
    try:
        order2 = store.checkout("bob", "WELCOME500")
        print("=== Создан заказ ===")
        print(order2)
    except Exception as e:
        print(f"Не удалось оформить заказ: {e}")

    # Изменение статуса заказа
    order1.update_status("paid")
    order1.update_status("shipped")
    print(f"\nОбновлённый статус заказа #{order1.order_id}: {order1.status}")

    # Отчёты
    print("\n" + store.inventory_report())
    print("\n" + store.sales_report())

    # Покажем историю заказов пользователя
    print("\n=== Заказы Алисы ===")
    for o in store.get_orders_by_user("alice"):
        print(o)

    print("\n=== Демонстрация завершена ===")


if __name__ == "__main__":
    main()