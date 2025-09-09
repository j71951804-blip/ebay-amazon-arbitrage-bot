#!/usr/bin/env python3
"""
Basic tests for the Arbitrage Bot
"""

import unittest
import asyncio
import sys
import os
from pathlib import Path
from decimal import Decimal

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from config_manager import ConfigManager
from database import DatabaseManager
from models import Product, ArbitrageOpportunity, ProfitThresholds
from arbitrage_analyzer import ArbitrageAnalyzer


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


class TestDatabase(unittest.TestCase):
    """Test database operations"""
    
    def setUp(self):
        # Use test database
        self.db_path = 'test_arbitrage.db'
        self.db = DatabaseManager(self.db_path)
    
    def tearDown(self):
        # Clean up test database
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


class TestArbitrageAnalyzer(unittest.TestCase):
    """Test arbitrage analysis logic"""
    
    def setUp(self):
        self.profit_thresholds = ProfitThresholds(
            min_profit_gbp=Decimal('10'),
            min_roi_percentage=25.0
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
            stock=5
        )
        
        target_product = Product(
            platform='amazon',
            product_id='amazon-456',
            title='iPhone 12 Pro Max 256GB',
            price=Decimal('800.00'),
            currency='GBP',
            shipping=Decimal('0.00'),
