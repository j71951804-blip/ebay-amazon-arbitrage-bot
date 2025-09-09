from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class Product:
    """Product data structure"""
    platform: str
    product_id: str
    title: str
    price: Decimal
    currency: str = 'GBP'
    shipping: Decimal = Decimal('0')
    url: str = ''
    seller_rating: float = 0.0
    stock: int = 0
    condition: str = 'new'
    image_url: str = ''
    seller_id: str = ''
    category: str = 'general'


@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity data structure"""
    opportunity_id: str
    source_platform: str
    target_platform: str
    product_title: str
    source_price: Decimal
    target_price: Decimal
    source_url: str
    target_url: str
    source_shipping: Decimal = Decimal('0')
    target_shipping: Decimal = Decimal('0')
    source_fees: Decimal = Decimal('0')
    target_fees: Decimal = Decimal('0')
    net_profit: Decimal = Decimal('0')
    roi_percentage: float = 0.0
    source_seller_rating: float = 0.0
    target_seller_rating: float = 0.0
    source_stock: int = 0
    target_demand_score: float = 0.0
    risk_score: float = 0.0
    created_at: datetime = None
    status: str = 'new'
    notes: str = ''

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class MarketplaceConfig:
    """Marketplace configuration"""
    platform: str
    enabled: bool = True
    api_credentials: dict = None
    fee_structure: dict = None
    search_limits: dict = None

    def __post_init__(self):
        if self.api_credentials is None:
            self.api_credentials = {}
        if self.fee_structure is None:
            self.fee_structure = {}
        if self.search_limits is None:
            self.search_limits = {'max_results': 50, 'rate_limit': 10}


@dataclass
class ProfitThresholds:
    """Profit threshold configuration"""
    min_profit_gbp: Decimal = Decimal('10')
    min_roi_percentage: float = 25.0
    alert_profit_gbp: Decimal = Decimal('25')
    max_risk_score: float = 7.0
    min_seller_rating: float = 3.5
