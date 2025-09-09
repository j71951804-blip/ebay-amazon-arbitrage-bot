
import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import numpy as np
from dataclasses import asdict

from models import Product, ArbitrageOpportunity
from database import DatabaseManager

logger = logging.getLogger(__name__)


class PriceTrendAnalyzer:
    """Analyzes price trends for better opportunity timing"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def analyze_price_trend(self, product_id: str, platform: str, days: int = 30) -> Dict:
        """Analyze price trend for a specific product"""
        try:
            df = self.db.get_price_history(product_id, platform, days)
            
            if df.empty or len(df) < 3:
                return {'trend': 'insufficient_data', 'confidence': 0.0}
            
            # Calculate price trend
            prices = df['price'].values
            dates = pd.to_datetime(df['recorded_at'])
            
            # Linear regression for trend
            x = np.arange(len(prices))
            coeffs = np.polyfit(x, prices, 1)
            slope = coeffs[0]
            
            # Determine trend
            if abs(slope) < 0.5:  # Less than £0.50 change per day
                trend = 'stable'
            elif slope > 0:
                trend = 'increasing'
            else:
                trend = 'decreasing'
            
            # Calculate confidence based on R-squared
            correlation = np.corrcoef(x, prices)[0, 1]
            confidence = abs(correlation) ** 2
            
            # Calculate volatility
            volatility = np.std(prices) / np.mean(prices) * 100
            
            return {
                'trend': trend,
                'slope': float(slope),
                'confidence': float(confidence),
                'volatility': float(volatility),
                'current_price': float(prices[-1]),
                'avg_price': float(np.mean(prices)),
                'min_price': float(np.min(prices)),
                'max_price': float(np.max(prices))
            }
            
        except Exception as e:
            logger.error(f"Error analyzing price trend: {e}")
            return {'trend': 'error', 'confidence': 0.0}


class SeasonalAnalyzer:
    """Analyzes seasonal trends in products"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def get_seasonal_multiplier(self, product_title: str, current_date: datetime = None) -> float:
        """Get seasonal demand multiplier for a product"""
        if current_date is None:
            current_date = datetime.now()
        
        month = current_date.month
        title_lower = product_title.lower()
        
        # Electronics seasonal patterns
        electronics_keywords = ['iphone', 'samsung', 'laptop', 'tablet', 'headphones']
        gaming_keywords = ['playstation', 'xbox', 'nintendo', 'console', 'game']
        fitness_keywords = ['fitness', 'treadmill', 'weights', 'exercise']
        
        multiplier = 1.0
        
        # Holiday season (November-December)
        if month in [11, 12]:
            if any(keyword in title_lower for keyword in electronics_keywords + gaming_keywords):
                multiplier = 1.3  # 30% higher demand
        
        # New Year fitness (January-February)
        elif month in [1, 2]:
            if any(keyword in title_lower for keyword in fitness_keywords):
                multiplier = 1.4  # 40% higher demand
        
        # Back to school (August-September)
        elif month in [8, 9]:
            if any(keyword in title_lower for keyword in ['laptop', 'tablet', 'backpack']):
                multiplier = 1.2  # 20% higher demand
        
        # Summer season (June-August)
        elif month in [6, 7, 8]:
            if any(keyword in title_lower for keyword in ['camera', 'phone', 'speaker']):
                multiplier = 1.1  # 10% higher demand
        
        return multiplier


class CompetitorAnalyzer:
    """Analyzes competitive landscape"""
    
    def __init__(self):
        self.competitor_data = {}
    
    def analyze_market_position(self, opportunity: ArbitrageOpportunity, 
                               similar_opportunities: List[ArbitrageOpportunity]) -> Dict:
        """Analyze market position of an opportunity"""
        try:
            if not similar_opportunities:
                return {'position': 'unique', 'competition_level': 'low'}
            
            # Compare profits
            our_profit = float(opportunity.net_profit)
            competitor_profits = [float(opp.net_profit) for opp in similar_opportunities]
            
            profit_rank = sum(1 for p in competitor_profits if p < our_profit) + 1
            total_competitors = len(competitor_profits) + 1
            
            # Determine position
            if profit_rank == 1:
                position = 'best'
            elif profit_rank <= total_competitors * 0.3:
                position = 'top'
            elif profit_rank <= total_competitors * 0.7:
                position = 'middle'
            else:
                position = 'bottom'
            
            # Competition level
            if total_competitors <= 3:
                competition_level = 'low'
            elif total_competitors <= 8:
                competition_level = 'medium'
            else:
                competition_level = 'high'
            
            return {
                'position': position,
                'profit_rank': profit_rank,
                'total_competitors': total_competitors,
                'competition_level': competition_level,
                'avg_competitor_profit': float(np.mean(competitor_profits))
            }
            
        except Exception as e:
            logger.error(f"Error analyzing market position: {e}")
            return {'position': 'unknown', 'competition_level': 'unknown'}


class RiskAssessment:
    """Advanced risk assessment for opportunities"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.price_analyzer = PriceTrendAnalyzer(db_manager)
    
    def assess_comprehensive_risk(self, opportunity: ArbitrageOpportunity) -> Dict:
        """Comprehensive risk assessment"""
        try:
            risks = {}
            total_risk_score = 0.0
            
            # Price volatility risk
            price_trend = self.price_analyzer.analyze_price_trend(
                opportunity.source_platform + '_' + str(hash(opportunity.product_title)),
                opportunity.source_platform
            )
            
            volatility_risk = min(price_trend.get('volatility', 20) / 10, 5.0)
            risks['price_volatility'] = volatility_risk
            total_risk_score += volatility_risk
            
            # Market saturation risk
            # Check how many similar opportunities exist
            saturation_risk = self._assess_market_saturation(opportunity)
            risks['market_saturation'] = saturation_risk
            total_risk_score += saturation_risk
            
            # Platform-specific risks
            platform_risk = self._assess_platform_risk(opportunity)
            risks['platform_risk'] = platform_risk
            total_risk_score += platform_risk
            
            # Liquidity risk
            liquidity_risk = self._assess_liquidity_risk(opportunity)
            risks['liquidity_risk'] = liquidity_risk
            total_risk_score += liquidity_risk
            
            # Time sensitivity risk
            time_risk = self._assess_time_sensitivity(opportunity)
            risks['time_sensitivity'] = time_risk
            total_risk_score += time_risk
            
            # Overall risk level
            if total_risk_score <= 8:
                risk_level = 'low'
            elif total_risk_score <= 15:
                risk_level = 'medium'
            elif total_risk_score <= 22:
                risk_level = 'high'
            else:
                risk_level = 'very_high'
            
            return {
                'total_risk_score': total_risk_score,
                'risk_level': risk_level,
                'risk_breakdown': risks,
                'recommendations': self._generate_risk_recommendations(risks, risk_level)
            }
            
        except Exception as e:
            logger.error(f"Error in comprehensive risk assessment: {e}")
            return {'total_risk_score': 10.0, 'risk_level': 'unknown'}
    
    def _assess_market_saturation(self, opportunity: ArbitrageOpportunity) -> float:
        """Assess market saturation risk"""
        # Simple implementation - in production, could analyze competitor count
        base_saturation = 2.0
        
        # Adjust based on profit margin
        if opportunity.roi_percentage > 100:
            return base_saturation + 2.0  # High ROI often means high competition
        elif opportunity.roi_percentage < 25:
            return base_saturation - 0.5  # Low ROI, less competition
        
        return base_saturation
    
    def _assess_platform_risk(self, opportunity: ArbitrageOpportunity) -> float:
        """Assess platform-specific risks"""
        risk_scores = {
            'ebay': 2.5,    # Higher individual seller risk
            'amazon': 1.5,  # More regulated but higher fees
        }
        
        source_risk = risk_scores.get(opportunity.source_platform.lower(), 2.0)
        target_risk = risk_scores.get(opportunity.target_platform.lower(), 2.0)
        
        return (source_risk + target_risk) / 2
    
    def _assess_liquidity_risk(self, opportunity: ArbitrageOpportunity) -> float:
        """Assess how quickly the item can be sold"""
        base_risk = 2.0
        
        # Adjust based on price range
        price = float(opportunity.target_price)
        if price < 50:
            return base_risk - 0.5  # Easier to sell cheaper items
        elif price > 500:
            return base_risk + 1.5  # Harder to sell expensive items
        
        return base_risk
    
    def _assess_time_sensitivity(self, opportunity: ArbitrageOpportunity) -> float:
        """Assess time sensitivity of the opportunity"""
        base_risk = 1.5
        
        # Higher profit opportunities are often more time-sensitive
        if opportunity.roi_percentage > 75:
            return base_risk + 1.0
        elif opportunity.roi_percentage < 30:
            return base_risk - 0.5
        
        return base_risk
    
    def _generate_risk_recommendations(self, risks: Dict, risk_level: str) -> List[str]:
        """Generate risk mitigation recommendations"""
        recommendations = []
        
        if risks.get('price_volatility', 0) > 3:
            recommendations.append("Monitor price closely - high volatility detected")
        
        if risks.get('market_saturation', 0) > 3:
            recommendations.append("Act quickly - high market competition")
        
        if risks.get('liquidity_risk', 0) > 3:
            recommendations.append("Consider lower quantities - potential selling difficulty")
        
        if risks.get('time_sensitivity', 0) > 2.5:
            recommendations.append("Time-sensitive opportunity - prioritize execution")
        
        if risk_level == 'very_high':
            recommendations.append("CAUTION: Very high risk - consider skipping")
        elif risk_level == 'high':
            recommendations.append("High risk - ensure thorough due diligence")
        
        return recommendations


class OpportunityRanker:
    """Advanced ranking system for opportunities"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.risk_assessor = RiskAssessment(db_manager)
        self.seasonal_analyzer = SeasonalAnalyzer(db_manager)
    
    def rank_opportunities(self, opportunities: List[ArbitrageOpportunity], 
                          user_preferences: Dict = None) -> List[Tuple[ArbitrageOpportunity, Dict]]:
        """Advanced ranking of opportunities"""
        if user_preferences is None:
            user_preferences = {
                'risk_tolerance': 'medium',  # low, medium, high
                'profit_priority': 'balanced',  # profit, roi, balanced
                'time_horizon': 'short',  # short, medium, long
                'capital_available': 1000  # GBP
            }
        
        scored_opportunities = []
        
        for opp in opportunities:
            try:
                score_data = self._calculate_comprehensive_score(opp, user_preferences)
                scored_opportunities.append((opp, score_data))
            except Exception as e:
                logger.error(f"Error scoring opportunity {opp.opportunity_id}: {e}")
                continue
        
        # Sort by composite score
        scored_opportunities.sort(key=lambda x: x[1]['composite_score'], reverse=True)
        
        return scored_opportunities
    
    def _calculate_comprehensive_score(self, opportunity: ArbitrageOpportunity, 
                                     preferences: Dict) -> Dict:
        """Calculate comprehensive scoring"""
        scores = {}
        weights = self._get_scoring_weights(preferences)
        
        # Profit score (0-100)
        profit_score = min(float(opportunity.net_profit) * 2, 100)  # £50 = 100 points
        scores['profit'] = profit_score
        
        # ROI score (0-100)
        roi_score = min(opportunity.roi_percentage, 100)
        scores['roi'] = roi_score
        
        # Risk score (inverted - lower risk = higher score)
        risk_assessment = self.risk_assessor.assess_comprehensive_risk(opportunity)
        risk_score = max(0, 100 - risk_assessment['total_risk_score'] * 4)
        scores['risk'] = risk_score
        
        # Seasonal score
        seasonal_multiplier = self.seasonal_analyzer.get_seasonal_multiplier(opportunity.product_title)
        seasonal_score = (seasonal_multiplier - 0.5) * 100  # 0.5-1.5 -> 0-100
        scores['seasonal'] = max(0, min(100, seasonal_score))
        
        # Velocity score (how quickly can this be executed)
        velocity_score = self._calculate_velocity_score(opportunity)
        scores['velocity'] = velocity_score
        
        # Calculate weighted composite score
        composite_score = (
            scores['profit'] * weights['profit'] +
            scores['roi'] * weights['roi'] +
            scores['risk'] * weights['risk'] +
            scores['seasonal'] * weights['seasonal'] +
            scores['velocity'] * weights['velocity']
        )
        
        return {
            'composite_score': composite_score,
            'individual_scores': scores,
            'weights_used': weights,
            'risk_assessment': risk_assessment
        }
    
    def _get_scoring_weights(self, preferences: Dict) -> Dict:
        """Get scoring weights based on user preferences"""
        base_weights = {
            'profit': 0.3,
            'roi': 0.25,
            'risk': 0.25,
            'seasonal': 0.1,
            'velocity': 0.1
        }
        
        # Adjust based on preferences
        if preferences['risk_tolerance'] == 'low':
            base_weights['risk'] = 0.4
            base_weights['profit'] = 0.2
        elif preferences['risk_tolerance'] == 'high':
            base_weights['risk'] = 0.1
            base_weights['profit'] = 0.4
        
        if preferences['profit_priority'] == 'profit':
            base_weights['profit'] = 0.5
            base_weights['roi'] = 0.15
        elif preferences['profit_priority'] == 'roi':
            base_weights['roi'] = 0.45
            base_weights['profit'] = 0.2
        
        return base_weights
    
    def _calculate_velocity_score(self, opportunity: ArbitrageOpportunity) -> float:
        """Calculate how quickly opportunity can be executed"""
        score = 50.0  # Base score
        
        # Adjust based on stock availability
        if opportunity.source_stock > 10:
            score += 20
        elif opportunity.source_stock > 5:
            score += 10
        elif opportunity.source_stock <= 1:
            score -= 20
        
        # Adjust based on seller rating (higher rating = faster transaction)
        if opportunity.source_seller_rating >= 4.5:
            score += 15
        elif opportunity.source_seller_rating >= 4.0:
            score += 10
        elif opportunity.source_seller_rating < 3.5:
            score -= 15
        
        return max(0, min(100, score))


class AutomatedDecisionEngine:
    """Automated decision engine for opportunity execution"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.ranker = OpportunityRanker(db_manager)
    
    def make_automated_decisions(self, opportunities: List[ArbitrageOpportunity],
                                decision_criteria: Dict) -> List[Dict]:
        """Make automated buy/skip decisions"""
        decisions = []
        
        # Rank opportunities first
        ranked_opportunities = self.ranker.rank_opportunities(opportunities)
        
        total_capital_used = 0.0
        available_capital = decision_criteria.get('max_capital', 1000.0)
        
        for opportunity, score_data in ranked_opportunities:
            try:
                decision = self._evaluate_single_opportunity(
                    opportunity, score_data, decision_criteria,
                    available_capital - total_capital_used
                )
                
                if decision['action'] == 'buy':
                    total_capital_used += decision['capital_required']
                
                decisions.append({
                    'opportunity_id': opportunity.opportunity_id,
                    'decision': decision,
                    'score_data': score_data
                })
                
                # Stop if we've used all capital
                if total_capital_used >= available_capital * 0.95:
                    break
                    
            except Exception as e:
                logger.error(f"Error making decision for {opportunity.opportunity_id}: {e}")
                continue
        
        return decisions
    
    def _evaluate_single_opportunity(self, opportunity: ArbitrageOpportunity,
                                   score_data: Dict, criteria: Dict,
                                   available_capital: float) -> Dict:
        """Evaluate single opportunity for automated decision"""
        
        capital_required = float(opportunity.source_price + opportunity.source_shipping)
        
        # Check capital constraint
        if capital_required > available_capital:
            return {
                'action': 'skip',
                'reason': 'insufficient_capital',
                'capital_required': capital_required,
                'confidence': 0.0
            }
        
        # Check minimum thresholds
        min_score = criteria.get('min_composite_score', 60)
        if score_data['composite_score'] < min_score:
            return {
                'action': 'skip',
                'reason': 'low_score',
                'capital_required': capital_required,
                'confidence': 0.2
            }
        
        # Check risk tolerance
        max_risk = criteria.get('max_risk_score', 15)
        if score_data['risk_assessment']['total_risk_score'] > max_risk:
            return {
                'action': 'skip',
                'reason': 'too_risky',
                'capital_required': capital_required,
                'confidence': 0.3
            }
        
        # Check minimum profit
        min_profit = criteria.get('min_profit', 10)
        if float(opportunity.net_profit) < min_profit:
            return {
                'action': 'skip',
                'reason': 'insufficient_profit',
                'capital_required': capital_required,
                'confidence': 0.1
            }
        
        # Calculate confidence based on score
        confidence = min(score_data['composite_score'] / 100, 0.95)
        
        return {
            'action': 'buy',
            'reason': 'meets_criteria',
            'capital_required': capital_required,
            'confidence': confidence,
            'expected_profit': float(opportunity.net_profit),
            'expected_roi': opportunity.roi_percentage
        }
