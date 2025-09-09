#!/usr/bin/env python3
"""
Quick test script to verify eBay API credentials
"""
import asyncio
import sys
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent / 'src'))

from config_manager import ConfigManager
from ebay_api import EbayAPI

async def test_ebay_connection():
    """Test eBay API connection"""
    print("🔗 Testing eBay API Connection...")
    
    try:
        # Load configuration
        config = ConfigManager()
        print(f"✓ Configuration loaded")
        
        # Check if credentials are configured
        ebay_config = config.config.get('ebay', {})
        if not ebay_config.get('app_id') or ebay_config.get('app_id') == 'YOUR_EBAY_APP_ID_HERE':
            print("❌ eBay credentials not configured!")
            print("Please update config/config.json with your actual eBay API credentials")
            return False
        
        # Initialize eBay API
        ebay_api = EbayAPI(config.config)
        
        # Test OAuth token
        print("🔑 Testing OAuth token...")
        token = await ebay_api.get_oauth_token()
        
        if token:
            print(f"✅ OAuth token obtained successfully!")
            print(f"Token: {token[:20]}...")
            
            # Test a simple search
            print("🔍 Testing product search...")
            products = await ebay_api.search_products("iphone", limit=5)
            
            if products:
                print(f"✅ Found {len(products)} products!")
                for i, product in enumerate(products[:3], 1):
                    print(f"  {i}. {product.title[:50]}... - £{product.price}")
            else:
                print("⚠️  No products found (this might be normal)")
            
            return True
        else:
            print("❌ Failed to get OAuth token!")
            print("Check your eBay API credentials in config/config.json")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        if 'ebay_api' in locals():
            await ebay_api.close_session()

async def main():
    success = await test_ebay_connection()
    
    if success:
        print("\n🎉 eBay API connection successful!")
        print("\n📋 Next steps:")
        print("  1. Set up Amazon API credentials (optional)")
        print("  2. Configure notifications (optional)")
        print("  3. Run your first scan: python src/main.py scan electronics")
    else:
        print("\n❌ eBay API connection failed!")
        print("\n🔧 Troubleshooting:")
        print("  1. Double-check your eBay API credentials")
        print("  2. Make sure your eBay app is approved")
        print("  3. Check if you're using the correct endpoint")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
