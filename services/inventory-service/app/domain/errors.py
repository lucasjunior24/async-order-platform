"""Erros do domínio de estoque.

Separa erros de negócio (sem estoque) de erros de infraestrutura
(indisponibilidade do repositório ou do cache).
"""


class InventoryError(Exception):
    """Base para erros do domínio de estoque."""


class OutOfStockError(InventoryError):
    """Levantada quando não há estoque suficiente para reservar o pedido."""

    def __init__(self, product_id: int) -> None:
        super().__init__(f"Estoque insuficiente para o produto {product_id}.")
        self.product_id = product_id


class StockNotFoundError(InventoryError):
    """Levantada quando o produto não existe no estoque."""

    def __init__(self, product_id: int) -> None:
        super().__init__(f"Produto {product_id} não encontrado no estoque.")
        self.product_id = product_id
