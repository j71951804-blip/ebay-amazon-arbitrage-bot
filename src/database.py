import sqlite3
import pandas as pd
import logging
from datetime import datetime, timedelta
from dataclasses import asdict
from typing import List, Dict, Optional
from decimal import Decimal

from models import ArbitrageOpportunity, Product

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database operations"""
    
    def __init__(self, db_path='arbitrage.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys = ON")
            
            # Opportunities table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS opportunities (
                    opportunity_id TEXT PRIMARY KEY,
                    source_platform TEXT NOT NULL,
                    target_platform TEXT NOT NULL,
                    product_title TEXT NOT NULL,
                    source_price REAL NOT NULL,
                    target_price REAL NOT NULL,
                    source_url TEXT,
                    target_url TEXT,
                    source_shipping REAL DEFAULT 0,
                    target_shipping REAL DEFAULT 0,
                    source_fees REAL DEFAULT 0,
                    target_fees REAL DEFAULT 0,
                    net_profit REAL NOT NULL,
                    roi_percentage REAL NOT NULL,
                    source_seller_rating REAL DEFAULT 0,
                    target_seller_rating REAL DEFAULT 0,
                    source_stock INTEGER DEFAULT 0,
                    target_demand_score REAL DEFAULT 0,
                    risk_score REAL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL,
                    status TEXT DEFAULT 'new',
                    notes TEXT
                )
            ''')
            
            # Create indexes separately
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_opportunities_status ON opportunities(status)''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_opportunities_profit ON opportunities(net_profit DESC)''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_opportunities_created ON opportunities(created_at DESC)''')
            
            # Performance tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    opportunities_found INTEGER DEFAULT 0,
                    opportunities_acted INTEGER DEFAULT 0,
                    total_profit REAL DEFAULT 0,
                    total_investment REAL DEFAULT 0,
                    roi_percentage REAL DEFAULT 0,
                    platform_breakdown TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date)
                )
            ''')
            
            # Blacklist table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blacklist (
                    seller_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    reason TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (seller_id, platform)
                )
            ''')
            
            # Price history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    price REAL NOT NULL,
                    shipping REAL DEFAULT 0,
                    stock INTEGER DEFAULT 0,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for price history
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_price_history_product_platform ON price_history(product_id, platform)''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_price_history_recorded ON price_history(recorded_at DESC)''')
            
            # Search keywords tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS search_keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    results_found INTEGER DEFAULT 0,
                    opportunities_found INTEGER DEFAULT 0,
                    last_searched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    avg_profit REAL DEFAULT 0,
                    success_rate REAL DEFAULT 0,
                    UNIQUE(keyword, platform)
                )
            ''')
            
            # Alerts/notifications log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opportunity_id TEXT,
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'sent',
                    FOREIGN KEY (opportunity_id) REFERENCES opportunities (opportunity_id)
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def save_opportunity(self, opportunity: ArbitrageOpportunity) -> bool:
        """Save opportunity to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Convert opportunity to dict and handle Decimal types
            data = asdict(opportunity)
            
            # Convert Decimal to float for SQLite
            for key, value in data.items():
                if isinstance(value, Decimal):
                    data[key] = float(value)
                elif isinstance(value, datetime):
                    data[key] = value.isoformat()
            
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            
            cursor.execute(
                f"INSERT OR REPLACE INTO opportunities ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Saved opportunity: {opportunity.opportunity_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving opportunity: {e}")
            return False
    
    def save_opportunities_batch(self, opportunities: List[ArbitrageOpportunity]) -> int:
        """Save multiple opportunities in batch"""
        if not opportunities:
            return 0
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            saved_count = 0
            for opportunity in opportunities:
                data = asdict(opportunity)
                
                # Convert Decimal to float for SQLite
                for key, value in data.items():
                    if isinstance(value, Decimal):
                        data[key] = float(value)
                    elif isinstance(value, datetime):
                        data[key] = value.isoformat()
                
                columns = ', '.join(data.keys())
                placeholders = ', '.join(['?' for _ in data])
                
                cursor.execute(
                    f"INSERT OR REPLACE INTO opportunities ({columns}) VALUES ({placeholders})",
                    list(data.values())
                )
                saved_count += 1
            
            conn.commit()
            conn.close()
            
            logger.info(f"Saved {saved_count} opportunities to database")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error saving opportunities batch: {e}")
            return 0
    
    def get_opportunities(self, status: str = 'new', limit: int = 100, 
                         min_profit: float = 0) -> pd.DataFrame:
        """Retrieve opportunities from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            query = """
                SELECT * FROM opportunities 
                WHERE status = ? AND net_profit >= ?
                ORDER BY net_profit DESC 
                LIMIT ?
            """
            
            df = pd.read_sql_query(query, conn, params=(status, min_profit, limit))
            conn.close()
            
            return df
            
        except Exception as e:
            logger.error(f"Error retrieving opportunities: {e}")
            return pd.DataFrame()
    
    def update_opportunity_status(self, opportunity_id: str, status: str, notes: str = None) -> bool:
        """Update opportunity status"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if notes:
                cursor.execute(
                    "UPDATE opportunities SET status = ?, notes = ? WHERE opportunity_id = ?",
                    (status, notes, opportunity_id)
                )
            else:
                cursor.execute(
                    "UPDATE opportunities SET status = ? WHERE opportunity_id = ?",
                    (status, opportunity_id)
                )
            
            conn.commit()
            affected_rows = cursor.rowcount
            conn.close()
            
            return affected_rows > 0
            
        except Exception as e:
            logger.error(f"Error updating opportunity status: {e}")
            return False
    
    def save_price_history(self, products: List[Product]):
        """Save product price history"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for product in products:
                cursor.execute('''
                    INSERT INTO price_history (product_id, platform, price, shipping, stock)
                    VALUES (?, ?, ?, ?, ?)
                ''', (product.product_id, product.platform, float(product.price), 
                      float(product.shipping), product.stock))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Saved price history for {len(products)} products")
            
        except Exception as e:
            logger.error(f"Error saving price history: {e}")
    
    def get_price_history(self, product_id: str, platform: str, days: int = 30) -> pd.DataFrame:
        """Get price history for a product"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            since_date = datetime.now() - timedelta(days=days)
            query = """
                SELECT * FROM price_history 
                WHERE product_id = ? AND platform = ? AND recorded_at >= ?
                ORDER BY recorded_at DESC
            """
            
            df = pd.read_sql_query(query, conn, params=(product_id, platform, since_date))
            conn.close()
            
            return df
            
        except Exception as e:
            logger.error(f"Error retrieving price history: {e}")
            return pd.DataFrame()
    
    def add_to_blacklist(self, seller_id: str, platform: str, reason: str):
        """Add seller to blacklist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO blacklist (seller_id, platform, reason)
                VALUES (?, ?, ?)
            ''', (seller_id, platform, reason))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Added {seller_id} ({platform}) to blacklist: {reason}")
            
        except Exception as e:
            logger.error(f"Error adding to blacklist: {e}")
    
    def is_blacklisted(self, seller_id: str, platform: str) -> bool:
        """Check if seller is blacklisted"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT 1 FROM blacklist WHERE seller_id = ? AND platform = ?",
                (seller_id, platform)
            )
            
            result = cursor.fetchone() is not None
            conn.close()
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking blacklist: {e}")
            return False
    
    def update_search_keyword_stats(self, keyword: str, platform: str, 
                                   results_found: int, opportunities_found: int, avg_profit: float):
        """Update search keyword statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            success_rate = (opportunities_found / results_found * 100) if results_found > 0 else 0
            
            cursor.execute('''
                INSERT OR REPLACE INTO search_keywords 
                (keyword, platform, results_found, opportunities_found, avg_profit, success_rate, last_searched)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (keyword, platform, results_found, opportunities_found, avg_profit, success_rate))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating keyword stats: {e}")
    
    def get_performance_summary(self, days: int = 30) -> Dict:
        """Get performance summary for the last N days"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            since_date = datetime.now() - timedelta(days=days)
            
            # Opportunities summary
            query = """
                SELECT 
                    COUNT(*) as total_opportunities,
                    SUM(net_profit) as total_potential_profit,
                    AVG(net_profit) as avg_profit,
                    AVG(roi_percentage) as avg_roi,
                    AVG(risk_score) as avg_risk_score,
                    COUNT(CASE WHEN status = 'acted' THEN 1 END) as acted_opportunities
                FROM opportunities 
                WHERE created_at >= ?
            """
            
            cursor = conn.cursor()
            cursor.execute(query, (since_date,))
            summary = cursor.fetchone()
            
            # Platform breakdown
            query = """
                SELECT source_platform, target_platform, COUNT(*) as count, AVG(net_profit) as avg_profit
                FROM opportunities 
                WHERE created_at >= ?
                GROUP BY source_platform, target_platform
            """
            
            cursor.execute(query, (since_date,))
            platform_breakdown = cursor.fetchall()
            
            conn.close()
            
            return {
                'total_opportunities': summary[0] or 0,
                'total_potential_profit': summary[1] or 0,
                'avg_profit': summary[2] or 0,
                'avg_roi': summary[3] or 0,
                'avg_risk_score': summary[4] or 0,
                'acted_opportunities': summary[5] or 0,
                'platform_breakdown': platform_breakdown,
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {}
    
    def cleanup_old_records(self, days: int = 90):
        """Clean up old records to manage database size"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Clean up old opportunities (keep acted ones)
            cursor.execute(
                "DELETE FROM opportunities WHERE created_at < ? AND status NOT IN ('acted', 'purchased')",
                (cutoff_date,)
            )
            
            opportunities_deleted = cursor.rowcount
            
            # Clean up old price history
            cursor.execute(
                "DELETE FROM price_history WHERE recorded_at < ?",
                (cutoff_date,)
            )
            
            price_history_deleted = cursor.rowcount
            
            # Clean up old alerts
            cursor.execute(
                "DELETE FROM alerts WHERE sent_at < ?",
                (cutoff_date,)
            )
            
            alerts_deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {opportunities_deleted} opportunities, "
                       f"{price_history_deleted} price records, {alerts_deleted} alerts")
            
        except Exception as e:
            logger.error(f"Error cleaning up database: {e}")
    
    def get_top_keywords(self, limit: int = 20) -> List[Dict]:
        """Get top performing keywords"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            query = """
                SELECT keyword, platform, opportunities_found, avg_profit, success_rate, last_searched
                FROM search_keywords
                WHERE opportunities_found > 0
                ORDER BY (opportunities_found * avg_profit) DESC
                LIMIT ?
            """
            
            cursor = conn.cursor()
            cursor.execute(query, (limit,))
            results = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'keyword': row[0],
                    'platform': row[1],
                    'opportunities_found': row[2],
                    'avg_profit': row[3],
                    'success_rate': row[4],
                    'last_searched': row[5]
                }
                for row in results
            ]
            
        except Exception as e:
            logger.error(f"Error getting top keywords: {e}")
            return []
    
    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {}
            
            # Table counts
            tables = ['opportunities', 'performance', 'blacklist', 'price_history', 'search_keywords', 'alerts']
            
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    stats[f"{table}_count"] = count
                except sqlite3.OperationalError:
                    stats[f"{table}_count"] = 0
            
            conn.close()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
