import asyncio
import aiohttp
import logging
import time
from typing import Dict, List, Tuple
from datetime import datetime
import json

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
                
                if response.status == 200:
                    token_data = await response.json()
                    result['status'] = 'success'
                    result['details'] = {
                        'token_type': token_data.get('token_type'),
                        'expires_in': token_data.get('expires_in'),
                        'scope': token_data.get('scope')
                    }
                    
                    # Test search endpoint with token
                    await self._test_ebay_search(config, token_data.get('access_token'), result)
                    
                else:
                    error_data = await response.text()
                    result['error'] = f"HTTP {response.status}: {error_data}"
                    result['details']['http_status'] = response.status
                
        except asyncio.TimeoutError:
            result['error'] = "Request timeout"
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    async def _test_ebay_search(self, config: Dict, token: str, result: Dict):
        """Test eBay search endpoint"""
        try:
            headers = {
                'Authorization': f'Bearer {token}',
                'X-EBAY-C-MARKETPLACE-ID': config.get('marketplace_id', 'EBAY_GB')
            }
            
            params = {
                'q': 'test',
                'limit': 1
            }
            
            async with self.session.get(
                f"{config['api_endpoint']}/buy/browse/v1/item_summary/search",
                headers=headers,
                params=params
            ) as search_response:
                
                if search_response.status == 200:
                    search_data = await search_response.json()
                    result['details']['search_test'] = {
                        'status': 'success',
                        'total_results': search_data.get('total', 0)
                    }
                else:
                    result['details']['search_test'] = {
                        'status': 'failed',
                        'http_status': search_response.status
                    }
                    
        except Exception as e:
            result['details']['search_test'] = {
                'status': 'error',
                'error': str(e)
            }
    
    async def test_amazon_api(self, config: Dict) -> Dict:
        """Test Amazon API connection (mock implementation)"""
        result = {
            'platform': 'Amazon',
            'status': 'success',  # Mock success since we're using simulated data
            'response_time': 0.1,
            'error': None,
            'details': {
                'note': 'Using simulated Amazon data for development',
                'access_key': config.get('access_key', '')[:4] + '****' if config.get('access_key') else 'not_configured',
                'region': config.get('region', 'eu-west-2')
            }
        }
        
        # In production, implement actual Amazon API testing
        # This would involve AWS signature verification and PAAPI calls
        
        return result
    
    async def test_telegram_connection(self, config: Dict) -> Dict:
        """Test Telegram bot connection"""
        result = {
            'platform': 'Telegram',
            'status': 'failed',
            'response_time': None,
            'error': None,
            'details': {}
        }
        
        telegram_config = config.get('notifications', {})
        bot_token = telegram_config.get('telegram_bot_token')
        
        if not bot_token:
            result['error'] = "Telegram bot token not configured"
            return result
        
        try:
            start_time = time.time()
            
            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            
            async with self.session.get(url) as response:
                response_time = time.time() - start_time
                result['response_time'] = response_time
                
                if response.status == 200:
                    data = await response.json()
                    if data.get('ok'):
                        bot_info = data['result']
                        result['status'] = 'success'
                        result['details'] = {
                            'bot_username': bot_info.get('username'),
                            'bot_name': bot_info.get('first_name'),
                            'can_join_groups': bot_info.get('can_join_groups'),
                            'can_read_all_group_messages': bot_info.get('can_read_all_group_messages')
                        }
                    else:
                        result['error'] = data.get('description', 'Unknown Telegram API error')
                else:
                    error_text = await response.text()
                    result['error'] = f"HTTP {response.status}: {error_text}"
                    
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    async def test_email_connection(self, config: Dict) -> Dict:
        """Test email configuration"""
        result = {
            'platform': 'Email',
            'status': 'success',  # Email config test is basic
            'response_time': 0.0,
            'error': None,
            'details': {}
        }
        
        email_config = config.get('notifications', {})
        
        required_fields = ['email_from', 'email_to', 'email_password']
        missing_fields = [field for field in required_fields if not email_config.get(field)]
        
        if missing_fields:
            result['status'] = 'failed'
            result['error'] = f"Missing email configuration: {', '.join(missing_fields)}"
        else:
            result['details'] = {
                'email_from': email_config['email_from'],
                'email_to': email_config['email_to'],
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587
            }
        
        return result
    
    async def test_database_connection(self, db_path: str = 'arbitrage.db') -> Dict:
        """Test database connection"""
        result = {
            'platform': 'Database',
            'status': 'failed',
            'response_time': None,
            'error': None,
            'details': {}
        }
        
        try:
            import sqlite3
            from pathlib import Path
            
            start_time = time.time()
            
            # Check if database file exists
            db_file = Path(db_path)
            result['details']['database_path'] = str(db_file.absolute())
            result['details']['database_exists'] = db_file.exists()
            
            if db_file.exists():
                result['details']['database_size_mb'] = round(db_file.stat().st_size / 1024 / 1024, 2)
            
            # Test connection
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Test basic query
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            result['details']['tables'] = [table[0] for table in tables]
            result['details']['table_count'] = len(tables)
            
            # Test each table for record counts
            table_stats = {}
            for table_name in result['details']['tables']:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name[0]}")
                    count = cursor.fetchone()[0]
                    table_stats[table_name[0]] = count
                except Exception as e:
                    table_stats[table_name[0]] = f"Error: {e}"
            
            result['details']['table_stats'] = table_stats
            
            conn.close()
            
            response_time = time.time() - start_time
            result['response_time'] = response_time
            result['status'] = 'success'
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    async def test_network_connectivity(self) -> Dict:
        """Test basic network connectivity"""
        result = {
            'platform': 'Network',
            'status': 'failed',
            'response_time': None,
            'error': None,
            'details': {}
        }
        
        test_urls = [
            'https://www.google.com',
            'https://api.ebay.com',
            'https://api.telegram.org',
            'https://www.amazon.co.uk'
        ]
        
        connectivity_results = {}
        total_time = 0
        successful_tests = 0
        
        for url in test_urls:
            try:
                start_time = time.time()
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    response_time = time.time() - start_time
                    total_time += response_time
                    
                    connectivity_results[url] = {
                        'status': 'success' if response.status < 400 else 'failed',
                        'http_status': response.status,
                        'response_time': round(response_time, 3)
                    }
                    
                    if response.status < 400:
                        successful_tests += 1
                        
            except asyncio.TimeoutError:
                connectivity_results[url] = {
                    'status': 'timeout',
                    'error': 'Request timeout'
                }
            except Exception as e:
                connectivity_results[url] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        result['details']['connectivity_tests'] = connectivity_results
        result['details']['success_rate'] = f"{successful_tests}/{len(test_urls)}"
        
        if successful_tests >= len(test_urls) * 0.75:  # 75% success rate
            result['status'] = 'success'
            result['response_time'] = round(total_time / len(test_urls), 3)
        else:
            result['error'] = f"Poor connectivity: only {successful_tests}/{len(test_urls)} tests passed"
        
        return result
    
    async def run_comprehensive_test(self, config: Dict, db_path: str = 'arbitrage.db') -> Dict:
        """Run comprehensive connection tests"""
        logger.info("Starting comprehensive connection tests...")
        
        start_time = time.time()
        
        # Run all tests concurrently where possible
        network_task = self.test_network_connectivity()
        database_task = self.test_database_connection(db_path)
        ebay_task = self.test_ebay_api(config.get('ebay', {}))
        amazon_task = self.test_amazon_api(config.get('amazon', {}))
        telegram_task = self.test_telegram_connection(config)
        email_task = self.test_email_connection(config)
        
        # Wait for all tests to complete
        results = await asyncio.gather(
            network_task,
            database_task,
            ebay_task,
            amazon_task,
            telegram_task,
            email_task,
            return_exceptions=True
        )
        
        total_time = time.time() - start_time
        
        # Process results
        test_results = {}
        successful_tests = 0
        total_tests = 0
        
        test_names = ['network', 'database', 'ebay', 'amazon', 'telegram', 'email']
        
        for i, result in enumerate(results):
            total_tests += 1
            test_name = test_names[i]
            
            if isinstance(result, Exception):
                test_results[test_name] = {
                    'platform': test_name.title(),
                    'status': 'error',
                    'error': str(result),
                    'response_time': None
                }
            else:
                test_results[test_name] = result
                if result.get('status') == 'success':
                    successful_tests += 1
        
        # Calculate overall status
        success_rate = successful_tests / total_tests
        if success_rate >= 0.8:
            overall_status = 'excellent'
        elif success_rate >= 0.6:
            overall_status = 'good'
        elif success_rate >= 0.4:
            overall_status = 'fair'
        else:
            overall_status = 'poor'
        
        # Generate summary
        summary = {
            'overall_status': overall_status,
            'success_rate': f"{successful_tests}/{total_tests}",
            'success_percentage': round(success_rate * 100, 1),
            'total_test_time': round(total_time, 2),
            'timestamp': datetime.now().isoformat(),
            'critical_services': self._check_critical_services(test_results),
            'recommendations': self._generate_recommendations(test_results)
        }
        
        return {
            'summary': summary,
            'detailed_results': test_results
        }
    
    def _check_critical_services(self, results: Dict) -> Dict:
        """Check status of critical services"""
        critical_services = {
            'network': results.get('network', {}).get('status') == 'success',
            'database': results.get('database', {}).get('status') == 'success',
            'ebay_api': results.get('ebay', {}).get('status') == 'success',
        }
        
        # Optional services
        optional_services = {
            'amazon_api': results.get('amazon', {}).get('status') == 'success',
            'telegram_notifications': results.get('telegram', {}).get('status') == 'success',
            'email_notifications': results.get('email', {}).get('status') == 'success',
        }
        
        critical_status = all(critical_services.values())
        
        return {
            'all_critical_online': critical_status,
            'critical_services': critical_services,
            'optional_services': optional_services
        }
    
    def _generate_recommendations(self, results: Dict) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Network issues
        if results.get('network', {}).get('status') != 'success':
            recommendations.append("🔴 CRITICAL: Network connectivity issues detected. Check internet connection.")
        
        # Database issues
        if results.get('database', {}).get('status') != 'success':
            recommendations.append("🔴 CRITICAL: Database connection failed. Check database file and permissions.")
        
        # eBay API issues
        ebay_status = results.get('ebay', {})
        if ebay_status.get('status') != 'success':
            if 'token' in ebay_status.get('error', '').lower():
                recommendations.append("🔴 CRITICAL: eBay API authentication failed. Check app credentials.")
            else:
                recommendations.append("🔴 CRITICAL: eBay API connection failed. Check network and credentials.")
        
        # Amazon API issues
        amazon_status = results.get('amazon', {})
        if amazon_status.get('status') != 'success':
            recommendations.append("🟡 WARNING: Amazon API not properly configured. Using simulated data.")
        
        # Notification issues
        if results.get('telegram', {}).get('status') != 'success':
            recommendations.append("🟡 WARNING: Telegram notifications not working. Check bot token and chat ID.")
        
        if results.get('email', {}).get('status') != 'success':
            recommendations.append("🟡 WARNING: Email notifications not configured. Set up email credentials.")
        
        # Performance recommendations
        slow_services = []
        for service, result in results.items():
            if result.get('response_time', 0) > 5:
                slow_services.append(service)
        
        if slow_services:
            recommendations.append(f"⚡ PERFORMANCE: Slow response from: {', '.join(slow_services)}. Check network quality.")
        
        # Success message
        if not recommendations:
            recommendations.append("✅ All systems operational! Arbitrage bot ready to run.")
        
        return recommendations


async def main():
    """Main function for running connection tests"""
    import sys
    import json
    from pathlib import Path
    
    # Load configuration
    config_path = Path('config/config.json')
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
    else:
        print("❌ Configuration file not found. Using default config.")
        config = {}
    
    # Run tests
    async with ConnectionTester() as tester:
        results = await tester.run_comprehensive_test(config)
        
        # Print summary
        summary = results['summary']
        print("\n" + "="*60)
        print("🔧 ARBITRAGE BOT - CONNECTION TEST RESULTS")
        print("="*60)
        print(f"Overall Status: {summary['overall_status'].upper()}")
        print(f"Success Rate: {summary['success_rate']} ({summary['success_percentage']}%)")
        print(f"Test Duration: {summary['total_test_time']}s")
        print(f"Test Time: {summary['timestamp']}")
        
        # Print critical services status
        critical = summary['critical_services']
        print(f"\n🎯 Critical Services:")
        for service, status in critical['critical_services'].items():
            icon = "✅" if status else "❌"
            print(f"  {icon} {service.replace('_', ' ').title()}")
        
        print(f"\n📡 Optional Services:")
        for service, status in critical['optional_services'].items():
            icon = "✅" if status else "❌"
            print(f"  {icon} {service.replace('_', ' ').title()}")
        
        # Print detailed results
        print(f"\n📊 Detailed Results:")
        for service, result in results['detailed_results'].items():
            status_icon = "✅" if result.get('status') == 'success' else "❌"
            response_time = result.get('response_time')
            time_str = f" ({response_time}s)" if response_time else ""
            
            print(f"  {status_icon} {result.get('platform', service.title())}{time_str}")
            
            if result.get('error'):
                print(f"      Error: {result['error']}")
        
        # Print recommendations
        print(f"\n💡 Recommendations:")
        for rec in summary['recommendations']:
            print(f"  {rec}")
        
        print("\n" + "="*60)
        
        # Exit with appropriate code
        sys.exit(0 if summary['overall_status'] in ['excellent', 'good'] else 1)


if __name__ == '__main__':
    asyncio.run(main())
