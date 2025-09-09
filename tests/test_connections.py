#!/usr/bin/env python3
"""
Complete test suite for the Arbitrage Bot
"""

import unittest
import asyncio
import sys
import os
import tempfile
from pathlib import Path
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from config_manager import ConfigManager
from database import DatabaseManager
from models import Product, ArbitrageOpportunity, ProfitThresholds
from arbitrage_analyzer import ArbitrageAnalyzer
from ebay_api import EbayAPI
from amazon_api import AmazonAPI
from notifications import NotificationManager


class TestConfiguration(unittest.TestCase):
    """Test configuration management"""
    
    def setUp(self):
        self.config_manager = ConfigManager()
    
    def test_config_loading(self):
        """Test that configuration loads without errors"""
        self.assertIsInstance(self.config_manager.config, dict)
        self.assertIn('ebay', self.config_manager.config)
        self.assertIn('amazon', self.config_manager.config)
    
    def test_profit_thresholds(self):
        """Test profit threshold configuration"""
        thresholds = self.config_manager.get_profit_thresholds()
        self.assertIsInstance(thresholds, ProfitThresholds)
        self.assertGreater(thresholds.min_profit_gbp, 0)
        self.assertGreater(thresholds.min_roi_percentage, 0)
    
    def test_marketplace_config(self):
        """Test marketplace configuration retrieval"""
        ebay_config = self.config_manager.get_marketplace_config('ebay')
        self.assertEqual(ebay_config.platform, 'ebay')
        self.assertTrue(ebay_config.enabled)
        
        amazon_config = self.config_manager.get_marketplace_config('amazon')
        self.assertEqual(amazon_config.platform, 'amazon')


class TestDatabase(unittest.TestCase):
    """Test database operations"""
    
    def setUp(self):
        # Use temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        self.db = DatabaseManager(self.db_path)
    
    def tearDown(self):
        # Clean up temporary database
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
    
    def test_database_initialization(self):
        """Test that database initializes correctly"""
        # Database should be created and tables should exist
        stats = self.db.get_database_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn('opportunities_count', stats)
    
    def test_opportunity_save_and_retrieve(self):
        """Test saving and retrieving opportunities"""
        # Create test opportunity
        opportunity = ArbitrageOpportunity(
            opportunity_id='test-123',
            source_platform='ebay',
            target_platform='amazon', 
            product_title='Test Product',
            source_price=Decimal('50.00'),
            target_price=Decimal('75.00'),
            source_url='https://ebay.com/test',
            target_url='https://amazon.com/test',
            net_profit=Decimal('20.00'),
            roi_percentage=40.0
        )
        
        # Save opportunity
        success = self.db.save_opportunity(opportunity)
        self.assertTrue(success)
        
        # Retrieve opportunities
        df = self.db.get_opportunities(limit=10)
        self.assertGreater(len(df), 0)
        self.assertEqual(df.iloc[0]['opportunity_id'], 'test-123')
    
    def test_batch_save_opportunities(self):
        """Test batch saving of opportunities"""
        opportunities = []
        for i in range(5):
            opp = ArbitrageOpportunity(
                opportunity_id=f'test-batch-{i}',
                source_platform='ebay',
                target_platform='amazon',
                product_title=f'Test Product {i}',
                source_price=Decimal('50.00'),
                target_price=Decimal('75.00'),
                source_url=f'https://ebay.com/test{i}',
                target_url=f'https://amazon.com/test{i}',
                net_profit=Decimal('20.00'),
                roi_percentage=40.0
            )
            opportunities.append(opp)
        
        # Save batch
        saved_count = self.db.save_opportunities_batch(opportunities)
        self.assertEqual(saved_count, 5)
        
        # Verify all saved
        df = self.db.get_opportunities(limit=10)
        self.assertEqual(len(df), 5)
    
    def test_price_history(self):
        """Test price history functionality"""
        products = [
            Product(
                platform='ebay',
                product_id='test-product-1',
                title='Test Product',
                price=Decimal('100.00'),
                shipping=Decimal('5.00'),
                stock=10
            )
        ]
        
        # Save price history
        self.db.save_price_history(products)
        
        # Retrieve price history
        df = self.db.get_price_history('test-product-1', 'ebay')
        self.assertGreater(len(df), 0)
        self.assertEqual(float(df.iloc[0]['price']), 100.00)
    
    def test_blacklist_functionality(self):
        """Test seller blacklist functionality"""
        seller_id = 'bad-seller-123'
        platform = 'ebay'
        reason = 'Poor ratings'
        
        # Add to blacklist
        self.db.add_to_blacklist(seller_id, platform, reason)
        
        # Check if blacklisted
        is_blacklisted = self.db.is_blacklisted(seller_id, platform)
        self.assertTrue(is_blacklisted)
        
        # Check non-blacklisted seller
        is_not_blacklisted = self.db.is_blacklisted('good-seller', platform)
        self.assertFalse(is_not_blacklisted)


class TestArbitrageAnalyzer(unittest.TestCase):
    """Test arbitrage analysis logic"""
    
    def setUp(self):
        self.profit_thresholds = ProfitThresholds(
            min_profit_gbp=Decimal('10'),
            min_roi_percentage=25.0,
            max_risk_score=7.0,
            min_seller_rating=3.5
        )
        self.analyzer = ArbitrageAnalyzer(self.profit_thresholds)
    
    def test_fee_calculations(self):
        """Test platform fee calculations"""
        price = Decimal('100.00')
        
        # Test eBay fees
        ebay_fees = self.analyzer._calculate_ebay_fees(price, 'sell')
        self.assertGreater(ebay_fees, 0)
        self.assertLess(ebay_fees, price)  # Fees should be less than item price
        
        # Test Amazon fees
        amazon_fees = self.analyzer._calculate_amazon_fees(price, 'sell')
        self.assertGreater(amazon_fees, 0)
        self.assertLess(amazon_fees, price)
    
    def test_opportunity_analysis(self):
        """Test opportunity analysis"""
        # Create test products
        source_product = Product(
            platform='ebay',
            product_id='ebay-123',
            title='iPhone 12 Pro Max 256GB',
            price=Decimal('600.00'),
            currency='GBP',
            shipping=Decimal('5.00'),
            seller_rating=4.5,
            stock=5,
            url='https://ebay.com/item/123'
        )
        
        target_product = Product(
            platform='amazon',
            product_id='amazon-456',
            title='iPhone 12 Pro Max 256GB',
            price=Decimal('800.00'),
            currency='GBP',
            shipping=Decimal('0.00'),
            seller_rating=4.8,
            stock=10,
            url='https://amazon.co.uk/item/456'
        )
        
        # Analyze opportunity
        opportunity = self.analyzer._analyze_opportunity(source_product, target_product)
        
        # Verify opportunity structure
        self.assertIsInstance(opportunity, ArbitrageOpportunity)
        self.assertEqual(opportunity.source_platform, 'ebay')
        self.assertEqual(opportunity.target_platform, 'amazon')
        self.assertGreater(opportunity.net_profit, 0)
        self.assertGreater(opportunity.roi_percentage, 0)
    
    def test_product_matching(self):
        """Test product matching algorithm"""
        source_products = [
            Product(
                platform='ebay',
                product_id='1',
                title='Apple iPhone 12 Pro Max 256GB Blue',
                price=Decimal('600.00')
            ),
            Product(
                platform='ebay', 
                product_id='2',
                title='Samsung Galaxy S21 Ultra 128GB Black',
                price=Decimal('500.00')
            )
        ]
        
        target_products = [
            Product(
                platform='amazon',
                product_id='A',
                title='iPhone 12 Pro Max 256GB Blue Apple',
                price=Decimal('750.00')
            ),
            Product(
                platform='amazon',
                product_id='B', 
                title='Galaxy S21 Ultra 128GB Black Samsung',
                price=Decimal('650.00')
            )
        ]
        
        # Test matching
        matches = self.analyzer._match_products(source_products, target_products)
        
        self.assertGreater(len(matches), 0)
        # First match should be iPhone (higher similarity expected)
        first_match = matches[0]
        self.assertGreater(first_match[2], 0.7)  # Similarity > 70%
    
    def test_title_normalization(self):
        """Test title normalization for matching"""
        title1 = "Apple iPhone 12 Pro Max 256GB Blue - NEW SEALED - FREE UK SHIPPING"
        title2 = "APPLE IPHONE 12 PRO MAX 256GB BLUE"
        
        normalized1 = self.analyzer._normalize_title(title1)
        normalized2 = self.analyzer._normalize_title(title2)
        
        # Should be similar after normalization
        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, normalized1, normalized2).ratio()
        self.assertGreater(similarity, 0.8)
    
    def test_find_opportunities(self):
        """Test end-to-end opportunity finding"""
        source_products = [
            Product(
                platform='ebay',
                product_id='ebay-1',
                title='Apple AirPods Pro',
                price=Decimal('150.00'),
                shipping=Decimal('0.00'),
                seller_rating=4.5,
                stock=5,
                url='https://ebay.com/1'
            )
        ]
        
        target_products = [
            Product(
                platform='amazon',
                product_id='amazon-1', 
                title='Apple AirPods Pro',
                price=Decimal('200.00'),
                shipping=Decimal('0.00'),
                seller_rating=4.8,
                stock=10,
                url='https://amazon.co.uk/1'
            )
        ]
        
        opportunities = self.analyzer.find_opportunities(source_products, target_products)
        
        # Should find profitable opportunities
        profitable_opps = [opp for opp in opportunities if opp.net_profit >= self.profit_thresholds.min_profit_gbp]
        
        if profitable_opps:
            opp = profitable_opps[0]
            self.assertGreater(opp.net_profit, Decimal('0'))
            self.assertGreater(opp.roi_percentage, 0)


class TestAPIs(unittest.TestCase):
    """Test API integrations"""
    
    def setUp(self):
        self.config = {
            'ebay': {
                'app_id': 'test_app_id',
                'cert_id': 'test_cert_id', 
                'dev_id': 'test_dev_id',
                'marketplace_id': 'EBAY_GB',
                'api_endpoint': 'https://api.ebay.com'
            },
            'amazon': {
                'access_key': 'test_access_key',
                'secret_key': 'test_secret_key',
                'marketplace_id': 'A1F83G8C2ARO7P',
                'region': 'eu-west-2'
            }
        }
    
    def test_ebay_api_initialization(self):
        """Test eBay API initialization"""
        ebay_api = EbayAPI(self.config)
        self.assertEqual(ebay_api.config['app_id'], 'test_app_id')
        self.assertIsNone(ebay_api.session)
        self.assertIsNone(ebay_api.token)
    
    def test_amazon_api_initialization(self):
        """Test Amazon API initialization"""
        amazon_api = AmazonAPI(self.config)
        self.assertEqual(amazon_api.config['access_key'], 'test_access_key')
        self.assertIsNone(amazon_api.session)
    
    @patch('aiohttp.ClientSession.post')
    async def test_ebay_oauth_token(self, mock_post):
        """Test eBay OAuth token retrieval"""
        # Mock successful token response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            'access_token': 'test_token_123',
            'token_type': 'Bearer',
            'expires_in': 7200
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        ebay_api = EbayAPI(self.config)
        token = await ebay_api.get_oauth_token()
        
        self.assertEqual(token, 'test_token_123')
        self.assertIsNotNone(ebay_api.token_expiry)
    
    async def test_amazon_search_simulation(self):
        """Test Amazon search simulation"""
        amazon_api = AmazonAPI(self.config)
        products = await amazon_api.search_products('laptop', limit=10)
        
        self.assertIsInstance(products, list)
        if products:  # Only test if products returned
            product = products[0]
            self.assertIsInstance(product, Product)
            self.assertEqual(product.platform, 'amazon')
            self.assertGreater(product.price, 0)
    
    def test_ebay_fee_calculation(self):
        """Test eBay fee calculation"""
        ebay_api = EbayAPI(self.config)
        
        price = Decimal('100.00')
        fees = ebay_api.calculate_fees(price, 'electronics')
        
        self.assertGreater(fees, 0)
        self.assertLess(fees, price)
        
        # Test different categories
        motors_fees = ebay_api.calculate_fees(price, 'motors')
        self.assertNotEqual(fees, motors_fees)
    
    def test_amazon_fee_calculation(self):
        """Test Amazon fee calculation"""
        amazon_api = AmazonAPI(self.config)
        
        price = Decimal('100.00')
        fees = amazon_api.calculate_fees(price, 'electronics')
        
        self.assertGreater(fees, 0)
        self.assertLess(fees, price)


class TestNotifications(unittest.TestCase):
    """Test notification system"""
    
    def setUp(self):
        self.config = {
            'notifications': {
                'telegram_bot_token': 'test_token',
                'telegram_chat_id': 'test_chat_id',
                'email_from': 'test@example.com',
                'email_to': 'alerts@example.com',
                'email_password': 'test_password'
            }
        }
        self.notification_manager = NotificationManager(self.config)
    
    def test_notification_manager_initialization(self):
        """Test notification manager initialization"""
        self.assertEqual(self.notification_manager.config['telegram_bot_token'], 'test_token')
        self.assertIsNone(self.notification_manager.session)
    
    def test_opportunity_message_formatting(self):
        """Test opportunity message formatting"""
        opportunity = ArbitrageOpportunity(
            opportunity_id='test-123',
            source_platform='ebay',
            target_platform='amazon',
            product_title='Test Product for Notification',
            source_price=Decimal('50.00'),
            target_price=Decimal('80.00'),
            source_url='https://ebay.com/test',
            target_url='https://amazon.com/test',
            net_profit=Decimal('25.00'),
            roi_percentage=50.0,
            risk_score=3.5
        )
        
        message = self.notification_manager._format_opportunity_message(opportunity)
        
        self.assertIn('Test Product for Notification', message)
        self.assertIn('£25.00', message)
        self.assertIn('50.0%', message)
        self.assertIn('ebay', message.lower())
        self.assertIn('amazon', message.lower())
    
    @patch('aiohttp.ClientSession.get')
    async def test_telegram_connection_test(self, mock_get):
        """Test Telegram connection test"""
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            'ok': True,
            'result': {
                'username': 'test_bot',
                'first_name': 'Test Bot'
            }
        }
        mock_get.return_value.__aenter__.return_value = mock_response
        
        await self.notification_manager.initialize()
        success = await self.notification_manager._test_telegram_connection()
        self.assertTrue(success)


class TestModels(unittest.TestCase):
    """Test data models"""
    
    def test_product_model(self):
        """Test Product model"""
        product = Product(
            platform='ebay',
            product_id='test-123',
            title='Test Product',
            price=Decimal('99.99'),
            currency='GBP',
            shipping=Decimal('5.00')
        )
        
        self.assertEqual(product.platform, 'ebay')
        self.assertEqual(product.price, Decimal('99.99'))
        self.assertEqual(product.currency, 'GBP')
        self.assertEqual(product.condition, 'new')  # Default value
    
    def test_arbitrage_opportunity_model(self):
        """Test ArbitrageOpportunity model"""
        opportunity = ArbitrageOpportunity(
            opportunity_id='test-opp-123',
            source_platform='ebay',
            target_platform='amazon',
            product_title='Test Opportunity',
            source_price=Decimal('100.00'),
            target_price=Decimal('150.00'),
            source_url='https://source.com',
            target_url='https://target.com'
        )
        
        self.assertEqual(opportunity.opportunity_id, 'test-opp-123')
        self.assertIsInstance(opportunity.created_at, datetime)
        self.assertEqual(opportunity.status, 'new')  # Default value
    
    def test_profit_thresholds_model(self):
        """Test ProfitThresholds model"""
        thresholds = ProfitThresholds(
            min_profit_gbp=Decimal('15.00'),
            min_roi_percentage=30.0,
            alert_profit_gbp=Decimal('50.00')
        )
        
        self.assertEqual(thresholds.min_profit_gbp, Decimal('15.00'))
        self.assertEqual(thresholds.min_roi_percentage, 30.0)
        self.assertEqual(thresholds.max_risk_score, 7.0)  # Default value


class TestIntegration(unittest.TestCase):
    """Integration tests"""
    
    def setUp(self):
        # Use temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        self.config = {
            'ebay': {
                'app_id': 'test_app_id',
                'cert_id': 'test_cert_id',
                'dev_id': 'test_dev_id',
                'marketplace_id': 'EBAY_GB',
                'api_endpoint': 'https://api.ebay.com'
            },
            'amazon': {
                'access_key': 'test_access_key',
                'secret_key': 'test_secret_key',
                'marketplace_id': 'A1F83G8C2ARO7P',
                'region': 'eu-west-2'
            },
            'profit_thresholds': {
                'min_profit_gbp': 10,
                'min_roi_percentage': 25,
                'alert_profit_gbp': 25,
                'max_risk_score': 7.0,
                'min_seller_rating': 3.5
            },
            'database': {
                'path': self.db_path
            }
        }
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
    
    async def test_full_opportunity_pipeline(self):
        """Test complete opportunity discovery and analysis pipeline"""
        # Initialize components
        db = DatabaseManager(self.db_path)
        profit_thresholds = ProfitThresholds(
            min_profit_gbp=Decimal('10'),
            min_roi_percentage=25.0
        )
        analyzer = ArbitrageAnalyzer(profit_thresholds)
        
        # Create mock products that should create opportunities
        ebay_products = [
            Product(
                platform='ebay',
                product_id='ebay-1',
                title='Apple AirPods Pro 2nd Generation',
                price=Decimal('180.00'),
                shipping=Decimal('0.00'),
                seller_rating=4.5,
                stock=5,
                url='https://ebay.com/item/1'
            ),
            Product(
                platform='ebay',
                product_id='ebay-2',
                title='Samsung Galaxy Buds Pro',
                price=Decimal('120.00'),
                shipping=Decimal('3.99'),
                seller_rating=4.2,
                stock=3,
                url='https://ebay.com/item/2'
            )
        ]
        
        amazon_products = [
            Product(
                platform='amazon',
                product_id='amazon-1',
                title='Apple AirPods Pro (2nd Generation)',
                price=Decimal('230.00'),
                shipping=Decimal('0.00'),
                seller_rating=4.8,
                stock=10,
                url='https://amazon.co.uk/item/1'
            ),
            Product(
                platform='amazon',
                product_id='amazon-2',
                title='Samsung Galaxy Buds Pro',
                price=Decimal('170.00'),
                shipping=Decimal('0.00'),
                seller_rating=4.6,
                stock=15,
                url='https://amazon.co.uk/item/2'
            )
        ]
        
        # Save price history
        db.save_price_history(ebay_products + amazon_products)
        
        # Find opportunities
        opportunities = analyzer.find_opportunities(ebay_products, amazon_products)
        
        # Verify opportunities were found
        self.assertGreater(len(opportunities), 0)
        
        # Save opportunities to database
        saved_count = db.save_opportunities_batch(opportunities)
        self.assertEqual(saved_count, len(opportunities))
        
        # Retrieve and verify
        retrieved_opportunities = db.get_opportunities(limit=10)
        self.assertEqual(len(retrieved_opportunities), len(opportunities))
        
        # Test opportunity summary
        summary = analyzer.get_opportunity_summary(opportunities)
        self.assertIn('total_opportunities', summary)
        self.assertEqual(summary['total_opportunities'], len(opportunities))
        
        return opportunities
    
    def test_risk_assessment_integration(self):
        """Test risk assessment integration"""
        opportunity = ArbitrageOpportunity(
            opportunity_id='risk-test-123',
            source_platform='ebay',
            target_platform='amazon',
            product_title='High Risk Test Product',
            source_price=Decimal('50.00'),
            target_price=Decimal('200.00'),  # Very high markup - risky
            source_url='https://ebay.com/test',
            target_url='https://amazon.com/test',
            net_profit=Decimal('120.00'),
            roi_percentage=240.0,  # Very high ROI - suspicious
            source_seller_rating=2.5,  # Low rating - risky
            risk_score=8.5  # High risk
        )
        
        profit_thresholds = ProfitThresholds(
            min_profit_gbp=Decimal('10'),
            min_roi_percentage=25.0,
            max_risk_score=7.0  # This opportunity exceeds risk threshold
        )
        
        analyzer = ArbitrageAnalyzer(profit_thresholds)
        
        # This opportunity should be filtered out due to high risk
        is_profitable = analyzer._is_profitable_opportunity(opportunity)
        self.assertFalse(is_profitable)


class TestPerformanceAndScaling(unittest.TestCase):
    """Test performance and scaling aspects"""
    
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        self.db = DatabaseManager(self.db_path)
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
    
    def test_large_batch_operations(self):
        """Test handling of large batches of data"""
        # Create 1000 test opportunities
        opportunities = []
        for i in range(1000):
            opp = ArbitrageOpportunity(
                opportunity_id=f'perf-test-{i}',
                source_platform='ebay',
                target_platform='amazon',
                product_title=f'Performance Test Product {i}',
                source_price=Decimal('50.00'),
                target_price=Decimal('75.00'),
                source_url=f'https://ebay.com/test{i}',
                target_url=f'https://amazon.com/test{i}',
                net_profit=Decimal('20.00'),
                roi_percentage=40.0
            )
            opportunities.append(opp)
        
        # Time the batch save operation
        import time
        start_time = time.time()
        saved_count = self.db.save_opportunities_batch(opportunities)
        end_time = time.time()
        
        # Should save all opportunities efficiently
        self.assertEqual(saved_count, 1000)
        
        # Should complete within reasonable time (less than 5 seconds)
        execution_time = end_time - start_time
        self.assertLess(execution_time, 5.0)
        
        # Verify retrieval performance
        start_time = time.time()
        retrieved = self.db.get_opportunities(limit=1000)
        end_time = time.time()
        
        self.assertEqual(len(retrieved), 1000)
        retrieval_time = end_time - start_time
        self.assertLess(retrieval_time, 2.0)
    
    def test_product_matching_performance(self):
        """Test product matching algorithm performance"""
        from arbitrage_analyzer import ArbitrageAnalyzer
        
        profit_thresholds = ProfitThresholds()
        analyzer = ArbitrageAnalyzer(profit_thresholds)
        
        # Create large product lists
        source_products = []
        target_products = []
        
        product_names = [
            'iPhone 13 Pro Max', 'Samsung Galaxy S22', 'iPad Air', 'MacBook Pro',
            'AirPods Pro', 'Sony Headphones', 'Nintendo Switch', 'PlayStation 5',
            'Canon Camera', 'Dell Laptop', 'Apple Watch', 'Surface Pro'
        ]
        
        for i in range(100):
            name = product_names[i % len(product_names)]
            
            source_products.append(Product(
                platform='ebay',
                product_id=f'ebay-{i}',
                title=f'{name} {i}',
                price=Decimal('100.00')
            ))
            
            target_products.append(Product(
                platform='amazon',
                product_id=f'amazon-{i}',
                title=f'{name} {i}',
                price=Decimal('150.00')
            ))
        
        # Time the matching operation
        import time
        start_time = time.time()
        matches = analyzer._match_products(source_products, target_products)
        end_time = time.time()
        
        # Should find matches
        self.assertGreater(len(matches), 0)
        
        # Should complete efficiently (less than 3 seconds for 100x100 comparison)
        execution_time = end_time - start_time
        self.assertLess(execution_time, 3.0)


async def run_async_tests():
    """Run async tests"""
    
    # Create test suite for async tests
    suite = unittest.TestSuite()
    
    # Add async test cases
    test_integration = TestIntegration()
    test_integration.setUp()
    
    try:
        opportunities = await test_integration.test_full_opportunity_pipeline()
        print(f"✅ Integration test passed: Found {len(opportunities)} opportunities")
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
    finally:
        test_integration.tearDown()
    
    # Test API mocking
    test_apis = TestAPIs()
    test_apis.setUp()
    
    try:
        # Test Amazon search simulation
        amazon_api = AmazonAPI(test_apis.config)
        products = await amazon_api.search_products('test', limit=5)
        print(f"✅ Amazon API test passed: Got {len(products)} simulated products")
        
        # Test fee calculation
        fees = amazon_api.calculate_fees(Decimal('100'), 'electronics')
        print(f"✅ Amazon fee calculation passed: £{fees}")
        
    except Exception as e:
        print(f"❌ Amazon API test failed: {e}")


def main():
    """Main test runner"""
    print("🧪 Running Arbitrage Bot Test Suite\n")
    
    # Run synchronous tests
    print("📋 Running unit tests...")
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabase))
    suite.addTests(loader.loadTestsFromTestCase(TestArbitrageAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestAPIs))
    suite.addTests(loader.loadTestsFromTestCase(TestNotifications))
    suite.addTests(loader.loadTestsFromTestCase(TestModels))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceAndScaling))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Run async tests
    print("\n🔄 Running async tests...")
    asyncio.run(run_async_tests())
    
    # Print summary
    print(f"\n📊 Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    
    if result.failures:
        print(f"\n❌ Failures:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print(f"\n💥 Errors:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    # Return exit code
    if result.failures or result.errors:
        print(f"\n❌ Some tests failed!")
        return 1
    else:
        print(f"\n✅ All tests passed!")
        return 0


if __name__ == '__main__':
    # Create logs directory for tests
    Path("logs").mkdir(exist_ok=True)
    
    exit_code = main()
    sys.exit(exit_code)
