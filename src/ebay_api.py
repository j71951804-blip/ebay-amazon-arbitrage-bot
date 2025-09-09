import aiohttp
import base64
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional

from models import Product

logger = logging.getLogger(__name__)


class EbayAPI:
    """eBay API integration"""
    
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
    
    async def search_products(self, keyword: str, limit: int = 50, condition: str = 'NEW') -> List[Product]:
        """Search for products on eBay"""
        await self.init_session()
        token = await self.get_oauth_token()
        
        if not token:
            logger.error("No valid eBay token available")
            return []
        
        headers = {
            'Authorization': f'Bearer {token}',
            'X-EBAY-C-MARKETPLACE-ID': self.config['marketplace_id']
        }
        
        # Build filters
        filters = [f'conditions:{{{condition}}}', 'deliveryCountry:GB']
        if 'buyItNowAvailable:true' not in filters:
            filters.append('buyItNowAvailable:true')  # Only Buy It Now listings
        
        params = {
            'q': keyword,
            'limit': min(limit, 200),  # eBay API limit
            'filter': ','.join(filters),
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
                    logger.info(f"Found {len(products)} eBay products for '{keyword}'")
                    return products
                else:
                    error_text = await response.text()
                    logger.error(f"eBay search failed: {response.status} - {error_text}")
                    return []
        except Exception as e:
            logger.error(f"eBay API error: {e}")
            return []
    
    def parse_ebay_results(self, items: List[Dict]) -> List[Product]:
        """Parse eBay search results"""
        products = []
        
        for item in items:
            try:
                # Extract price information
                price_info = item.get('price', {})
                price_value = price_info.get('value', '0')
                price_currency = price_info.get('currency', 'GBP')
                
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
                
                # Extract seller information
                seller = item.get('seller', {})
                seller_id = seller.get('username', '')
                seller_rating = self.extract_seller_rating(seller)
                
                # Extract image
                image_info = item.get('image', {})
                image_url = image_info.get('imageUrl', '') if image_info else ''
                
                # Extract category for fee calculation
                categories = item.get('categories', [])
                category = categories[0].get('categoryName', 'general') if categories else 'general'
                
                product = Product(
                    platform='ebay',
                    product_id=item.get('itemId', ''),
                    title=item.get('title', ''),
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
                
                # Basic validation
                if product.price > 0 and product.title:
                    products.append(product)
                
            except (ValueError, KeyError, TypeError) as e:
                logger.warning(f"Error parsing eBay item: {e}")
                continue
        
        return products
    
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
