import aiohttp
import asyncio
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
from datetime import datetime
from decimal import Decimal

from models import ArbitrageOpportunity

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manages notifications via Telegram and Email"""
    
    def __init__(self, config: Dict):
        self.config = config.get('notifications', {})
        self.session = None
        self.last_notification_time = {}
        
        # Rate limiting (prevent spam)
        self.min_notification_interval = 300  # 5 minutes between similar notifications
    
    async def initialize(self):
        """Initialize notification system"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        # Test connections
        await self._test_telegram_connection()
        self._test_email_config()
        
        logger.info("Notification system initialized")
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _test_telegram_connection(self):
        """Test Telegram bot connection"""
        if not self.config.get('telegram_bot_token'):
            logger.warning("Telegram bot token not configured")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.config['telegram_bot_token']}/getMe"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('ok'):
                        bot_info = data['result']
                        logger.info(f"Telegram bot connected: {bot_info.get('username')}")
                        return True
                
                logger.warning(f"Telegram connection test failed: {response.status}")
                return False
                
        except Exception as e:
            logger.error(f"Telegram connection test error: {e}")
            return False
    
    def _test_email_config(self):
        """Test email configuration"""
        required_fields = ['email_from', 'email_to', 'email_password']
        missing_fields = [field for field in required_fields if not self.config.get(field)]
        
        if missing_fields:
            logger.warning(f"Email not configured - missing: {missing_fields}")
            return False
        
        logger.info("Email configuration validated")
        return True
    
    async def send_opportunity_alert(self, opportunity: ArbitrageOpportunity):
        """Send alert for new opportunity"""
        # Rate limiting check
        rate_limit_key = f"{opportunity.source_platform}-{opportunity.target_platform}"
        now = datetime.now()
        
        if rate_limit_key in self.last_notification_time:
            time_since_last = (now - self.last_notification_time[rate_limit_key]).seconds
            if time_since_last < self.min_notification_interval:
                logger.debug(f"Rate limited notification for {rate_limit_key}")
                return
        
        self.last_notification_time[rate_limit_key] = now
        
        # Create alert message
        message = self._format_opportunity_message(opportunity)
        
        # Send via configured channels
        tasks = []
        
        if self.config.get('telegram_bot_token'):
            tasks.append(self._send_telegram_message(message))
        
        if self.config.get('email_from'):
            tasks.append(self._send_email_alert(opportunity, message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"Sent opportunity alert: {opportunity.opportunity_id}")
    
    def _format_opportunity_message(self, opportunity: ArbitrageOpportunity) -> str:
        """Format opportunity as message"""
        roi_emoji = "🔥" if opportunity.roi_percentage > 50 else "📈"
        risk_emoji = "⚠️" if opportunity.risk_score > 6 else "✅"
        
        message = f"""
{roi_emoji} **Arbitrage Opportunity Found!**

**Product:** {opportunity.product_title[:80]}{'...' if len(opportunity.product_title) > 80 else ''}

**💰 Profit Analysis:**
• Net Profit: £{opportunity.net_profit:.2f}
• ROI: {opportunity.roi_percentage:.1f}%
• Risk Score: {opportunity.risk_score:.1f}/10 {risk_emoji}

**📊 Platform Comparison:**
• Buy from {opportunity.source_platform.title()}: £{opportunity.source_price:.2f}
• Sell on {opportunity.target_platform.title()}: £{opportunity.target_price:.2f}

**💸 Cost Breakdown:**
• Source Cost: £{opportunity.source_price + opportunity.source_shipping:.2f}
• Target Fees: £{opportunity.target_fees:.2f}
• Source Fees: £{opportunity.source_fees:.2f}

**🔗 Links:**
• Source: {opportunity.source_url[:50]}{'...' if len(opportunity.source_url) > 50 else ''}
• Target: {opportunity.target_url[:50]}{'...' if len(opportunity.target_url) > 50 else ''}

**📅 Found:** {opportunity.created_at.strftime('%Y-%m-%d %H:%M')}
        """.strip()
        
        return message
    
    async def _send_telegram_message(self, message: str):
        """Send message via Telegram"""
        try:
            bot_token = self.config.get('telegram_bot_token')
            chat_id = self.config.get('telegram_chat_id')
            
            if not bot_token or not chat_id:
                logger.warning("Telegram credentials not configured")
                return False
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            # Format message for Telegram (Markdown)
            telegram_message = message.replace('**', '*')
            
            payload = {
                'chat_id': chat_id,
                'text': telegram_message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.debug("Telegram message sent successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Telegram send failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False
    
    async def _send_email_alert(self, opportunity: ArbitrageOpportunity, message: str):
        """Send email alert"""
        try:
            # Run email sending in thread pool to avoid blocking
            await asyncio.get_event_loop().run_in_executor(
                None, self._send_email_sync, opportunity, message
            )
            return True
            
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return False
    
    def _send_email_sync(self, opportunity: ArbitrageOpportunity, message: str):
        """Send email synchronously"""
        try:
            # Email configuration
            smtp_server = "smtp.gmail.com"
            smtp_port = 587
            
            from_email = self.config['email_from']
            to_email = self.config['email_to']
            password = self.config['email_password']
            
            # Create email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Arbitrage Alert: £{opportunity.net_profit:.2f} Profit ({opportunity.roi_percentage:.0f}% ROI)"
            msg['From'] = from_email
            msg['To'] = to_email
            
            # Create HTML version
            html_message = self._create_html_email(opportunity, message)
            
            # Attach parts
            text_part = MIMEText(message, 'plain', 'utf-8')
            html_part = MIMEText(html_message, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(from_email, password)
                server.send_message(msg)
            
            logger.debug("Email sent successfully")
            
        except Exception as e:
            logger.error(f"Email send error: {e}")
            raise
    
    def _create_html_email(self, opportunity: ArbitrageOpportunity, message: str) -> str:
        """Create HTML version of email"""
        profit_color = "#28a745" if opportunity.net_profit > 20 else "#ffc107"
        risk_color = "#dc3545" if opportunity.risk_score > 6 else "#28a745"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; }}
                .profit {{ color: {profit_color}; font-weight: bold; font-size: 18px; }}
                .risk {{ color: {risk_color}; font-weight: bold; }}
                .section {{ margin: 15px 0; padding: 10px; border-left: 3px solid #007bff; }}
                .link {{ word-break: break-all; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>🎯 Arbitrage Opportunity Detected!</h2>
                <p class="profit">Net Profit: £{opportunity.net_profit:.2f} ({opportunity.roi_percentage:.1f}% ROI)</p>
            </div>
            
            <div class="section">
                <h3>Product Details</h3>
                <p><strong>Title:</strong> {opportunity.product_title}</p>
                <p><strong>Risk Score:</strong> <span class="risk">{opportunity.risk_score:.1f}/10</span></p>
            </div>
            
            <div class="section">
                <h3>Financial Breakdown</h3>
                <table>
                    <tr><th>Item</th><th>Amount</th></tr>
                    <tr><td>Buy Price ({opportunity.source_platform.title()})</td><td>£{opportunity.source_price:.2f}</td></tr>
                    <tr><td>Shipping Cost</td><td>£{opportunity.source_shipping:.2f}</td></tr>
                    <tr><td>Source Fees</td><td>£{opportunity.source_fees:.2f}</td></tr>
                    <tr><td>Target Fees ({opportunity.target_platform.title()})</td><td>£{opportunity.target_fees:.2f}</td></tr>
                    <tr><td>Sell Price</td><td>£{opportunity.target_price:.2f}</td></tr>
                    <tr style="background-color: #f8f9fa;"><td><strong>Net Profit</strong></td><td><strong>£{opportunity.net_profit:.2f}</strong></td></tr>
                </table>
            </div>
            
            <div class="section">
                <h3>Action Links</h3>
                <p><strong>Source ({opportunity.source_platform.title()}):</strong><br>
                <a href="{opportunity.source_url}" class="link">{opportunity.source_url}</a></p>
                
                <p><strong>Target ({opportunity.target_platform.title()}):</strong><br>
                <a href="{opportunity.target_url}" class="link">{opportunity.target_url}</a></p>
            </div>
            
            <div class="section">
                <h3>Additional Information</h3>
                <p><strong>Source Seller Rating:</strong> {opportunity.source_seller_rating:.1f}/5.0</p>
                <p><strong>Stock Available:</strong> {opportunity.source_stock}</p>
                <p><strong>Discovery Time:</strong> {opportunity.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Opportunity ID:</strong> {opportunity.opportunity_id}</p>
            </div>
            
            <hr>
            <p><small>This alert was generated by the Arbitrage Bot. Please verify all information before making any purchases.</small></p>
        </body>
        </html>
        """
        
        return html
    
    async def send_daily_summary(self, opportunities_count: int, total_profit: Decimal, 
                                top_opportunities: list):
        """Send daily summary notification"""
        if opportunities_count == 0:
            message = "📊 **Daily Summary**\n\nNo new arbitrage opportunities found today."
        else:
            message = f"""
📊 **Daily Arbitrage Summary**

**Today's Results:**
• {opportunities_count} opportunities found
• £{total_profit:.2f} total potential profit

**Top Opportunities:**
"""
            for i, opp in enumerate(top_opportunities[:5], 1):
                message += f"{i}. £{opp.net_profit:.2f} profit - {opp.product_title[:40]}...\n"
        
        # Send via configured channels
        tasks = []
        
        if self.config.get('telegram_bot_token'):
            tasks.append(self._send_telegram_message(message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_error_alert(self, error_message: str, component: str):
        """Send error alert to administrators"""
        message = f"""
🚨 **System Error Alert**

**Component:** {component}
**Error:** {error_message}
**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please check the system logs for more details.
        """.strip()
        
        if self.config.get('telegram_bot_token'):
            await self._send_telegram_message(message)
    
    async def send_system_status(self, status: Dict):
        """Send system status update"""
        uptime = status.get('uptime', 'Unknown')
        opportunities_today = status.get('opportunities_today', 0)
        last_scan = status.get('last_scan', 'Never')
        
        message = f"""
🤖 **System Status Update**

**Uptime:** {uptime}
**Opportunities Today:** {opportunities_today}
**Last Scan:** {last_scan}
**Status:** {'🟢 Healthy' if status.get('healthy', False) else '🔴 Issues Detected'}
        """.strip()
        
        if self.config.get('telegram_bot_token'):
            await self._send_telegram_message(message)
