"""各網站 adapter；鍵為 `reference.json` 的來源名稱。"""

from .base import Site
from .futu import Futu
from .stockanalysis import StockAnalysis
from .tradingview import TradingView

SITES: dict[str, Site] = {site.name: site for site in (StockAnalysis(), Futu(), TradingView())}
