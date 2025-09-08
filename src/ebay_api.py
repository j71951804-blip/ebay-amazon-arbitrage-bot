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
    
    async def get_oauth_token(self):
        """Get OAuth token for eBay API"""
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token
        
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
        
        async with self.session.post(
            f"{self.config['api_endpoint']}/identity/v1/oauth2/token",
            headers=headers,
            data=data
        ) as response:
            if response.status == 200:
                token_data = await response.json()
                self.token = token_data['access_token']
                self.token_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])
                return self.token
            else:
                logger.error(f"Failed to get eBay token: {response.status}")
                return None
    
    async def search_products(self, keyword, limit=50):
        """Search for products on eBay"""
        await self.init_session()
        token = await self.get_oauth_token()
        
        if not token:
            return []
        
        headers = {
            'Authorization': f'Bearer {token}',
            'X-EBAY-C-MARKETPLACE-ID': self.config['marketplace_id']
        }
        
        params = {
            'q': keyword,
            'limit': limit,
            'filter': 'conditions:{NEW},deliveryCountry:GB'
        }
        
        try:
            async with self.session.get(
                f"{self.config['api_endpoint']}/buy/browse/v1/item_summary/search",
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return self.parse_ebay_results(data.get('itemSummaries', []))
                else:
                    logger.error(f"eBay search failed: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"eBay API error: {e}")
            return []
    
    def parse_ebay_results(self, items):
        """Parse eBay search results"""
        products = []
        for item in items:
            try:
                price = item.get('price', {})
                shipping = item.get('shippingOptions', [{}])[0].get('shippingCost', {})
                
                product = {
                    'platform': 'ebay',
                    'product_id': item.get('itemId'),
                    'title': item.get('title'),
                    'price': Decimal(price.get('value', '0')),
                    'currency': price.get('currency', 'GBP'),
                    'shipping': Decimal(shipping.get('value', '0')),
                    'url': item.get('itemWebUrl'),
                    'seller_rating': self.extract_seller_rating(item),
                    'stock': item.get('estimatedAvailabilities', [{}])[0].get('availabilityThreshold', 0),
                    'condition': item.get('condition'),
                    'image_url': item.get('image', {}).get('imageUrl')
                }
                products.append(product)
            except Exception as e:
                logger.warning(f"Error parsing eBay item: {e}")
                continue
        
        return products
    
    def extract_seller_rating(self, item):
        """Extract seller rating from item data"""
        seller = item.get('seller', {})
        feedback = seller.get('feedbackPercentage')
        if feedback:
            return float(feedback) / 100 * 5  # Convert to 5-star scale
        return 0.0
    
    def calculate_fees(self, price, category='general'):
        """Calculate eBay selling fees"""
        # Basic eBay UK fees (simplified)
        listing_fee = Decimal('0.35')  # First 1000 listings free
        final_value_fee = price * Decimal('0.129')  # 12.9% for most categories
        payment_processing = price * Decimal('0.03') + Decimal('0.30')  # 3% + £0.30
        
        return listing_fee + final_value_fee + payment_processing
