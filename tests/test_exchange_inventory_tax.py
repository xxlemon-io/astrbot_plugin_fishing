from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta

# Provide a lightweight astrbot.api.logger stub for unit tests.
class _DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass


if "astrbot.api" not in sys.modules:
    astrbot_module = types.ModuleType("astrbot")
    api_module = types.ModuleType("astrbot.api")
    api_module.logger = _DummyLogger()
    astrbot_module.api = api_module
    sys.modules["astrbot"] = astrbot_module
    sys.modules["astrbot.api"] = api_module

from core.domain.models import Exchange, User, UserCommodity
from core.services.exchange_inventory_service import ExchangeInventoryService


class FakeUserRepo:
    def __init__(self, user: User):
        self._user = user

    def get_by_id(self, user_id: str) -> User | None:
        return self._user if self._user.user_id == user_id else None

    def update(self, user: User) -> None:
        self._user = user


class FakeExchangeRepo:
    def __init__(self, commodities: list[UserCommodity], price_map: dict[str, list[Exchange]] | None = None):
        self._commodities = list(commodities)
        self.price_map = price_map or {}

    def get_user_commodities(self, user_id: str) -> list[UserCommodity]:
        return list(self._commodities)

    def delete_user_commodity(self, instance_id: int) -> None:
        self._commodities = [item for item in self._commodities if item.instance_id != instance_id]

    def update_user_commodity_quantity(self, instance_id: int, quantity: int) -> None:
        for item in self._commodities:
            if item.instance_id == instance_id:
                item.quantity = quantity
                break

    def clear_expired_commodities(self, user_id: str) -> int:
        return 0

    def add_user_commodity(self, user_commodity: UserCommodity) -> None:
        self._commodities.append(user_commodity)

    def get_user_commodity_by_instance_id(self, instance_id: int) -> UserCommodity | None:
        for item in self._commodities:
            if item.instance_id == instance_id:
                return item
        return None

    def get_prices_for_date(self, date_str: str) -> list[Exchange]:
        return self.price_map.get(date_str, [])


class FakeLogRepo:
    def __init__(self):
        self.records = []

    def add_tax_record(self, record):
        self.records.append(record)


def _build_user(user_id: str = "user-1", coins: int = 0) -> User:
    return User(user_id=user_id, created_at=datetime.now(), nickname="tester", coins=coins)


def _commodity(instance_id: int, quantity: int, purchase_price: int, expires_delta_days: int = 3) -> UserCommodity:
    return UserCommodity(
        instance_id=instance_id,
        user_id="user-1",
        commodity_id="dried_fish",
        quantity=quantity,
        purchase_price=purchase_price,
        purchased_at=datetime.now() - timedelta(days=1),
        expires_at=datetime.now() + timedelta(days=expires_delta_days),
    )


def test_sell_commodity_taxes_only_profit():
    user = _build_user()
    repo = FakeExchangeRepo([_commodity(1, 10, 100)])
    log_repo = FakeLogRepo()
    service = ExchangeInventoryService(FakeUserRepo(user), repo, {"exchange": {"tax_rate": 0.1}}, log_repo)

    result = service.sell_commodity("user-1", "dried_fish", 10, current_price=150)

    assert result["success"]
    assert result["tax_amount"] == 50  # 500 profit * 10% tax
    assert "税基 500" in result["message"]
    assert log_repo.records[-1].original_amount == 500
    assert "毛收入 1,500 金币" in log_repo.records[-1].tax_type


def test_sell_commodity_with_loss_has_no_tax():
    user = _build_user()
    repo = FakeExchangeRepo([_commodity(1, 5, 200)])
    log_repo = FakeLogRepo()
    service = ExchangeInventoryService(FakeUserRepo(user), repo, {"exchange": {"tax_rate": 0.2}}, log_repo)

    result = service.sell_commodity("user-1", "dried_fish", 5, current_price=150)

    assert result["tax_amount"] == 0
    assert "本次无税费" in result["message"]
    assert log_repo.records[-1].tax_amount == 0
    assert "未盈利免税" in log_repo.records[-1].tax_type


def test_clear_all_inventory_uses_profit_as_tax_base():
    today = datetime.now().strftime("%Y-%m-%d")
    user = _build_user()
    commodities = [
        _commodity(1, 2, 100),
        _commodity(2, 1, 50),
    ]
    price_entries = [Exchange(date=today, time="00:00:00", commodity_id="dried_fish", price=200)]
    repo = FakeExchangeRepo(commodities, price_map={today: price_entries})
    log_repo = FakeLogRepo()
    service = ExchangeInventoryService(FakeUserRepo(user), repo, {"exchange": {"tax_rate": 0.2}}, log_repo)

    result = service.clear_all_inventory("user-1")

    assert result["success"]
    # Cost = 2*100 + 1*50 = 250; value = 3*200 = 600; profit = 350; tax = 70
    assert result["tax_amount"] == 70
    assert "税基 350" in result["message"]
    assert log_repo.records[-1].original_amount == 350
    assert log_repo.records[-1].tax_amount == 70

