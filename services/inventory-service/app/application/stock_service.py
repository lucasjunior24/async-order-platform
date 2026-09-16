"""Serviço de leitura e reserva de estoque com cache (T5.2 e T5.3).

Implementa cache read-through com TTL e invalidação após reserva, garantindo
que leituras repetidas não batam no banco e que o cache reflita o saldo mais
recente.
"""

from app.application.ports import StockCache, StockRepository
from app.domain import ProductId, StockLevel, StockNotFoundError


class StockService:
    """Coordena repositório de estoque e cache.

    - ``get_stock``: read-through (MISS → banco → populate cache).
    - ``reserve``: decrementa, persiste e invalida a entrada em cache.
    - ``invalidate``: remove a entrada em cache (invalidação orientada a eventos).
    """

    def __init__(
        self,
        repository: StockRepository,
        cache: StockCache,
        *,
        ttl: int = 60,
    ) -> None:
        self._repository = repository
        self._cache = cache
        self._ttl = ttl

    async def get_stock(self, product_id: ProductId) -> StockLevel | None:
        """Retorna o nível de estoque, lendo do cache quando disponível."""
        cached = await self._cache.get(product_id)
        if cached is not None:
            return cached

        stock = await self._repository.get(product_id)
        if stock is not None:
            await self._cache.set(stock, self._ttl)
        return stock

    async def reserve(self, product_id: ProductId, quantity: int) -> StockLevel:
        """Reserva `quantity` unidades, persiste e invalida o cache.

        Levanta ``OutOfStockError`` se o saldo for insuficiente e
        ``StockNotFoundError`` se o produto não existir.
        """
        stock = await self.get_stock(product_id)
        if stock is None:
            raise StockNotFoundError(product_id)

        new_stock = stock.decrement(quantity)
        await self._repository.save(new_stock)
        await self._cache.delete(product_id)
        return new_stock

    async def invalidate(self, product_id: ProductId) -> None:
        """Invalida a entrada em cache do produto."""
        await self._cache.delete(product_id)
