import aiohttp
import base64
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import asyncio

from models import Product

logger = logging.getLogger(__name__)


class EbayAPI:
    """Enhanced eBay API integration for finding cheapest arbitrage opportunities"""
    
    def __init__(self, config):
        self.config = config['ebay']
        self.session = None
        self.token = None
        self.token_expiry = None
    
    async def init_session(self):
        """Initialize aiohttp session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_oauth_token(self):
        """Get OAuth token for eBay API"""
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token
        
        await self.init_session()
        
        credentials = f"{self.config['app_id']}:{self.config['cert_id']}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {encoded_credentials}'
        }
        
        data = {
            'grant_type': 'client_credentials',
            'scope': 'https://api.ebay.com/oauth/api_scope'
        }
        
        try:
            async with self.session.post(
                f"{self.config['api_endpoint']}/identity/v1/oauth2/token",
                headers=headers,
                data=data
            ) as response:
                if response.status == 200:
                    token_data = await response.json()
                    self.token = token_data['access_token']
                    self.token_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])
                    logger.info("eBay OAuth token obtained successfully")
                    return self.token
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get eBay token: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Error getting eBay OAuth token: {e}")
            return None
    
    async def search_cheapest_products(self, keyword: str, 
                                      max_price: float = 50.0,
                                      min_price: float = 0.01,
                                      limit: int = 100) -> List[Product]:
        """
        Search for the cheapest products on eBay with high resale potential
        
        Args:
            keyword: Search keyword
            max_price: Maximum price in GBP
            min_price: Minimum price in GBP (to avoid junk)
            limit: Number of results to return
        """
        await self.init_session()
        token = await self.get_oauth_token()
        
        if not token:
            logger.error("No valid eBay token available")
            return []
        
        all_products = []
        
        # Search strategies for finding cheap products
        search_strategies = [
            {'sort': 'price', 'condition': 'NEW'},           # Cheapest new items
            {'sort': 'price', 'condition': 'USED'},          # Cheapest used items
            {'sort': 'price', 'condition': 'REFURBISHED'},   # Refurbished deals
            {'sort': 'endingSoonest', 'condition': 'NEW'},   # Ending soon (potential deals)
        ]
        
        for strategy in search_strategies:
            products = await self._search_with_strategy(
                keyword, strategy, max_price, min_price, limit // len(search_strategies)
            )
            all_products.extend(products)
            
            # Small delay between searches
            await asyncio.sleep(0.5)
        
        # Sort by price and filter for best opportunities
        all_products.sort(key=lambda x: x.price)
        
        # Remove duplicates
        seen_ids = set()
        unique_products = []
        for product in all_products:
            if product.product_id not in seen_ids:
                seen_ids.add(product.product_id)
                unique_products.append(product)
        
        logger.info(f"Found {len(unique_products)} cheap products for '{keyword}'")
        return unique_products[:limit]
    
    async def _search_with_strategy(self, keyword: str, strategy: Dict,
                                   max_price: float, min_price: float,
                                   limit: int) -> List[Product]:
        """Execute a search with specific strategy"""
        headers = {
            'Authorization': f'Bearer {self.token}',
            'X-EBAY-C-MARKETPLACE-ID': self.config['marketplace_id']
        }
        
        # Build filters for cheap products
        filters = [
            f'price:[{min_price}..{max_price}]',
            f'conditions:{{{strategy["condition"]}}}',
            'deliveryCountry:GB',
            'buyItNowAvailable:true',
            'itemLocationCountry:GB'  # UK items (faster shipping)
        ]
        
        params = {
            'q': keyword,
            'limit': min(limit, 200),
            'filter': ','.join(filters),
            'sort': strategy['sort'],
            'fieldgroups': 'MATCHING_ITEMS,EXTENDED'
        }
        
        try:
            async with self.session.get(
                f"{self.config['api_endpoint']}/buy/browse/v1/item_summary/search",
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    products = self.parse_ebay_results(data.get('itemSummaries', []))
                    return products
                else:
                    error_text = await response.text()
                    logger.error(f"eBay search failed: {response.status} - {error_text}")
                    return []
        except Exception as e:
            logger.error(f"eBay API error in strategy search: {e}")
            return []
    
    async def find_arbitrage_goldmines(self, 
                                      categories: List[str] = None,
                                      budget: float = 100.0) -> List[Product]:
        """
        Find products with highest arbitrage potential
        Searches for underpriced items in specific categories
        """
        if categories is None:
            # High-profit potential categories
            categories = [
                'electronics clearance',
                'wholesale lot',
                'bulk sale',
                'job lot',
                'bundle deal',
                'liquidation stock',
                'overstock',
                'warehouse clearance',
                'returns pallet',
                'discontinued',
                'end of line',
                'shop closure'
            ]
        
        all_products = []
        
        for category in categories:
            logger.info(f"Searching for deals in: {category}")
            
            # Search for very cheap items in this category
            products = await self.search_cheapest_products(
                keyword=category,
                max_price=budget / 5,  # Look for items 1/5 of budget
                min_price=0.99,
                limit=20
            )
            
            all_products.extend(products)
            await asyncio.sleep(1)  # Rate limiting
        
        # Filter and rank by potential
        goldmines = self._identify_goldmines(all_products)
        
        return goldmines
    
    def _identify_goldmines(self, products: List[Product]) -> List[Product]:
        """Identify products with highest profit potential"""
        goldmines = []
        
        for product in products:
            # Calculate potential score
            score = self._calculate_arbitrage_score(product)
            
            if score > 50:  # Threshold for good opportunities
                goldmines.append(product)
        
        # Sort by score (highest potential first)
        goldmines.sort(key=lambda x: self._calculate_arbitrage_score(x), reverse=True)
        
        return goldmines[:50]  # Return top 50
    
    def _calculate_arbitrage_score(self, product: Product) -> float:
        """Calculate arbitrage potential score"""
        score = 100.0
        
        # Price factors
        if product.price < Decimal('5'):
            score += 30  # Very cheap items have high markup potential
        elif product.price < Decimal('10'):
            score += 20
        elif product.price < Decimal('20'):
            score += 10
        
        # Condition factors
        if product.condition == 'new':
            score += 20
        elif product.condition == 'refurbished':
            score += 10
        
        # Shipping factors
        if product.shipping == Decimal('0'):
            score += 15  # Free shipping is good
        elif product.shipping < Decimal('3'):
            score += 5
        
        # Seller rating
        if product.seller_rating >= 4.5:
            score += 10
        elif product.seller_rating >= 4.0:
            score += 5
        
        # Stock availability
        if product.stock > 10:
            score += 10  # Can buy multiple
        elif product.stock > 5:
            score += 5
        
        # Title analysis for valuable keywords
        valuable_keywords = [
            'apple', 'iphone', 'samsung', 'sony', 'nintendo', 'playstation',
            'xbox', 'dyson', 'bose', 'wholesale', 'bulk', 'lot', 'bundle'
        ]
        
        title_lower = product.title.lower()
        for keyword in valuable_keywords:
            if keyword in title_lower:
                score += 15
                break
        
        return score
    
    async def search_mispriced_items(self, limit: int = 50) -> List[Product]:
        """
        Search for potentially mispriced items
        These are items priced significantly below market value
        """
        mispricing_keywords = [
            'urgent sale',
            'quick sale',
            'must go',
            'moving sale',
            'divorce sale',
            'house clearance',
            'garage sale',
            'estate sale',
            'collection only',  # Often cheaper
            '99p start',
            'no reserve',
            'untested',  # Risky but potentially profitable
            'spares repair'  # For those who can fix
        ]
        
        all_products = []
        
        for keyword in mispricing_keywords[:5]:  # Limit searches
            products = await self.search_cheapest_products(
                keyword=keyword,
                max_price=30.0,
                min_price=0.01,
                limit=10
            )
            all_products.extend(products)
            await asyncio.sleep(0.5)
        
        return all_products
    
    async def search_bulk_opportunities(self, budget: float = 100.0) -> List[Product]:
        """
        Search for bulk/wholesale opportunities
        These can be split and sold individually for profit
        """
        bulk_keywords = [
            'wholesale lot',
            'job lot',
            'bulk pack',
            'bundle of',
            'box of',
            'pallet of',
            'carton',
            'multipack',
            'wholesale only',
            'trade pack'
        ]
        
        all_products = []
        
        for keyword in bulk_keywords:
            products = await self.search_cheapest_products(
                keyword=keyword,
                max_price=budget,
                min_price=10.0,  # Bulk items usually cost more
                limit=10
            )
            
            # Filter for actual bulk items
            bulk_products = [p for p in products if self._is_bulk_item(p)]
            all_products.extend(bulk_products)
            
            await asyncio.sleep(0.5)
        
        return all_products
    
    def _is_bulk_item(self, product: Product) -> bool:
        """Check if item is actually a bulk/wholesale item"""
        bulk_indicators = [
            'x', 'pcs', 'pieces', 'pack', 'lot', 'bundle',
            'wholesale', 'bulk', 'set of', 'pairs'
        ]
        
        title_lower = product.title.lower()
        
        # Check for quantity indicators (e.g., "10x", "5 pack", "lot of 20")
        import re
        quantity_pattern = r'\d+\s*(?:x|pcs|pieces|pack|items)'
        if re.search(quantity_pattern, title_lower):
            return True
        
        # Check for bulk keywords
        for indicator in bulk_indicators:
            if indicator in title_lower:
                return True
        
        return False
    
    def parse_ebay_results(self, items: List[Dict]) -> List[Product]:
        """Parse eBay search results with enhanced cheap product detection"""
        products = []
        
        for item in items:
            try:
                # Extract price information
                price_info = item.get('price', {})
                price_value = price_info.get('value', '0')
                price_currency = price_info.get('currency', 'GBP')
                
                # Skip if price is 0 or missing
                if float(price_value) <= 0:
                    continue
                
                # Extract shipping information
                shipping_options = item.get('shippingOptions', [])
                shipping_cost = Decimal('0')
                if shipping_options:
                    shipping_info = shipping_options[0].get('shippingCost', {})
                    if shipping_info:
                        shipping_cost = Decimal(str(shipping_info.get('value', '0')))
                
                # Extract availability
                availability = item.get('estimatedAvailabilities', [{}])[0]
                stock = availability.get('availabilityThreshold', 0)
                if not stock:
                    stock = availability.get('estimatedAvailableQuantity', 0)
                
                # Extract seller information
                seller = item.get('seller', {})
                seller_id = seller.get('username', '')
                seller_rating = self.extract_seller_rating(seller)
                
                # Skip low-rated sellers for cheap items (higher risk)
                if float(price_value) < 10 and seller_rating < 4.0:
                    continue
                
                # Extract image
                image_info = item.get('image', {})
                image_url = image_info.get('imageUrl', '') if image_info else ''
                
                # Extract category
                categories = item.get('categories', [])
                category = categories[0].get('categoryName', 'general') if categories else 'general'
                
                # Check for deal indicators in title
                title = item.get('title', '')
                deal_score = self._calculate_deal_score(title, float(price_value))
                
                product = Product(
                    platform='ebay',
                    product_id=item.get('itemId', ''),
                    title=title,
                    price=Decimal(str(price_value)),
                    currency=price_currency,
                    shipping=shipping_cost,
                    url=item.get('itemWebUrl', ''),
                    seller_rating=seller_rating,
                    stock=stock,
                    condition=item.get('condition', 'UNSPECIFIED').lower(),
                    image_url=image_url,
                    seller_id=seller_id,
                    category=category.lower()
                )
                
                # Only add products that seem like good deals
                if product.price > 0 and product.title and deal_score > 30:
                    products.append(product)
                
            except (ValueError, KeyError, TypeError) as e:
                logger.warning(f"Error parsing eBay item: {e}")
                continue
        
        return products
    
    def _calculate_deal_score(self, title: str, price: float) -> float:
        """Calculate how good a deal this might be"""
        score = 50.0  # Base score
        title_lower = title.lower()
        
        # Positive indicators
        deal_keywords = [
            'clearance', 'sale', 'reduced', 'bargain', 'deal',
            'wholesale', 'bulk', 'lot', 'bundle', 'multi',
            'rrp', 'was £', 'save', 'off', 'special'
        ]
        
        for keyword in deal_keywords:
            if keyword in title_lower:
                score += 10
        
        # Price-based scoring
        if price < 5:
            score += 20
        elif price < 10:
            score += 15
        elif price < 20:
            score += 10
        
        # Negative indicators (might not be a good deal)
        negative_keywords = [
            'faulty', 'broken', 'parts only', 'read description',
            'untested', 'spares', 'repair', 'cracked', 'damaged'
        ]
        
        for keyword in negative_keywords:
            if keyword in title_lower:
                score -= 15
        
        return score
    
    def extract_seller_rating(self, seller: Dict) -> float:
        """Extract seller rating from seller data"""
        try:
            feedback_percentage = seller.get('feedbackPercentage')
            if feedback_percentage is not None:
                # Convert percentage to 5-star scale
                return float(feedback_percentage) / 100 * 5
            
            # Fallback to score if available
            feedback_score = seller.get('feedbackScore', 0)
            if feedback_score > 1000:
                return 5.0
            elif feedback_score > 500:
                return 4.5
            elif feedback_score > 100:
                return 4.0
            elif feedback_score > 50:
                return 3.5
            else:
                return 3.0
                
        except (TypeError, ValueError):
            return 0.0
    
    def calculate_fees(self, price: Decimal, category: str = 'general') -> Decimal:
        """Calculate eBay selling fees"""
        try:
            # eBay UK fees (2024 rates)
            listing_fee = Decimal('0.35')  # First 1000 listings free for private sellers
            
            # Final value fee varies by category
            category_fees = {
                'motors': Decimal('0.10'),      # 10%
                'business': Decimal('0.12'),    # 12%
                'general': Decimal('0.129'),    # 12.9%
                'technology': Decimal('0.129'), # 12.9%
            }
            
            final_value_fee_rate = category_fees.get(category.lower(), Decimal('0.129'))
            final_value_fee = price * final_value_fee_rate
            
            # Payment processing fee
            payment_processing = price * Decimal('0.029') + Decimal('0.30')  # 2.9% + £0.30
            
            return listing_fee + final_value_fee + payment_processing
            
        except Exception as e:
            logger.error(f"Error calculating eBay fees: {e}")
            return Decimal('0')
    
    async def get_item_details(self, item_id: str) -> Optional[Product]:
        """Get detailed information for a specific item"""
        await self.init_session()
        token = await self.get_oauth_token()
        
        if not token:
            return None
        
        headers = {
            'Authorization': f'Bearer {token}',
            'X-EBAY-C-MARKETPLACE-ID': self.config['marketplace_id']
        }
        
        try:
            async with self.session.get(
                f"{self.config['api_endpoint']}/buy/browse/v1/item/{item_id}",
                headers=headers
            ) as response:
                if response.status == 200:
                    item_data = await response.json()
                    return self.parse_single_item(item_data)
                else:
                    logger.error(f"Failed to get item details: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting item details: {e}")
            return None
    
    def parse_single_item(self, item: Dict) -> Product:
        """Parse single eBay item details"""
        price_info = item.get('price', {})
        shipping_options = item.get('shippingOptions', [])
        shipping_cost = Decimal('0')
        
        if shipping_options:
            shipping_info = shipping_options[0].get('shippingCost', {})
            if shipping_info:
                shipping_cost = Decimal(str(shipping_info.get('value', '0')))
        
        seller = item.get('seller', {})
        availability = item.get('estimatedAvailabilities', [{}])[0]
        
        return Product(
            platform='ebay',
            product_id=item.get('itemId', ''),
            title=item.get('title', ''),
            price=Decimal(str(price_info.get('value', '0'))),
            currency=price_info.get('currency', 'GBP'),
            shipping=shipping_cost,
            url=item.get('itemWebUrl', ''),
            seller_rating=self.extract_seller_rating(seller),
            stock=availability.get('availabilityThreshold', 0),
            condition=item.get('condition', 'UNSPECIFIED').lower(),
            image_url=item.get('image', {}).get('imageUrl', ''),
            seller_id=seller.get('username', ''),
            category=item.get('categoryPath', 'general').lower()
        )
