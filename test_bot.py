#!/usr/bin/env python3
"""
Simple test runner for the Arbitrage Bot
Save this as test_bot.py in the project root directory
"""

import sys
import os
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).parent
src_dir = current_dir / 'src'
sys.path.insert(0, str(src_dir))

print("🧪 Testing Arbitrage Bot")
print("=" * 50)

def test_imports():
    """Test if we can import all modules"""
    print("\n📦 Testing Imports...")
    
    try:
        print("  ✓ Testing basic imports...")
        import json
        import sqlite3
        import decimal
        print("    ✓ Standard library modules OK")
        
        print("  ✓ Testing external packages...")
        try:
            import pandas as pd
            print("    ✓ pandas OK")
        except ImportError as e:
            print(f"    ❌ pandas: {e}")
            return False
            
        try:
            import aiohttp
            print("    ✓ aiohttp OK")
        except ImportError as e:
            print(f"    ❌ aiohttp: {e}")
            return False
            
        try:
            import numpy as np
            print("    ✓ numpy OK")
        except ImportError as e:
            print(f"    ❌ numpy: {e}")
            return False
        
        print("  ✓ Testing project modules...")
        try:
            from models import Product, ArbitrageOpportunity
            print("    ✓ models OK")
        except ImportError as e:
            print(f"    ❌ models: {e}")
            return False
            
        try:
            from config_manager import ConfigManager
            print("    ✓ config_manager OK")
        except ImportError as e:
            print(f"    ❌ config_manager: {e}")
            return False
            
        try:
            from database import DatabaseManager
            print("    ✓ database OK")
        except ImportError as e:
            print(f"    ❌ database: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"    ❌ Import test failed: {e}")
        return False

def test_config():
    """Test configuration"""
    print("\n⚙️  Testing Configuration...")
    
    try:
        from config_manager import ConfigManager
        
        # Create directories
        config_dir = Path('config')
        config_dir.mkdir(exist_ok=True)
        
        # Check if config exists
        config_file = config_dir / 'config.json'
        if not config_file.exists():
            print("    ⚠️  config.json not found, creating from example...")
            example_file = config_dir / 'config.example.json'
            if example_file.exists():
                import shutil
                shutil.copy(example_file, config_file)
                print(f"    ✓ Copied {example_file} to {config_file}")
            else:
                # Create basic config
                basic_config = {
                    "ebay": {
                        "app_id": "YOUR_EBAY_APP_ID",
                        "cert_id": "YOUR_EBAY_CERT_ID",
                        "dev_id": "YOUR_EBAY_DEV_ID",
                        "marketplace_id": "EBAY_GB",
                        "api_endpoint": "https://api.ebay.com"
                    },
                    "amazon": {
                        "access_key": "YOUR_AWS_ACCESS_KEY",
                        "secret_key": "YOUR_AWS_SECRET_KEY",
                        "marketplace_id": "A1F83G8C2ARO7P",
                        "region": "eu-west-2"
                    },
                    "profit_thresholds": {
                        "min_profit_gbp": 10,
                        "min_roi_percentage": 25,
                        "alert_profit_gbp": 25,
                        "max_risk_score": 7.0,
                        "min_seller_rating": 3.5
                    },
                    "notifications": {
                        "telegram_bot_token": "",
                        "telegram_chat_id": "",
                        "email_from": "",
                        "email_to": "",
                        "email_password": ""
                    },
                    "database": {
                        "path": "./arbitrage.db"
                    }
                }
                
                import json
                with open(config_file, 'w') as f:
                    json.dump(basic_config, f, indent=2)
                print(f"    ✓ Created basic {config_file}")
        
        # Test loading config
        config_manager = ConfigManager()
        print("    ✓ Configuration loaded successfully")
        
        # Check required sections
        required = ['ebay', 'amazon', 'profit_thresholds']
        for section in required:
            if section in config_manager.config:
                print(f"    ✓ Section '{section}' found")
            else:
                print(f"    ❌ Section '{section}' missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"    ❌ Configuration test failed: {e}")
        return False

def test_database():
    """Test database functionality"""
    print("\n💾 Testing Database...")
    
    try:
        from database import DatabaseManager
        from models import ArbitrageOpportunity
        from decimal import Decimal
        import tempfile
        import os
        
        # Use temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            test_db_path = tmp.name
        
        print(f"    ✓ Using test database: {test_db_path}")
        
        # Initialize database
        db = DatabaseManager(test_db_path)
        print("    ✓ Database initialized")
        
        # Test saving opportunity
        test_opp = ArbitrageOpportunity(
            opportunity_id='test-123',
            source_platform='ebay',
            target_platform='amazon',
            product_title='Test Product',
            source_price=Decimal('50.00'),
            target_price=Decimal('75.00'),
            source_url='https://test.com',
            target_url='https://test.com',
            net_profit=Decimal('20.00'),
            roi_percentage=40.0
        )
        
        success = db.save_opportunity(test_opp)
        if success:
            print("    ✓ Test opportunity saved")
        else:
            print("    ❌ Failed to save test opportunity")
            return False
        
        # Test retrieval
        df = db.get_opportunities(limit=1)
        if len(df) > 0:
            print(f"    ✓ Retrieved {len(df)} opportunity")
        else:
            print("    ❌ Failed to retrieve opportunities")
            return False
        
        # Cleanup
        os.unlink(test_db_path)
        print("    ✓ Test database cleaned up")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Database test failed: {e}")
        return False

def test_analysis():
    """Test analysis functionality"""
    print("\n🔍 Testing Analysis...")
    
    try:
        from arbitrage_analyzer import ArbitrageAnalyzer
        from models import Product, ProfitThresholds
        from decimal import Decimal
        
        # Create analyzer
        thresholds = ProfitThresholds(
            min_profit_gbp=Decimal('10'),
            min_roi_percentage=25.0
        )
        analyzer = ArbitrageAnalyzer(thresholds)
        print("    ✓ Analyzer created")
        
        # Test fee calculation
        ebay_fees = analyzer._calculate_ebay_fees(Decimal('100'), 'sell')
        if ebay_fees > 0:
            print(f"    ✓ eBay fee calculation: £{ebay_fees}")
        else:
            print("    ❌ eBay fee calculation failed")
            return False
        
        # Test product matching
        source = [Product(
            platform='ebay',
            product_id='test-1',
            title='Apple iPhone 13',
            price=Decimal('500')
        )]
        
        target = [Product(
            platform='amazon',
            product_id='test-2',
            title='iPhone 13 Apple',
            price=Decimal('600')
        )]
        
        opportunities = analyzer.find_opportunities(source, target)
        if len(opportunities) > 0:
            print(f"    ✓ Found {len(opportunities)} test opportunities")
            opp = opportunities[0]
            print(f"      Net profit: £{opp.net_profit}")
            print(f"      ROI: {opp.roi_percentage:.1f}%")
        else:
            print("    ⚠️  No opportunities found (this is normal for test data)")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Analysis test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Starting basic functionality tests...\n")
    
    # Create necessary directories
    for dirname in ['logs', 'config', 'backups', 'reports']:
        Path(dirname).mkdir(exist_ok=True)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Database", test_database),
        ("Analysis", test_analysis),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} test PASSED")
            else:
                print(f"❌ {test_name} test FAILED")
        except Exception as e:
            print(f"❌ {test_name} test ERROR: {e}")
    
    # Summary
    print("\n" + "="*50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All basic tests passed!")
        print("\n📋 Next steps:")
        print("  1. Configure your eBay/Amazon API credentials in config/config.json")
        print("  2. Try: python src/main.py scan electronics")
        print("  3. Check logs/arbitrage_bot.log for detailed output")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        print("\n🔧 Common fixes:")
        print("  - Make sure all dependencies are installed: pip install -r requirements.txt")
        print("  - Check file permissions")
        print("  - Ensure you're in the project root directory")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
