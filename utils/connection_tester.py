import asyncio
import aiohttp
import logging
import time
from typing import Dict, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionTester:
    """Tests API connections and network connectivity"""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_ebay_api(self, config: Dict) -> Dict:
        """Test eBay API connection"""
        result = {
            'platform': 'eBay',
            'status': 'failed',
            'response_time': None,
            'error': None,
            'details': {}
        }
        
        try:
            start_time = time.time()
            
            # Test OAuth endpoint
            credentials = f"{config['app_id']}:{config['cert_id']}"
            encoded_credentials = __import__('base64').b64encode(credentials.encode()).decode()
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {encoded_credentials}'
            }
            
            data = {
                'grant_type': 'client_credentials',
                'scope': 'https://api.ebay.com/oauth/api_scope'
            }
            
            async with self.session.post(
                f"{config['api_endpoint']}/identity/v1/oauth2/token",
                headers=headers,
                data=data
            ) as response:
                response_time = time.time() - start_time
                result['response_time'] = response_time
                
                if response
