"""公司 parser 可以呼叫的 utility。

每個 utility 做一件事，不含任何一家公司的 tag、成員或分類名稱。既有 utility 只增不改：需要不同行為時新增一個。
"""

from .facts import Missing, describe, find, one_of, put

__all__ = ["Missing", "describe", "find", "one_of", "put"]
