import json
import os
from pathlib import Path
from typing import Dict, Any
from decimal import Decimal
import logging

from models import MarketplaceConfig, ProfitThresholds

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration from JSON files and environment variables"""
    
    def __init__(self, config_dir='config'):
        self.config_dir = Path(config_dir)
        self.config = {}
        self.load_config()
    
    def load_config(self):
        """Load configuration from JSON and environment variables"""
        # Load main config file
        config_file = self.config_dir / 'config.json'
        if config_file.exists():
            with open(config_file, 'r') as f:
                self.config = json.load(f)
        else:
            logger.warning(f"Config file not found: {config_file}")
            self.config = self.get_default_config()
        
        # Override with environment variables
        self.load_env_overrides()
        
        # Validate configuration
        self.validate_config()
        
        logger.info("Configuration loaded successfully")
    
    def load_env_overrides(self):
        """Override config with environment variables"""
        env_mappings = {
            'EBAY_APP_ID': ['ebay', 'app_id'],
            'EBAY_CERT_ID': ['ebay', 'cert_id'],
            'EBAY_DEV_ID': ['ebay', 'dev_id'],
            'AMAZON_ACCESS_KEY': ['amazon', 'access_key'],
            'AMAZON_SECRET_KEY': ['amazon', 'secret_key'],
            'TELEGRAM_BOT_TOKEN': ['notifications', 'telegram_bot_token'],
            'TELEGRAM_CHAT_ID': ['notifications', 'telegram_chat_id'],
            'EMAIL_PASSWORD': ['notifications', 'email_password'],
            'DB_PATH': ['database', 'path']
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                self.set_nested_config(config_path, value)
    
    def set_nested_config(self, path, value):
        """Set nested configuration value"""
        config = self.config
        for key in path[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[path[-1]] = value
    
    def get_default_config(self):
        """Return default configuration"""
        return {
            "ebay": {
                "app_id": "",
                "cert_id": "",
                "dev_id": "",
                "marketplace_id": "EBAY_GB",
                "api_endpoint": "https://api.ebay.com"
            },
            "amazon": {
                "access_key": "",
                "secret_key": "",
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
    
    def validate_config(self):
        """Validate configuration completeness"""
        required_fields = [
            ['ebay', 'app_id'],
            ['ebay', 'cert_id'],
            ['amazon', 'access_key'],
            ['amazon', 'secret_key']
        ]
        
        missing_fields = []
        for field_path in required_fields:
            if not self.get_nested_config(field_path):
                missing_fields.append('.'.join(field_path))
        
        if missing_fields:
            logger.warning(f"Missing configuration fields: {missing_fields}")
        
    def get_nested_config(self, path):
        """Get nested configuration value"""
        config = self.config
        try:
            for key in path:
                config = config[key]
            return config
        except (KeyError, TypeError):
            return None
    
    def get_marketplace_config(self, platform: str) -> MarketplaceConfig:
        """Get marketplace-specific configuration"""
        platform_config = self.config.get(platform, {})
        return MarketplaceConfig(
            platform=platform,
            enabled=platform_config.get('enabled', True),
            api_credentials=platform_config,
            fee_structure=platform_config.get('fees', {}),
            search_limits=platform_config.get('limits', {})
        )
    
    def get_profit_thresholds(self) -> ProfitThresholds:
        """Get profit threshold configuration"""
        thresholds = self.config.get('profit_thresholds', {})
        return ProfitThresholds(
            min_profit_gbp=Decimal(str(thresholds.get('min_profit_gbp', 10))),
            min_roi_percentage=thresholds.get('min_roi_percentage', 25.0),
            alert_profit_gbp=Decimal(str(thresholds.get('alert_profit_gbp', 25))),
            max_risk_score=thresholds.get('max_risk_score', 7.0),
            min_seller_rating=thresholds.get('min_seller_rating', 3.5)
        )
    
    def get(self, key: str, default=None):
        """Get configuration value"""
        return self.config.get(key, default)
    
    def save_config(self, filename='config.json'):
        """Save current configuration to file"""
        config_file = self.config_dir / filename
        config_file.parent.mkdir(exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(self.config, f, indent=2, default=str)
        
        logger.info(f"Configuration saved to {config_file}")
