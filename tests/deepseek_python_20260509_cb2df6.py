"""
Модуль банковской системы

Реализует модель управления клиентами, счетами и финансовыми операциями.
Включает классы Customer, Account (абстрактный), SavingsAccount, CheckingAccount,
Transaction и Bank. Предоставляет кастомные исключения для обработки ошибок,
а также демонстрационную функцию main(), показывающую основные сценарии использования.

Версия: 1.0
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional, Any
import uuid


# Пользовательские исключения
class InsufficientFundsError(Exception):
    """Исключение, выбрасываемое при недостатке средств на счёте."""

    def __init__(self, account_id: str, required: float, available: float):
        self.account_id = account_id
        self.required = required
        self.available = available
        super().__init__(f"Недостаточно средств на счёте {account_id}: требуется {required:.2f}, доступно {available:.2f}")


class AccountNotFoundError(Exception):
    """Исключение, выбрасываемое при обращении к несуществующему счёту."""

    def __init__(self, account_id: str):
        self.account_id = account_id
        super().__init__(f"Счёт {account_id} не найден")


class InvalidTransactionError(Exception):
    """Исключение при недопустимой транзакции (например, перевод самому себе)."""

    def __init__(self, message: str = "Недопустимая операция"):
        super().__init__(message)


class Transaction:
    """
    Класс, описывающий банковскую операцию.

    Атрибуты:
        transaction_id (str): Уникальный идентификатор транзакции.
        timestamp (datetime): Дата и время операции.
        from_account (str): Идентификатор счёта-отправителя (может быть None, если пополнение).
        to_account (str): Идентификатор счёта-получателя (может быть None, если снятие).
        amount (float): Сумма операции.
        description (str): Описание (например, "Перевод", "Снятие", "Пополнение").
    """

    def __init__(self, from_account: Optional[str], to_account: Optional[str], amount: float, description: str = ""):
        """
        Инициализация транзакции.

        Параметры:
            from_account (Optional[str]): ID отправителя.
            to_account (Optional[str]): ID получателя.
            amount (float): Сумма (должна быть > 0).
            description (str): Назначение платежа.

        Исключения:
            ValueError: Если сумма <= 0.
        """
        if amount <= 0:
            raise ValueError("Сумма транзакции должна быть положительной")
        self.transaction_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        self.timestamp = datetime.now()
        self.from_account = from_account
        self.to_account = to_account
        self.amount = amount
        self.description = description

    def __str__(self) -> str:
        """Удобочитаемое представление транзакции."""
        direction = "Пополнение" if self.from_account is None else (
            "Снятие" if self.to_account is None else "Перевод"
        )
        return (f"[{self.timestamp:%Y-%m-%d %H:%M}] {direction}: "
                f"{self.amount:.2f} | от {self.from_account or '—'} к {self.to_account or '—'} | {self.description}")

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация транзакции в словарь."""
        return {
            "transaction_id": self.transaction_id,
            "timestamp": self.timestamp.isoformat(),
            "from_account": self.from_account,
            "to_account": self.to_account,
            "amount": self.amount,
            "description": self.description
        }


class Account(ABC):
    """
    Абстрактный банковский счёт.

    Атрибуты:
        account_id (str): Уникальный номер счёта.
        owner (Customer): Владелец счёта.
        balance (float): Текущий баланс.
        transactions (List[Transaction]): История операций.
    """

    def __init__(self, account_id: str, owner: "Customer", initial_balance: float = 0.0):
        """
        Инициализация счёта.

        Параметры:
            account_id (str): Номер счёта.
            owner (Customer): Владелец.
            initial_balance (float): Начальный баланс (не может быть отрицательным).

        Исключения:
            ValueError: При отрицательном начальном балансе.
        """
        if initial_balance < 0:
            raise ValueError("Начальный баланс не может быть отрицательным")
        self.account_id = account_id
        self.owner = owner
        self.balance = initial_balance
        self.transactions: List[Transaction] = []

    def deposit(self, amount: float, description: str = "Пополнение") -> Transaction:
        """
        Пополнение счёта.

        Параметры:
            amount (float): Сумма пополнения (положительная).
            description (str): Описание.

        Возвращает:
            Transaction: Запись о транзакции.

        Исключения:
            ValueError: Если сумма <= 0.
        """
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной")
        self.balance += amount
        t = Transaction(from_account=None, to_account=self.account_id, amount=amount, description=description)
        self.transactions.append(t)
        return t

    def withdraw(self, amount: float, description: str = "Снятие") -> Transaction:
        """
        Снятие средств со счёта.

        Параметры:
            amount (float): Сумма снятия.
            description (str): Описание.

        Возвращает:
            Transaction: Запись о транзакции.

        Исключения:
            InsufficientFundsError: Если недостаточно средств.
            ValueError: Если сумма <= 0.
        """
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной")
        if not self._can_withdraw(amount):
            raise InsufficientFundsError(self.account_id, amount, self.balance)
        self.balance -= amount
        t = Transaction(from_account=self.account_id, to_account=None, amount=amount, description=description)
        self.transactions.append(t)
        return t

    @abstractmethod
    def _can_withdraw(self, amount: float) -> bool:
        """
        Проверяет, возможна ли операция снятия с учётом специфики типа счёта.

        Параметры:
            amount (float): Запрашиваемая сумма.

        Возвращает:
            bool: True, если снятие разрешено.
        """
        pass

    def get_balance(self) -> float:
        """Возвращает текущий баланс."""
        return self.balance

    def __str__(self) -> str:
        """Строковое представление счёта."""
        return f"Счёт {self.account_id} ({self.owner.name}), баланс: {self.balance:.2f}"

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация счёта в словарь (без владельца для циклической защиты)."""
        return {
            "account_id": self.account_id,
            "type": self.__class__.__name__,
            "balance": self.balance,
            "transactions": [t.to_dict() for t in self.transactions]
        }


class SavingsAccount(Account):
    """
    Сберегательный счёт с начислением процентов и ограничением на количество снятий в месяц.

    Атрибуты:
        interest_rate (float): Годовая процентная ставка (в долях, например 0.05 = 5%).
        max_withdrawals_per_month (int): Максимальное количество снятий в месяц.
        _withdrawal_count (int): Счётчик снятий за текущий месяц.
    """

    def __init__(self, account_id: str, owner: "Customer", initial_balance: float = 0.0,
                 interest_rate: float = 0.05, max_withdrawals: int = 3):
        """
        Инициализация сберегательного счёта.

        Параметры:
            account_id (str): Номер счёта.
            owner (Customer): Владелец.
            initial_balance (float): Начальный баланс.
            interest_rate (float): Процентная ставка.
            max_withdrawals (int): Лимит снятий в месяц.
        """
        super().__init__(account_id, owner, initial_balance)
        self.interest_rate = interest_rate
        self.max_withdrawals_per_month = max_withdrawals
        self._withdrawal_count = 0
        self._last_reset_month = datetime.now().month

    def _can_withdraw(self, amount: float) -> bool:
        """
        Проверяет, возможно ли снятие (достаточно средств и не превышен лимит операций).

        Параметры:
            amount (float): Сумма.

        Возвращает:
            bool: True, если снятие разрешено.
        """
        # Сброс счётчика снятий при новом месяце
        now = datetime.now()
        if now.month != self._last_reset_month:
            self._withdrawal_count = 0
            self._last_reset_month = now.month

        if self._withdrawal_count >= self.max_withdrawals_per_month:
            return False
        if amount > self.balance:
            return False
        return True

    def withdraw(self, amount: float, description: str = "Снятие") -> Transaction:
        """
        Снятие с учётом счётчика операций.

        Параметры:
            amount (float): Сумма.
            description (str): Описание.

        Возвращает:
            Transaction: Запись о транзакции.

        Исключения:
            InsufficientFundsError: Если недостаточно средств или превышен лимит снятий.
        """
        if not self._can_withdraw(amount):
            if amount > self.balance:
                raise InsufficientFundsError(self.account_id, amount, self.balance)
            else:
                raise InsufficientFundsError(self.account_id, amount, self.balance)  # можно своё исключение
        t = super().withdraw(amount, description)
        self._withdrawal_count += 1
        return t

    def add_interest(self) -> None:
        """Начисляет проценты на текущий баланс (годовые проценты делятся на 12 для месячного начисления)."""
        interest = self.balance * (self.interest_rate / 12)
        self.deposit(interest, description="Начисление процентов")

    def __str__(self) -> str:
        return (f"Сберегательный счёт {self.account_id} ({self.owner.name}), "
                f"баланс: {self.balance:.2f}, ставка: {self.interest_rate:.1%}, "
                f"снятий в этом месяце: {self._withdrawal_count}/{self.max_withdrawals_per_month}")


class CheckingAccount(Account):
    """
    Расчётный счёт с возможностью овердрафта.

    Атрибуты:
        overdraft_limit (float): Разрешённый лимит перерасхода (отрицательный баланс).
    """

    def __init__(self, account_id: str, owner: "Customer", initial_balance: float = 0.0,
                 overdraft_limit: float = 0.0):
        """
        Инициализация расчётного счёта.

        Параметры:
            account_id (str): Номер счёта.
            owner (Customer): Владелец.
            initial_balance (float): Начальный баланс.
            overdraft_limit (float): Лимит овердрафта (>= 0).
        """
        super().__init__(account_id, owner, initial_balance)
        if overdraft_limit < 0:
            raise ValueError("Лимит овердрафта не может быть отрицательным")
        self.overdraft_limit = overdraft_limit

    def _can_withdraw(self, amount: float) -> bool:
        """
        Проверка возможности снятия: баланс + овердрафт >= сумма.

        Параметры:
            amount (float): Сумма.

        Возвращает:
            bool: True, если снятие возможно.
        """
        return (self.balance + self.overdraft_limit) >= amount

    def __str__(self) -> str:
        return (f"Расчётный счёт {self.account_id} ({self.owner.name}), "
                f"баланс: {self.balance:.2f}, овердрафт: до {self.overdraft_limit:.2f}")


class Customer:
    """
    Клиент банка.

    Атрибуты:
        customer_id (str): Уникальный идентификатор клиента.
        name (str): Полное имя.
        email (str): Электронная почта.
        accounts (List[Account]): Счета клиента.
    """

    def __init__(self, customer_id: str, name: str, email: str):
        """
        Инициализация клиента.

        Параметры:
            customer_id (str): Идентификатор.
            name (str): Имя.
            email (str): Email.
        """
        self.customer_id = customer_id
        self.name = name
        self.email = email
        self.accounts: List[Account] = []

    def add_account(self, account: Account) -> None:
        """
        Добавляет счёт клиенту.

        Параметры:
            account (Account): Объект счёта.
        """
        self.accounts.append(account)

    def get_total_balance(self) -> float:
        """Возвращает суммарный баланс по всем счетам."""
        return sum(acc.balance for acc in self.accounts)

    def __str__(self) -> str:
        return f"Клиент {self.name} (ID: {self.customer_id}, email: {self.email}), счетов: {len(self.accounts)}"

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация клиента."""
        return {
            "customer_id": self.customer_id,
            "name": self.name,
            "email": self.email,
            "accounts": [acc.account_id for acc in self.accounts]
        }


class Bank:
    """
    Центральный класс банковской системы.

    Управляет клиентами, счетами, проводит транзакции и генерирует отчёты.

    Атрибуты:
        name (str): Название банка.
        customers (Dict[str, Customer]): Словарь клиентов по ID.
        accounts (Dict[str, Account]): Словарь счетов по ID.
    """

    def __init__(self, name: str = "Мой Банк"):
        """
        Инициализация банка.

        Параметры:
            name (str): Название банка.
        """
        self.name = name
        self.customers: Dict[str, Customer] = {}
        self.accounts: Dict[str, Account] = {}

    def register_customer(self, customer: Customer) -> None:
        """
        Регистрирует нового клиента.

        Параметры:
            customer (Customer): Объект клиента.

        Исключения:
            ValueError: Если клиент с таким ID уже существует.
        """
        if customer.customer_id in self.customers:
            raise ValueError(f"Клиент с ID {customer.customer_id} уже зарегистрирован")
        self.customers[customer.customer_id] = customer

    def open_account(self, account: Account) -> None:
        """
        Открывает счёт и привязывает его к клиенту.

        Параметры:
            account (Account): Счёт для открытия.

        Исключения:
            ValueError: Если счёт с таким ID уже существует.
            ValueError: Если владелец счёта не зарегистрирован в банке.
        """
        if account.account_id in self.accounts:
            raise ValueError(f"Счёт {account.account_id} уже существует")
        if account.owner.customer_id not in self.customers:
            raise ValueError(f"Клиент {account.owner.customer_id} не зарегистрирован")
        self.accounts[account.account_id] = account
        account.owner.add_account(account)

    def transfer(self, from_account_id: str, to_account_id: str, amount: float, description: str = "Перевод") -> Transaction:
        """
        Перевод средств между счетами.

        Параметры:
            from_account_id (str): Счёт отправителя.
            to_account_id (str): Счёт получателя.
            amount (float): Сумма.
            description (str): Назначение.

        Возвращает:
            Transaction: Запись о переводе.

        Исключения:
            AccountNotFoundError: Если один из счетов не найден.
            InvalidTransactionError: При переводе самому себе.
            InsufficientFundsError: При недостатке средств на счёте отправителя.
        """
        from_acc = self.accounts.get(from_account_id)
        to_acc = self.accounts.get(to_account_id)
        if not from_acc:
            raise AccountNotFoundError(from_account_id)
        if not to_acc:
            raise AccountNotFoundError(to_account_id)
        if from_account_id == to_account_id:
            raise InvalidTransactionError("Нельзя перевести средства на тот же счёт")

        # Снимаем с отправителя (внутренний withdraw без записи транзакции?)
        # Используем withdraw и deposit, которые уже создают транзакции.
        # Но нам нужна одна общая транзакция перевода.
        # Сначала проверим возможность снятия:
        if not from_acc._can_withdraw(amount):
            raise InsufficientFundsError(from_account_id, amount, from_acc.balance)

        # Выполняем перевод
        from_acc.balance -= amount
        to_acc.balance += amount

        transaction = Transaction(from_account=from_account_id, to_account=to_account_id,
                                  amount=amount, description=description)
        from_acc.transactions.append(transaction)
        to_acc.transactions.append(transaction)

        return transaction

    def get_customer_accounts(self, customer_id: str) -> List[Account]:
        """
        Возвращает все счета клиента.

        Параметры:
            customer_id (str): ID клиента.

        Возвращает:
            List[Account]: Список счетов.
        """
        customer = self.customers.get(customer_id)
        if not customer:
            raise ValueError(f"Клиент {customer_id} не найден")
        return customer.accounts

    def generate_customer_statement(self, customer_id: str) -> str:
        """
        Генерирует текстовую выписку по всем счетам клиента.

        Параметры:
            customer_id (str): ID клиента.

        Возвращает:
            str: Отформатированная выписка.
        """
        customer = self.customers.get(customer_id)
        if not customer:
            return f"Клиент {customer_id} не найден"
        lines = [f"=== Выписка по клиенту: {customer.name} ==="]
        for acc in customer.accounts:
            lines.append(f"\nСчёт {acc.account_id} (баланс: {acc.balance:.2f}):")
            for tr in acc.transactions[-10:]:  # последние 10 операций
                lines.append(f"  {tr}")
        return "\n".join(lines)

    def total_deposits(self) -> float:
        """Общая сумма средств на всех счетах."""
        return sum(acc.balance for acc in self.accounts.values())

    def __str__(self) -> str:
        return f"Банк '{self.name}': клиентов — {len(self.customers)}, счетов — {len(self.accounts)}"


# ----------------------------------------------------------------------
# Вспомогательные функции
# ----------------------------------------------------------------------
def generate_account_id(prefix: str = "ACC") -> str:
    """Генерирует уникальный идентификатор счёта."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


# ----------------------------------------------------------------------
# Демонстрационная функция
# ----------------------------------------------------------------------
def main():
    """Демонстрация работы банковской системы."""
    bank = Bank("Первый Национальный")

    # Регистрируем клиентов
    alice = Customer("C001", "Алиса Иванова", "alice@example.com")
    bob = Customer("C002", "Боб Петров", "bob@example.com")
    bank.register_customer(alice)
    bank.register_customer(bob)

    # Открываем счета
    acc1 = SavingsAccount(generate_account_id("SAV"), alice, initial_balance=10000.0, interest_rate=0.06, max_withdrawals=3)
    acc2 = CheckingAccount(generate_account_id("CHK"), alice, initial_balance=5000.0, overdraft_limit=2000.0)
    acc3 = CheckingAccount(generate_account_id("CHK"), bob, initial_balance=15000.0)

    bank.open_account(acc1)
    bank.open_account(acc2)
    bank.open_account(acc3)

    # Выполняем операции
    try:
        acc1.deposit(2000, "Зарплата")
        acc2.withdraw(3000, "Оплата аренды")
        bank.transfer(acc1.account_id, acc2.account_id, 1500, "Перевод на карту")
        bank.transfer(acc3.account_id, acc1.account_id, 5000, "Возврат долга")
        # Попытка снять больше лимита сберегательного счёта
        acc1.withdraw(12000)  # должно хватить? сейчас баланс ~ 10000+2000-1500+5000=15500, но лимит снятий: уже было снятие? нет
        acc1.withdraw(1000)  # второе снятие
        acc1.withdraw(1000)  # третье снятие
        # Четвёртое снятие должно вызвать ошибку
        acc1.withdraw(500)
    except (InsufficientFundsError, InvalidTransactionError, AccountNotFoundError) as e:
        print(f"Ошибка операции: {e}")

    # Начисление процентов по сберегательному счёту
    acc1.add_interest()
    print(f"После начисления процентов баланс сберегательного счёта: {acc1.get_balance():.2f}")

    # Вывод выписки
    print("\n" + bank.generate_customer_statement("C001"))

    # Общая информация
    print(f"\n{bank}")
    print(f"Общая сумма депозитов: {bank.total_deposits():.2f}")

    # Демонстрация ошибок
    print("\n--- Проверка исключений ---")
    try:
        # Перевод на несуществующий счёт
        bank.transfer(acc1.account_id, "BAD-ACC", 100)
    except Exception as e:
        print(f"Перехвачено: {e}")

    try:
        # Регистрация клиента с существующим ID
        bank.register_customer(Customer("C001", "Двойник", "d@d.com"))
    except Exception as e:
        print(f"Перехвачено: {e}")

    print("\n=== Демонстрация завершена ===")


if __name__ == "__main__":
    main()