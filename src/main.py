#!/usr/bin/env python3
"""
Arbitrage Bot - Main Application
Finds arbitrage opportunities between eBay and Amazon
"""

import asyncio
import logging
import sys
import signal
from pathlib import Path
from typing import List
from datetime import datetime
import time

# Add src directory to path
sys.path.append(str(Path(__file__).parent))

from config_manager import ConfigManager
from database import DatabaseManager
from ebay_api import EbayAPI
from amazon_api import AmazonAPI
from arbitrage_analyzer import ArbitrageAnalyzer
from notifications import NotificationManager
from models import Product, ArbitrageOpportunity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/arbitrage_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class ArbitrageBot:
    """Main arbitrage bot application"""
    
    def __init__(self):
        self.config = ConfigManager()
        self.database = DatabaseManager(self.config.get('database', {}).get('path', 'arbitrage.db'))
        
        # Initialize APIs
        self.ebay_api = EbayAPI(self.config.config)
        self.amazon_api = AmazonAPI(self.config.config)
        
        # Initialize analyzer and notifications
        self.analyzer = ArbitrageAnalyzer(self.config.get_profit_thresholds())
        self.notifications = NotificationManager(self.config.config)
        
        # Control flags
        self.running = False
        self.search_interval = self.config.get('search', {}).get('search_interval_minutes', 30) * 60
        
    async def initialize(self):
        """Initialize all components"""
        try:
            logger.info("Initializing Arbitrage Bot...")
            
            # Test API connections
            await self._test_api_connections()
            
            # Initialize notification system
            await self.notifications.initialize()
            
            logger.info("Bot initialization complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            return False
    
    async def _test_api_connections(self):
        """Test API connections"""
        logger.info("Testing API connections...")
        
        try:
            # Test eBay API
            token = await self.ebay_api.get_oauth_token()
            if token:
                logger.info("eBay API connection successful")
            else:
                logger.warning("eBay API connection failed")
            
            # Test Amazon API (mock for now)
            await self.amazon_api.init_session()
            logger.info("Amazon API connection initialized")
            
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            raise
    
    async def run_single_scan(self, keywords: List[str] = None) -> List[ArbitrageOpportunity]:
        """Run a single scan for opportunities"""
        if not keywords:
            keywords = self.config.get('search', {}).get('keywords', ['electronics'])
        
        logger.info(f"Starting scan for keywords: {keywords}")
        all_opportunities = []
        
        for keyword in keywords:
            try:
                opportunities = await self._scan_keyword(keyword)
                all_opportunities.extend(opportunities)
                
                # Small delay between keywords to avoid rate limiting
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error scanning keyword '{keyword}': {e}")
                continue
        
        # Save opportunities to database
        if all_opportunities:
            saved_count = self.database.save_opportunities_batch(all_opportunities)
            logger.info(f"Saved {saved_count} opportunities to database")
            
            # Send notifications for high-profit opportunities
            await self._send_opportunity_notifications(all_opportunities)
        
        return all_opportunities
    
    async def _scan_keyword(self, keyword: str) -> List[ArbitrageOpportunity]:
        """Scan a single keyword across platforms"""
        logger.info(f"Scanning keyword: {keyword}")
        
        try:
            # Search both platforms concurrently
            ebay_task = self.ebay_api.search_products(keyword, limit=50)
            amazon_task = self.amazon_api.search_products(keyword, limit=50)
            
            ebay_products, amazon_products = await asyncio.gather(
                ebay_task, amazon_task, return_exceptions=True
            )
            
            # Handle exceptions from tasks
            if isinstance(ebay_products, Exception):
                logger.error(f"eBay search failed for '{keyword}': {ebay_products}")
                ebay_products = []
            
            if isinstance(amazon_products, Exception):
                logger.error(f"Amazon search failed for '{keyword}': {amazon_products}")
                amazon_products = []
            
            logger.info(f"Found {len(ebay_products)} eBay products, {len(amazon_products)} Amazon products")
            
            # Save price history
            all_products = ebay_products + amazon_products
            if all_products:
                self.database.save_price_history(all_products)
            
            # Find opportunities in both directions
            opportunities = []
            
            # eBay -> Amazon arbitrage
            ebay_to_amazon = self.analyzer.find_opportunities(ebay_products, amazon_products)
            opportunities.extend(ebay_to_amazon)
            
            # Amazon -> eBay arbitrage
            amazon_to_ebay = self.analyzer.find_opportunities(amazon_products, ebay_products)
            opportunities.extend(amazon_to_ebay)
            
            # Update keyword statistics
            total_results = len(ebay_products) + len(amazon_products)
            avg_profit = sum(opp.net_profit for opp in opportunities) / len(opportunities) if opportunities else 0
            
            self.database.update_search_keyword_stats(
                keyword, 'both', total_results, len(opportunities), float(avg_profit)
            )
            
            logger.info(f"Found {len(opportunities)} opportunities for keyword '{keyword}'")
            return opportunities
            
        except Exception as e:
            logger.error(f"Error scanning keyword '{keyword}': {e}")
            return []
    
    async def _send_opportunity_notifications(self, opportunities: List[ArbitrageOpportunity]):
        """Send notifications for high-profit opportunities"""
        profit_threshold = self.config.get_profit_thresholds().alert_profit_gbp
        
        high_profit_opportunities = [
            opp for opp in opportunities 
            if opp.net_profit >= profit_threshold
        ]
        
        if high_profit_opportunities:
            logger.info(f"Sending notifications for {len(high_profit_opportunities)} high-profit opportunities")
            
            for opportunity in high_profit_opportunities:
                await self.notifications.send_opportunity_alert(opportunity)
                
                # Small delay between notifications
                await asyncio.sleep(1)
    
    async def run_continuous(self):
        """Run bot continuously"""
        self.running = True
        logger.info(f"Starting continuous mode (scan interval: {self.search_interval}s)")
        
        keywords = self.config.get('search', {}).get('keywords', ['electronics'])
        
        while self.running:
            try:
                start_time = time.time()
                
                # Run scan
                opportunities = await self.run_single_scan(keywords)
                
                # Log summary
                if opportunities:
                    summary = self.analyzer.get_opportunity_summary(opportunities)
                    logger.info(f"Scan complete: {summary['total_opportunities']} opportunities, "
                               f"£{summary['total_potential_profit']:.2f} potential profit")
                else:
                    logger.info("Scan complete: No opportunities found")
                
                # Cleanup old records periodically
                if datetime.now().hour == 2:  # 2 AM cleanup
                    self.database.cleanup_old_records()
                
                # Calculate sleep time
                elapsed_time = time.time() - start_time
                sleep_time = max(0, self.search_interval - elapsed_time)
                
                if sleep_time > 0:
                    logger.info(f"Sleeping for {sleep_time:.0f}s until next scan")
                    await asyncio.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, stopping...")
                break
            except Exception as e:
                logger.error(f"Error in continuous mode: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
        
        self.running = False
        logger.info("Continuous mode stopped")
    
    def stop(self):
        """Stop the bot"""
        self.running = False
        logger.info("Stop signal received")
    
    async def get_opportunities_report(self, limit: int = 50) -> List[dict]:
        """Get current opportunities report"""
        df = self.database.get_opportunities(limit=limit)
        
        if df.empty:
            return []
        
        return df.to_dict('records')
    
    async def get_performance_report(self, days: int = 30) -> dict:
        """Get performance report"""
        performance = self.database.get_performance_summary(days)
        top_keywords = self.database.get_top_keywords(limit=10)
        
        return {
            'performance': performance,
            'top_keywords': top_keywords,
            'report_generated': datetime.now().isoformat()
        }
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up resources...")
        
        try:
            await self.ebay_api.close_session()
            await self.amazon_api.close_session()
            await self.notifications.cleanup()
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


async def main():
    """Main function"""
    bot = ArbitrageBot()
    
    # Setup signal handlers
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        bot.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize bot
        if not await bot.initialize():
            logger.error("Failed to initialize bot")
            return 1
        
        # Check command line arguments
        if len(sys.argv) > 1:
            command = sys.argv[1].lower()
            
            if command == 'scan':
                # Single scan mode
                keywords = sys.argv[2:] if len(sys.argv) > 2 else None
                opportunities = await bot.run_single_scan(keywords)
                
                if opportunities:
                    print(f"\nFound {len(opportunities)} opportunities:")
                    for opp in opportunities[:10]:  # Show top 10
                        print(f"  {opp.product_title[:50]}... - £{opp.net_profit:.2f} profit ({opp.roi_percentage:.1f}% ROI)")
                else:
                    print("No opportunities found")
            
            elif command == 'report':
                # Generate report
                opportunities = await bot.get_opportunities_report()
                performance = await bot.get_performance_report()
                
                print(f"\n=== Arbitrage Bot Report ===")
                print(f"Current Opportunities: {len(opportunities)}")
                print(f"Performance Summary (30 days):")
                print(f"  Total Opportunities: {performance['performance'].get('total_opportunities', 0)}")
                print(f"  Total Potential Profit: £{performance['performance'].get('total_potential_profit', 0):.2f}")
                print(f"  Average ROI: {performance['performance'].get('avg_roi', 0):.1f}%")
            
            elif command == 'continuous':
                # Continuous mode
                await bot.run_continuous()
            
            else:
                print("Usage: python main.py [scan|report|continuous] [keywords...]")
                return 1
        else:
            # Default to continuous mode
            await bot.run_continuous()
        
        return 0
        
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        return 1
        
    finally:
        await bot.cleanup()


if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)
    
    # Run the bot
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
