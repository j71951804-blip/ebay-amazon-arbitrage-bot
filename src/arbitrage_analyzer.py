import uuid
from decimal import Decimal
from typing import List, Dict, Tuple
import logging
from difflib import SequenceMatcher
import re

from models import Product, ArbitrageOpportunity, ProfitThresholds

logger = logging.getLogger(__name__)


class ArbitrageAnalyzer:
    """Analyzes products across platforms to find arbitrage opportunities"""
    
    def __init__(self, profit_thresholds: ProfitThresholds):
        self.profit_thresholds = profit_thresholds
        self.fee_calculators = {
            'ebay': self._calculate_ebay_fees,
            'amazon': self._calculate_amazon_fees
        }
    
    def find_opportunities(self, 
                          source_products: List[Product], 
                          target_products: List[Product]) -> List[ArbitrageOpportunity]:
        """Find arbitrage opportunities between two product lists"""
        opportunities = []
        
        # Create title-based matches
        matches = self._match_products(source_products, target_products)
        
        for source_product, target_product, similarity in matches:
            if similarity < 0.7:  # Skip low-similarity matches
                continue
                
            opportunity = self._analyze_opportunity(source_product, target_product)
            
            if self._is_profitable_opportunity(opportunity):
                opportunities.append(opportunity)
        
        # Sort by profit descending
        opportunities.sort(key=lambda x: x.net_profit, reverse=True)
        
        logger.info(f"Found {len(opportunities)} profitable opportunities")
        return opportunities
    
    def _match_products(self, source_products: List[Product], 
                       target_products: List[Product]) -> List[Tuple[Product, Product, float]]:
        """Match products between platforms based on title similarity"""
        matches = []
        
        for source_product in source_products:
            source_title = self._normalize_title(source_product.title)
            
            for target_product in target_products:
                target_title = self._normalize_title(target_product.title)
                
                # Calculate similarity
                similarity = SequenceMatcher(None, source_title, target_title).ratio()
                
                if similarity > 0.6:  # Minimum similarity threshold
                    matches.append((source_product, target_product, similarity))
        
        # Sort by similarity and keep best matches
        matches.sort(key=lambda x: x[2], reverse=True)
        
        # Remove duplicate matches (keep highest similarity)
        seen_sources = set()
        seen_targets = set()
        unique_matches = []
        
        for source, target, similarity in matches:
            if source.product_id not in seen_sources and target.product_id not in seen_targets:
                unique_matches.append((source, target, similarity))
                seen_sources.add(source.product_id)
                seen_targets.add(target.product_id)
        
        return unique_matches
    
    def _normalize_title(self, title: str) -> str:
        """Normalize product title for comparison"""
        if not title:
            return ""
            
        # Convert to lowercase
        title = title.lower()
        
        # Remove common marketplace words
        remove_words = [
            'new', 'used', 'refurbished', 'genuine', 'original', 'official',
            'fast', 'free', 'shipping', 'delivery', 'uk', 'gb', 'europe',
            'warranty', 'sealed', 'boxed', 'brand'
        ]
        
        for word in remove_words:
            title = re.sub(r'\b' + word + r'\b', '', title)
        
        # Remove extra whitespace and special characters
        title = re.sub(r'[^\w\s]', ' ', title)
        title = re.sub(r'\s+', ' ', title).strip()
        
        return title
    
    def _analyze_opportunity(self, source_product: Product, target_product: Product) -> ArbitrageOpportunity:
        """Analyze a potential arbitrage opportunity"""
        opportunity_id = str(uuid.uuid4())
        
        # Calculate costs
        source_total_cost = source_product.price + source_product.shipping
        source_fees = self._calculate_fees(source_product.price, source_product.platform, 'buy')
        
        # Calculate revenue
        target_revenue = target_product.price
        target_fees = self._calculate_fees(target_product.price, target_product.platform, 'sell')
        target_shipping_cost = target_product.shipping  # What buyer pays
        
        # Net profit calculation
        total_costs = source_total_cost + source_fees + target_fees
        net_profit = target_revenue - total_costs
        
        # ROI calculation
        roi_percentage = float((net_profit / total_costs) * 100) if total_costs > 0 else 0
        
        # Risk scoring
        risk_score = self._calculate_risk_score(source_product, target_product, net_profit)
        
        # Demand scoring (simplified)
        demand_score = self._estimate_demand_score(target_product)
        
        return ArbitrageOpportunity(
            opportunity_id=opportunity_id,
            source_platform=source_product.platform,
            target_platform=target_product.platform,
            product_title=target_product.title,
            source_price=source_product.price,
            target_price=target_product.price,
            source_url=source_product.url,
            target_url=target_product.url,
            source_shipping=source_product.shipping,
            target_shipping=target_product.shipping,
            source_fees=source_fees,
            target_fees=target_fees,
            net_profit=net_profit,
            roi_percentage=roi_percentage,
            source_seller_rating=source_product.seller_rating,
            target_seller_rating=target_product.seller_rating,
            source_stock=source_product.stock,
            target_demand_score=demand_score,
            risk_score=risk_score
        )
    
    def _calculate_fees(self, price: Decimal, platform: str, transaction_type: str) -> Decimal:
        """Calculate platform-specific fees"""
        calculator = self.fee_calculators.get(platform)
        if calculator:
            return calculator(price, transaction_type)
        return Decimal('0')
    
    def _calculate_ebay_fees(self, price: Decimal, transaction_type: str) -> Decimal:
        """Calculate eBay fees"""
        if transaction_type == 'sell':
            # eBay selling fees (UK)
            listing_fee = Decimal('0.35')  # First 1000 listings free
            final_value_fee = price * Decimal('0.129')  # 12.9%
            payment_processing = price * Decimal('0.03') + Decimal('0.30')  # 3% + £0.30
            return listing_fee + final_value_fee + payment_processing
        else:
            # Buying fees (minimal)
            return Decimal('0')
    
    def _calculate_amazon_fees(self, price: Decimal, transaction_type: str) -> Decimal:
        """Calculate Amazon fees"""
        if transaction_type == 'sell':
            # Amazon FBA fees (simplified)
            referral_fee = price * Decimal('0.15')  # 15% for most categories
            fba_fee = Decimal('2.50')  # Simplified FBA fee
            storage_fee = Decimal('0.75')  # Monthly storage
            return referral_fee + fba_fee + storage_fee
        else:
            # Buying fees
            return Decimal('0')
    
    def _calculate_risk_score(self, source_product: Product, target_product: Product, profit: Decimal) -> float:
        """Calculate risk score (0-10, higher is riskier)"""
        risk = 0.0
        
        # Price difference risk
        if source_product.price > 0:
            price_ratio = float(target_product.price / source_product.price)
            if price_ratio > 3:  # Very high markup
                risk += 3.0
            elif price_ratio > 2:
                risk += 1.5
        
        # Seller rating risk
        if source_product.seller_rating < 4.0:
            risk += 2.0
        if target_product.seller_rating < 4.0:
            risk += 1.0
        
        # Stock availability risk
        if source_product.stock < 5:
            risk += 1.5
        if source_product.stock == 0:
            risk += 3.0
        
        # Profit margin risk
        if profit < Decimal('5'):
            risk += 2.0
        elif profit < Decimal('15'):
            risk += 1.0
        
        # Platform risk
        platform_risk = {
            'ebay': 1.0,    # Individual sellers
            'amazon': 0.5   # More regulated
        }
        risk += platform_risk.get(source_product.platform, 1.0)
        
        return min(risk, 10.0)
    
    def _estimate_demand_score(self, product: Product) -> float:
        """Estimate demand score based on available data"""
        score = 5.0  # Baseline
        
        # Category-based demand (simplified)
        high_demand_keywords = [
            'iphone', 'samsung', 'apple', 'sony', 'nintendo', 
            'playstation', 'xbox', 'airpods', 'macbook'
        ]
        
        title_lower = product.title.lower()
        for keyword in high_demand_keywords:
            if keyword in title_lower:
                score += 2.0
                break
        
        # Price range demand
        if Decimal('20') <= product.price <= Decimal('200'):
            score += 1.0  # Sweet spot for flipping
        
        return min(score, 10.0)
    
    def _is_profitable_opportunity(self, opportunity: ArbitrageOpportunity) -> bool:
        """Check if opportunity meets profit thresholds"""
        return (
            opportunity.net_profit >= self.profit_thresholds.min_profit_gbp and
            opportunity.roi_percentage >= self.profit_thresholds.min_roi_percentage and
            opportunity.risk_score <= self.profit_thresholds.max_risk_score and
            opportunity.source_seller_rating >= self.profit_thresholds.min_seller_rating
        )
    
    def get_opportunity_summary(self, opportunities: List[ArbitrageOpportunity]) -> Dict:
        """Get summary statistics for opportunities"""
        if not opportunities:
            return {
                'total_opportunities': 0,
                'total_potential_profit': Decimal('0'),
                'average_roi': 0.0,
                'average_risk_score': 0.0
            }
        
        total_profit = sum(opp.net_profit for opp in opportunities)
        avg_roi = sum(opp.roi_percentage for opp in opportunities) / len(opportunities)
        avg_risk = sum(opp.risk_score for opp in opportunities) / len(opportunities)
        
        return {
            'total_opportunities': len(opportunities),
            'total_potential_profit': total_profit,
            'average_roi': avg_roi,
            'average_risk_score': avg_risk,
            'high_profit_opportunities': len([opp for opp in opportunities 
                                            if opp.net_profit >= self.profit_thresholds.alert_profit_gbp])
        }
