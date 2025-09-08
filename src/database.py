class DatabaseManager:
    """Manages SQLite database operations"""
    
    def __init__(self, db_path='arbitrage.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Opportunities table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS opportunities (
                opportunity_id TEXT PRIMARY KEY,
                source_platform TEXT,
                target_platform TEXT,
                product_title TEXT,
                source_price REAL,
                target_price REAL,
                source_url TEXT,
                target_url TEXT,
                source_shipping REAL,
                target_shipping REAL,
                source_fees REAL,
                target_fees REAL,
                net_profit REAL,
                roi_percentage REAL,
                source_seller_rating REAL,
                target_seller_rating REAL,
                source_stock INTEGER,
                target_demand_score REAL,
                risk_score REAL,
                created_at TIMESTAMP,
                status TEXT,
                notes TEXT
            )
        ''')
        
        # Performance tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE,
                opportunities_found INTEGER,
                opportunities_acted INTEGER,
                total_profit REAL,
                total_investment REAL,
                roi_percentage REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Blacklist table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blacklist (
                seller_id TEXT PRIMARY KEY,
                platform TEXT,
                reason TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Price history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                platform TEXT,
                price REAL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_opportunity(self, opportunity: ArbitrageOpportunity):
        """Save opportunity to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        data = asdict(opportunity)
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        
        cursor.execute(
            f"INSERT OR REPLACE INTO opportunities ({columns}) VALUES ({placeholders})",
            list(data.values())
        )
        
        conn.commit()
        conn.close()
    
    def get_opportunities(self, status='new', limit=100):
        """Retrieve opportunities from database"""
        conn = sqlite3.connect(self.db_path)
        query = """
            SELECT * FROM opportunities 
            WHERE status = ? 
            ORDER BY net_profit DESC 
            LIMIT ?
        """
        df = pd.read_sql_query(query, conn, params=(status, limit))
        conn.close()
        return df
