"""Testes unitários do serviço de estoque com cache (T5.2 e T5.3)."""

import pytest

from app.application.stock_service import StockService
from app.domain import (
    OutOfStockError,
    ProductId,
    StockLevel,
    StockNotFoundError,
)
from app.infrastructure.in_memory import InMemoryStockCache, InMemoryStockRepository


def _stock(product_id: int, available: int) -> StockLevel:
    return StockLevel(product_id=ProductId(product_id), available=available)


def _service() -> tuple[StockService, InMemoryStockRepository, InMemoryStockCache]:
    repository = InMemoryStockRepository()
    cache = InMemoryStockCache()
    service = StockService(repository, cache)
    return service, repository, cache


async def test_stock_cached_after_first_fetch() -> None:
    service, repository, cache = _service()
    repository.add(_stock(10, 5))

    first = await service.get_stock(ProductId(10))
    second = await service.get_stock(ProductId(10))

    assert first == second
    assert repository.fetch_count() == 1
    assert cache.get_raw(ProductId(10)) is not None


async def test_missing_stock_returns_none() -> None:
    service, repository, _ = _service()

    result = await service.get_stock(ProductId(99))

    assert result is None
    assert repository.fetch_count() == 1


async def test_reserve_decrements_and_invalidates_cache() -> None:
    service, repository, cache = _service()
    repository.add(_stock(10, 5))

    await service.get_stock(ProductId(10))

    new_stock = await service.reserve(ProductId(10), 2)

    assert new_stock.available == 3
    assert cache.get_raw(ProductId(10)) is None


async def test_reserve_raises_when_out_of_stock() -> None:
    service, repository, _ = _service()
    repository.add(_stock(10, 1))

    with pytest.raises(OutOfStockError):
        await service.reserve(ProductId(10), 2)


async def test_reserve_raises_when_product_not_found() -> None:
    service, _, _ = _service()

    with pytest.raises(StockNotFoundError):
        await service.reserve(ProductId(99), 1)


async def test_invalidate_removes_cache_entry() -> None:
    service, repository, cache = _service()
    repository.add(_stock(10, 5))

    await service.get_stock(ProductId(10))
    await service.invalidate(ProductId(10))

    assert cache.get_raw(ProductId(10)) is None
