#!/usr/bin/env python3
"""
Utility scripts for the arbitrage bot
Includes data cleanup, report generation, and maintenance tasks
"""

import sqlite3
import pandas as pd
import json
import csv
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal
import argparse
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DataExporter:
    """Export data to various formats"""
    
    def __init__(self, db_path: str = 'arbitrage.db'):
        self.db_path = db_path
    
    def export_opportunities_to_csv(self, filepath: str, days: int = 30, status: str = None) -> bool:
        """Export opportunities to CSV"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Build query
            query = "SELECT * FROM opportunities WHERE created_at >= ?"
            params = [datetime.now() - timedelta(days=days)]
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY created_at DESC"
            
            # Execute and export
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            
            if df.empty:
                logger.warning("No opportunities found for export")
                return False
            
            df.to_csv(filepath, index=False)
            logger.info(f"Exported {len(df)} opportunities to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting opportunities: {e}")
            return False
    
    def export_performance_report(self, filepath: str, days: int = 30) -> bool:
        """Export performance report to JSON"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Opportunities summary
            opp_query = """
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as opportunities_found,
                    SUM(CASE WHEN status = 'acted' THEN 1 ELSE 0 END) as opportunities_acted,
                    SUM(net_profit) as total_potential_profit,
                    AVG(net_profit) as avg_profit,
                    AVG(roi_percentage) as avg_roi,
                    source_platform,
                    target_platform
                FROM opportunities 
                WHERE created_at >= ?
                GROUP BY DATE(created_at), source_platform, target_platform
                ORDER BY date DESC
            """
            
            since_date = datetime.now() - timedelta(days=days)
            df_opportunities = pd.read_sql_query(opp_query, conn, params=[since_date])
            
            # Keywords performance
            keywords_query = """
                SELECT keyword, platform, opportunities_found, avg_profit, success_rate, last_searched
                FROM search_keywords
                WHERE last_searched >= ?
                ORDER BY (opportunities_found * avg_profit) DESC
            """
            
            df_keywords = pd.read_sql_query(keywords_query, conn, params=[since_date])
            
            conn.close()
            
            # Create report
            report = {
                'report_date': datetime.now().isoformat(),
                'period_days': days,
                'opportunities_by_date': df_opportunities.to_dict('records'),
                'keyword_performance': df_keywords.to_dict('records'),
                'summary': {
                    'total_opportunities': int(df_opportunities['opportunities_found'].sum()) if not df_opportunities.empty else 0,
                    'total_potential_profit': float(df_opportunities['total_potential_profit'].sum()) if not df_opportunities.empty else 0,
                    'avg_profit_per_opportunity': float(df_opportunities['avg_profit'].mean()) if not df_opportunities.empty else 0,
                    'avg_roi': float(df_opportunities['avg_roi'].mean()) if not df_opportunities.empty else 0
                }
            }
            
            # Save report
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Performance report exported to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting performance report: {e}")
            return False
    
    def generate_html_report(self, filepath: str, days: int = 7) -> bool:
        """Generate HTML report"""
        try:
            # Get data
            conn = sqlite3.connect(self.db_path)
            
            # Recent opportunities
            opp_query = """
                SELECT product_title, source_platform, target_platform, net_profit, 
                       roi_percentage, risk_score, created_at, status
                FROM opportunities 
                WHERE created_at >= ?
                ORDER BY net_profit DESC
                LIMIT 50
            """
            
            since_date = datetime.now() - timedelta(days=days)
            df_opportunities = pd.read_sql_query(opp_query, conn, params=[since_date])
            
            conn.close()
            
            # Create HTML
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Arbitrage Bot Report</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    .header {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 30px; }}
                    .summary {{ display: flex; gap: 20px; margin-bottom: 30px; }}
                    .metric {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                    th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                    th {{ background-color: #f2f2f2; }}
                    .profit {{ color: #28a745; font-weight: bold; }}
                    .risk-low {{ color: #28a745; }}
                    .risk-medium {{ color: #ffc107; }}
                    .risk-high {{ color: #dc3545; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🎯 Arbitrage Bot Report</h1>
                    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>Period: Last {days} days</p>
                </div>
            """
            
            if not df_opportunities.empty:
                total_opportunities = len(df_opportunities)
                total_profit = df_opportunities['net_profit'].sum()
                avg_roi = df_opportunities['roi_percentage'].mean()
                avg_risk = df_opportunities['risk_score'].mean()
                
                html_content += f"""
                <div class="summary">
                    <div class="metric">
                        <h3>Total Opportunities</h3>
                        <h2>{total_opportunities}</h2>
                    </div>
                    <div class="metric">
                        <h3>Total Potential Profit</h3>
                        <h2 class="profit">£{total_profit:.2f}</h2>
                    </div>
                    <div class="metric">
                        <h3>Average ROI</h3>
                        <h2>{avg_roi:.1f}%</h2>
                    </div>
                    <div class="metric">
                        <h3>Average Risk Score</h3>
                        <h2>{avg_risk:.1f}/10</h2>
                    </div>
                </div>
                
                <h2>Top Opportunities</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Product</th>
                            <th>Source → Target</th>
                            <th>Profit</th>
                            <th>ROI</th>
                            <th>Risk</th>
                            <th>Status</th>
                            <th>Date</th>
                        </tr>
                    </thead>
                    <tbody>
                """
                
                for _, row in df_opportunities.iterrows():
                    risk_class = 'risk-low' if row['risk_score'] <= 4 else 'risk-medium' if row['risk_score'] <= 7 else 'risk-high'
                    product_title = row['product_title'][:50] + '...' if len(row['product_title']) > 50 else row['product_title']
                    
                    html_content += f"""
                        <tr>
                            <td>{product_title}</td>
                            <td>{row['source_platform'].title()} → {row['target_platform'].title()}</td>
                            <td class="profit">£{row['net_profit']:.2f}</td>
                            <td>{row['roi_percentage']:.1f}%</td>
                            <td class="{risk_class}">{row['risk_score']:.1f}</td>
                            <td>{row['status'].title()}</td>
                            <td>{pd.to_datetime(row['created_at']).strftime('%Y-%m-%d')}</td>
                        </tr>
                    """
                
                html_content += """
                    </tbody>
                </table>
                """
            else:
                html_content += """
                <div class="metric">
                    <h3>No opportunities found in the selected period</h3>
                </div>
                """
            
            html_content += """
            </body>
            </html>
            """
            
            with open(filepath, 'w') as f:
                f.write(html_content)
            
            logger.info(f"HTML report generated: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating HTML report: {e}")
            return False


class DatabaseMaintenance:
    """Database maintenance utilities"""
    
    def __init__(self, db_path: str = 'arbitrage.db'):
        self.db_path = db_path
    
    def cleanup_old_records(self, days: int = 90) -> Dict[str, int]:
        """Clean up old records"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            deleted_counts = {}
            
            # Clean opportunities (keep acted/purchased ones)
            cursor.execute(
                "DELETE FROM opportunities WHERE created_at < ? AND status NOT IN ('acted', 'purchased')",
                (cutoff_date,)
            )
            deleted_counts['opportunities'] = cursor.rowcount
            
            # Clean price history
            cursor.execute("DELETE FROM price_history WHERE recorded_at < ?", (cutoff_date,))
            deleted_counts['price_history'] = cursor.rowcount
            
            # Clean alerts
            cursor.execute("DELETE FROM alerts WHERE sent_at < ?", (cutoff_date,))
            deleted_counts['alerts'] = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            total_deleted = sum(deleted_counts.values())
            logger.info(f"Cleaned up {total_deleted} old records: {deleted_counts}")
            
            return deleted_counts
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {}
    
    def optimize_database(self) -> bool:
        """Optimize database performance"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Analyze tables
            cursor.execute("ANALYZE")
            
            # Vacuum database
            cursor.execute("VACUUM")
            
            # Reindex
            cursor.execute("REINDEX")
            
            conn.close()
            
            logger.info("Database optimization completed")
            return True
            
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            return False
    
    def backup_database(self, backup_dir: str = 'backups') -> Optional[str]:
        """Create database backup"""
        try:
            backup_path = Path(backup_dir)
            backup_path.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = backup_path / f"arbitrage_backup_{timestamp}.db"
            
            # Copy database
            import shutil
            shutil.copy2(self.db_path, backup_file)
            
            logger.info(f"Database backed up to {backup_file}")
            return str(backup_file)
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return None
    
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
            
            # Database size
            db_size = Path(self.db_path).stat().st_size / 1024 / 1024  # MB
            stats['database_size_mb'] = round(db_size, 2)
            
            # Recent activity
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN created_at >= datetime('now', '-1 day') THEN 1 END) as opportunities_24h,
                    COUNT(CASE WHEN created_at >= datetime('now', '-7 day') THEN 1 END) as opportunities_7d,
                    COUNT(CASE WHEN created_at >= datetime('now', '-30 day') THEN 1 END) as opportunities_30d
                FROM opportunities
            """)
            
            activity = cursor.fetchone()
            if activity:
                stats['opportunities_last_24h'] = activity[0]
                stats['opportunities_last_7d'] = activity[1] 
                stats['opportunities_last_30d'] = activity[2]
            
            conn.close()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}


class ConfigurationManager:
    """Configuration management utilities"""
    
    @staticmethod
    def validate_config(config_path: str = 'config/config.json') -> Dict:
        """Validate configuration file"""
        issues = []
        warnings = []
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Check required sections
            required_sections = ['ebay', 'amazon', 'notifications', 'profit_thresholds']
            for section in required_sections:
                if section not in config:
                    issues.append(f"Missing required section: {section}")
            
            # Check eBay configuration
            if 'ebay' in config:
                ebay_required = ['app_id', 'cert_id', 'dev_id']
                for field in ebay_required:
                    if not config['ebay'].get(field):
                        issues.append(f"Missing eBay field: {field}")
            
            # Check Amazon configuration
            if 'amazon' in config:
                amazon_required = ['access_key', 'secret_key']
                for field in amazon_required:
                    if not config['amazon'].get(field):
                        issues.append(f"Missing Amazon field: {field}")
            
            # Check notifications
            if 'notifications' in config:
                if not config['notifications'].get('telegram_bot_token'):
                    warnings.append("Telegram notifications not configured")
                if not config['notifications'].get('email_from'):
                    warnings.append("Email notifications not configured")
            
            # Check profit thresholds
            if 'profit_thresholds' in config:
                thresholds = config['profit_thresholds']
                if thresholds.get('min_profit_gbp', 0) <= 0:
                    warnings.append("Minimum profit threshold should be > 0")
                if thresholds.get('min_roi_percentage', 0) <= 0:
                    warnings.append("Minimum ROI threshold should be > 0")
            
            status = 'valid' if not issues else 'invalid'
            
            return {
                'status': status,
                'issues': issues,
                'warnings': warnings,
                'config_loaded': True
            }
            
        except FileNotFoundError:
            return {
                'status': 'invalid',
                'issues': [f"Configuration file not found: {config_path}"],
                'warnings': [],
                'config_loaded': False
            }
        except json.JSONDecodeError as e:
            return {
                'status': 'invalid',
                'issues': [f"Invalid JSON in config file: {e}"],
                'warnings': [],
                'config_loaded': False
            }
        except Exception as e:
            return {
                'status': 'invalid',
                'issues': [f"Error reading config: {e}"],
                'warnings': [],
                'config_loaded': False
            }
    
    @staticmethod
    def create_example_config(output_path: str = 'config/config.example.json') -> bool:
        """Create example configuration file"""
        try:
            Path(output_path).parent.mkdir(exist_ok=True)
            
            example_config = {
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
                    "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
                    "telegram_chat_id": "YOUR_CHAT_ID",
                    "email_from": "your_email@gmail.com",
                    "email_to": "alerts@yourdomain.com",
                    "email_password": "your_app_password"
                },
                "database": {
                    "path": "./arbitrage.db"
                },
                "search": {
                    "keywords": [
                        "electronics", "phone", "tablet", "laptop",
                        "camera", "headphones", "speaker", "watch"
                    ],
                    "max_results_per_platform": 50,
                    "search_interval_minutes": 30
                },
                "risk": {
                    "max_price_difference_percentage": 500,
                    "min_seller_feedback": 50,
                    "blocked_sellers": []
                }
            }
            
            with open(output_path, 'w') as f:
                json.dump(example_config, f, indent=2)
            
            logger.info(f"Example configuration created: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating example config: {e}")
            return False


def main():
    """Main function for utility scripts"""
    parser = argparse.ArgumentParser(description='Arbitrage Bot Utilities')
    parser.add_argument('command', choices=[
        'export-opportunities', 'export-performance', 'generate-html-report',
        'cleanup-database', 'optimize-database', 'backup-database',
        'database-stats', 'validate-config', 'create-example-config'
    ])
    parser.add_argument('--days', type=int, default=30, help='Number of days for reports')
    parser.add_argument('--output', type=str, help='Output file path')
    parser.add_argument('--status', type=str, help='Filter by status')
    parser.add_argument('--db-path', type=str, default='arbitrage.db', help='Database path')
    
    args = parser.parse_args()
    
    if args.command == 'export-opportunities':
        exporter = DataExporter(args.db_path)
        output_file = args.output or f'opportunities_{datetime.now().strftime("%Y%m%d")}.csv'
        success = exporter.export_opportunities_to_csv(output_file, args.days, args.status)
        sys.exit(0 if success else 1)
    
    elif args.command == 'export-performance':
        exporter = DataExporter(args.db_path)
        output_file = args.output or f'performance_{datetime.now().strftime("%Y%m%d")}.json'
        success = exporter.export_performance_report(output_file, args.days)
        sys.exit(0 if success else 1)
    
    elif args.command == 'generate-html-report':
        exporter = DataExporter(args.db_path)
        output_file = args.output or f'report_{datetime.now().strftime("%Y%m%d")}.html'
        success = exporter.generate_html_report(output_file, args.days)
        sys.exit(0 if success else 1)
    
    elif args.command == 'cleanup-database':
        maintenance = DatabaseMaintenance(args.db_path)
        deleted = maintenance.cleanup_old_records(args.days)
        print(f"Cleanup complete. Deleted records: {deleted}")
    
    elif args.command == 'optimize-database':
        maintenance = DatabaseMaintenance(args.db_path)
        success = maintenance.optimize_database()
        sys.exit(0 if success else 1)
    
    elif args.command == 'backup-database':
        maintenance = DatabaseMaintenance(args.db_path)
        backup_file = maintenance.backup_database()
        if backup_file:
            print(f"Database backed up to: {backup_file}")
        sys.exit(0 if backup_file else 1)
    
    elif args.command == 'database-stats':
        maintenance = DatabaseMaintenance(args.db_path)
        stats = maintenance.get_database_stats()
        print("\n=== Database Statistics ===")
        for key, value in stats.items():
            print(f"{key.replace('_', ' ').title()}: {value}")
    
    elif args.command == 'validate-config':
        config_path = args.output or 'config/config.json'
        result = ConfigurationManager.validate_config(config_path)
        
        print(f"\n=== Configuration Validation ===")
        print(f"Status: {result['status'].upper()}")
        
        if result['issues']:
            print(f"\nIssues ({len(result['issues'])}):")
            for issue in result['issues']:
                print(f"  ❌ {issue}")
        
        if result['warnings']:
            print(f"\nWarnings ({len(result['warnings'])}):")
            for warning in result['warnings']:
                print(f"  ⚠️  {warning}")
        
        if result['status'] == 'valid' and not result['warnings']:
            print("  ✅ Configuration is valid!")
        
        sys.exit(0 if result['status'] == 'valid' else 1)
    
    elif args.command == 'create-example-config':
        output_path = args.output or 'config/config.example.json'
        success = ConfigurationManager.create_example_config(output_path)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
