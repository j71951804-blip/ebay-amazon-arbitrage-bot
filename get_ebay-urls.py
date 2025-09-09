#!/usr/bin/env python3
"""
Extract eBay URLs from your arbitrage opportunities
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / 'src'))

from database import DatabaseManager

def show_opportunity_urls():
    """Show all opportunities with clickable URLs"""
    db = DatabaseManager()
    df = db.get_opportunities(limit=20)
    
    if len(df) == 0:
        print("No opportunities found in database")
        return
    
    print("🔍 Your Arbitrage Opportunities with Direct Links:")
    print("=" * 80)
    
    for i, (_, opp) in enumerate(df.iterrows(), 1):
        print(f"\n🎯 OPPORTUNITY #{i}")
        print(f"Product: {opp['product_title']}")
        print(f"Profit: £{opp['net_profit']:.2f} ({opp['roi_percentage']:.1f}% ROI)")
        print(f"Risk Score: {opp['risk_score']:.1f}/10")
        
        print(f"\n📦 BUY FROM {opp['source_platform'].upper()}:")
        print(f"   Price: £{opp['source_price']:.2f}")
        print(f"   URL: {opp['source_url']}")
        
        print(f"\n💰 SELL ON {opp['target_platform'].upper()}:")
        print(f"   Price: £{opp['target_price']:.2f}")
        print(f"   URL: {opp['target_url']}")
        
        print(f"\n📋 SUMMARY:")
        print(f"   Total Cost: £{opp['source_price'] + opp['source_shipping'] + opp['source_fees']:.2f}")
        print(f"   Revenue: £{opp['target_price']:.2f}")
        print(f"   Net Profit: £{opp['net_profit']:.2f}")
        
        print("\n" + "─" * 80)

if __name__ == "__main__":
    show_opportunity_urls()
