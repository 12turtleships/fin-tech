#!/usr/bin/env python3
"""
SQLite Database Module for Dogecoin Analyzer
Stores market data, analysis results, and trade executions
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any


class TradingDatabase:
    """SQLite database for storing trading data and analysis."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the database connection.
        
        Args:
            db_path: Path to SQLite database file. If None, uses 'trading_data.db' in current directory.
        """
        if db_path is None:
            db_path = Path(__file__).resolve().parent / "trading_data.db"
        
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Table for market data snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                current_price REAL,
                price_30_days_ago REAL,
                price_change REAL,
                price_change_percent REAL,
                recent_high REAL,
                recent_low REAL,
                volatility_30d REAL,
                volatility_24h REAL,
                price_range_24h REAL,
                ma_7 REAL,
                ma_14 REAL,
                ma_30 REAL,
                avg_volume_30d REAL,
                recent_volume_30d REAL,
                avg_volume_24h REAL,
                best_bid REAL,
                best_ask REAL,
                spread REAL,
                spread_percent REAL,
                volume_imbalance REAL,
                rsi REAL,
                macd REAL,
                macd_signal REAL,
                bb_upper REAL,
                bb_middle REAL,
                bb_lower REAL,
                fear_greed_index INTEGER,
                fear_greed_classification TEXT,
                news_sentiment TEXT,
                technical_indicators_json TEXT,
                order_book_json TEXT,
                portfolio_value REAL,
                usd_percentage REAL,
                doge_percentage REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table for analysis results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                market_data_id INTEGER,
                recommendation TEXT NOT NULL,
                percentage REAL,
                confidence_level TEXT,
                reasoning TEXT,
                risk_assessment TEXT,
                risk_factors_json TEXT,
                portfolio_rebalancing TEXT,
                key_market_factors_json TEXT,
                timing_considerations TEXT,
                analysis_json TEXT,
                chart_image_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (market_data_id) REFERENCES market_data(id)
            )
        """)
        
        # Table for trade executions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                analysis_id INTEGER,
                action TEXT NOT NULL,
                percentage REAL,
                order_id TEXT,
                order_status TEXT,
                amount_usd REAL,
                amount_doge REAL,
                current_price REAL,
                balance_usd_before REAL,
                balance_doge_before REAL,
                balance_usd_after REAL,
                balance_doge_after REAL,
                order_details_json TEXT,
                success INTEGER DEFAULT 0,
                error_message TEXT,
                reflection TEXT,
                decision_correct INTEGER,
                decision_quality_label TEXT,
                decision_quality_score INTEGER,
                reflection_timestamp TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analysis_results(id)
            )
        """)
        
        # Table for once-per-day news cache (SerpAPI cost savings when running every 6 hours)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_cache (
                cache_date TEXT PRIMARY KEY,
                news_data_json TEXT NOT NULL,
                news_sentiment_text TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add new columns to existing table if they don't exist (migration)
        try:
            cursor.execute("ALTER TABLE trade_executions ADD COLUMN reflection TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute("ALTER TABLE trade_executions ADD COLUMN decision_correct INTEGER")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute("ALTER TABLE trade_executions ADD COLUMN reflection_timestamp TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute("ALTER TABLE trade_executions ADD COLUMN decision_quality_label TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute("ALTER TABLE trade_executions ADD COLUMN decision_quality_score INTEGER")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Create indexes for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_data_timestamp ON market_data(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_timestamp ON analysis_results(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_recommendation ON analysis_results(recommendation)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trade_executions(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_action ON trade_executions(action)")
        
        self.conn.commit()
        print(f"✅ Database initialized: {self.db_path}")
    
    def save_market_data(self, market_data: Dict[str, Any]) -> int:
        """
        Save market data snapshot to database.
        
        Args:
            market_data: Dictionary containing market data from prepare_comprehensive_data()
        
        Returns:
            ID of the inserted record
        """
        cursor = self.conn.cursor()
        timestamp = datetime.now().isoformat()
        
        # Extract technical indicators JSON
        tech_indicators = market_data.get('technical_indicators_30d', {})
        tech_indicators_json = json.dumps(tech_indicators) if tech_indicators else None
        
        # Extract order book JSON
        order_book = market_data.get('order_book', {})
        order_book_json = json.dumps(order_book) if order_book else None
        
        # Extract investment status
        investment_status = market_data.get('investment_status', {})
        portfolio_value = investment_status.get('portfolio_value')
        current_allocation = investment_status.get('current_allocation', {})
        usd_percentage = current_allocation.get('usd_percentage')
        doge_percentage = current_allocation.get('doge_percentage')
        
        # Extract fear and greed index
        fear_greed = market_data.get('fear_greed_index', {})
        fear_greed_value = None
        fear_greed_classification = None
        if fear_greed and isinstance(fear_greed, dict):
            current = fear_greed.get('current', {})
            if isinstance(current, dict):
                fear_greed_value = current.get('value')
                fear_greed_classification = current.get('classification')
        
        cursor.execute("""
            INSERT INTO market_data (
                timestamp, current_price, price_30_days_ago, price_change, price_change_percent,
                recent_high, recent_low, volatility_30d, volatility_24h, price_range_24h,
                ma_7, ma_14, ma_30, avg_volume_30d, recent_volume_30d, avg_volume_24h,
                best_bid, best_ask, spread, spread_percent, volume_imbalance,
                rsi, macd, macd_signal, bb_upper, bb_middle, bb_lower,
                fear_greed_index, fear_greed_classification, news_sentiment,
                technical_indicators_json, order_book_json,
                portfolio_value, usd_percentage, doge_percentage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            market_data.get('current_price'),
            market_data.get('price_30_days_ago'),
            market_data.get('price_change'),
            market_data.get('price_change_percent'),
            market_data.get('recent_high'),
            market_data.get('recent_low'),
            market_data.get('volatility_30d'),
            market_data.get('volatility_24h'),
            market_data.get('price_range_24h'),
            market_data.get('moving_averages', {}).get('ma_7'),
            market_data.get('moving_averages', {}).get('ma_14'),
            market_data.get('moving_averages', {}).get('ma_30'),
            market_data.get('volume_analysis', {}).get('avg_volume_30d'),
            market_data.get('volume_analysis', {}).get('recent_volume_30d'),
            market_data.get('volume_analysis', {}).get('avg_volume_24h'),
            market_data.get('order_book', {}).get('best_bid'),
            market_data.get('order_book', {}).get('best_ask'),
            market_data.get('order_book', {}).get('spread'),
            market_data.get('order_book', {}).get('spread_percent'),
            market_data.get('order_book', {}).get('volume_imbalance'),
            tech_indicators.get('rsi'),
            tech_indicators.get('macd'),
            tech_indicators.get('macd_signal'),
            tech_indicators.get('bb_upper'),
            tech_indicators.get('bb_middle'),
            tech_indicators.get('bb_lower'),
            fear_greed_value,
            fear_greed_classification,
            market_data.get('news_sentiment'),
            tech_indicators_json,
            order_book_json,
            portfolio_value,
            usd_percentage,
            doge_percentage
        ))
        
        market_data_id = cursor.lastrowid
        self.conn.commit()
        print(f"✅ Market data saved to database (ID: {market_data_id})")
        return market_data_id
    
    def save_analysis_result(self, analysis_json: Dict[str, Any], market_data_id: Optional[int] = None, 
                           chart_image_path: Optional[str] = None) -> int:
        """
        Save analysis result to database.
        
        Args:
            analysis_json: Dictionary containing the ChatGPT analysis JSON
            market_data_id: ID of the related market_data record
            chart_image_path: Path to the chart screenshot
        
        Returns:
            ID of the inserted record
        """
        cursor = self.conn.cursor()
        timestamp = datetime.now().isoformat()
        
        # Extract fields from analysis JSON
        risk_factors = analysis_json.get('risk_factors', [])
        risk_factors_json = json.dumps(risk_factors) if risk_factors else None
        
        key_market_factors = analysis_json.get('key_market_factors', [])
        key_market_factors_json = json.dumps(key_market_factors) if key_market_factors else None
        
        # Store full analysis JSON
        analysis_json_str = json.dumps(analysis_json)
        
        cursor.execute("""
            INSERT INTO analysis_results (
                timestamp, market_data_id, recommendation, percentage, confidence_level,
                reasoning, risk_assessment, risk_factors_json, portfolio_rebalancing,
                key_market_factors_json, timing_considerations, analysis_json, chart_image_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            market_data_id,
            analysis_json.get('recommendation'),
            analysis_json.get('percentage'),
            analysis_json.get('confidence_level'),
            analysis_json.get('reasoning'),
            analysis_json.get('risk_assessment'),
            risk_factors_json,
            analysis_json.get('portfolio_rebalancing'),
            key_market_factors_json,
            analysis_json.get('timing_considerations'),
            analysis_json_str,
            chart_image_path
        ))
        
        analysis_id = cursor.lastrowid
        self.conn.commit()
        print(f"✅ Analysis result saved to database (ID: {analysis_id})")
        return analysis_id
    
    def save_trade_execution(self, action: str, percentage: float, order_result: Optional[Dict[str, Any]] = None,
                           analysis_id: Optional[int] = None, current_price: Optional[float] = None,
                           balance_usd_before: Optional[float] = None, balance_doge_before: Optional[float] = None,
                           balance_usd_after: Optional[float] = None, balance_doge_after: Optional[float] = None,
                           error_message: Optional[str] = None, reflection: Optional[str] = None,
                           decision_correct: Optional[bool] = None, decision_quality_label: Optional[str] = None,
                           decision_quality_score: Optional[int] = None) -> int:
        """
        Save trade execution to database.
        
        Args:
            action: Trade action (BUY, SELL, HOLD)
            percentage: Percentage of portfolio/balance used
            order_result: Result dictionary from trade execution (contains order_id, status, etc.)
            analysis_id: ID of the related analysis_results record
            current_price: Price at time of trade
            balance_usd_before: USD balance before trade
            balance_doge_before: DOGE balance before trade
            balance_usd_after: USD balance after trade
            balance_doge_after: DOGE balance after trade
            error_message: Error message if trade failed
            reflection: Reflection/remarks on the decision for self-improvement
            decision_correct: Boolean indicating if the decision was correct (True/False/None)
        
        Returns:
            ID of the inserted record
        """
        cursor = self.conn.cursor()
        timestamp = datetime.now().isoformat()
        
        # Extract order details
        order_id = None
        order_status = None
        amount_usd = None
        amount_doge = None
        order_details_json = None

        def _to_float(v):
            if v is None:
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        act = action.upper()

        if order_result and isinstance(order_result, dict):
            # Coinbase Advanced Trade wraps the order in success_response; fill fields are often absent here.
            sr = order_result.get('success_response') or {}
            order_id = (
                sr.get('order_id')
                or order_result.get('order_id')
                or order_result.get('id')
            )
            order_status = sr.get('status') or order_result.get('status')

            filled_size = (
                order_result.get('filled_size')
                or sr.get('filled_size')
                or sr.get('filled_quantity')
            )
            executed_value = (
                order_result.get('executed_value')
                or sr.get('executed_value')
                or sr.get('filled_value')
            )

            filled_f = _to_float(filled_size)
            exec_f = _to_float(executed_value)

            if act == 'BUY':
                amount_usd = exec_f
                amount_doge = filled_f
            elif act == 'SELL':
                amount_doge = filled_f
                amount_usd = exec_f

            order_details_json = json.dumps(order_result)

        # Coinbase market IOC create response often omits fills; sizes are in order_configuration.
        if order_result and isinstance(order_result, dict):
            oc = order_result.get('order_configuration') or {}
            mmc = oc.get('market_market_ioc') or {}
            if act == 'BUY':
                if amount_usd is None:
                    amount_usd = _to_float(mmc.get('quote_size'))
                if amount_doge is None and amount_usd is not None and current_price and current_price > 0:
                    amount_doge = amount_usd / current_price
            elif act == 'SELL':
                if amount_doge is None:
                    amount_doge = _to_float(mmc.get('base_size'))
                if amount_usd is None and amount_doge is not None and current_price and current_price > 0:
                    amount_usd = amount_doge * current_price

        # When the API response omits fills, infer from wallet snapshots (same moment as trade save).
        if act == 'BUY':
            if amount_doge is None and balance_doge_before is not None and balance_doge_after is not None:
                d_doge = balance_doge_after - balance_doge_before
                if d_doge > 1e-10:
                    amount_doge = d_doge
            if amount_usd is None and balance_usd_before is not None and balance_usd_after is not None:
                d_usd = balance_usd_before - balance_usd_after
                if d_usd > 1e-10:
                    amount_usd = d_usd
        elif act == 'SELL':
            if amount_doge is None and balance_doge_before is not None and balance_doge_after is not None:
                d_doge = balance_doge_before - balance_doge_after
                if d_doge > 1e-10:
                    amount_doge = d_doge
            if amount_usd is None and balance_usd_before is not None and balance_usd_after is not None:
                d_usd = balance_usd_after - balance_usd_before
                if d_usd > 1e-10:
                    amount_usd = d_usd

        success = 1 if order_result is not None and error_message is None else 0
        
        # Set reflection timestamp if reflection is provided
        reflection_timestamp = datetime.now().isoformat() if reflection else None
        
        # Convert decision_correct boolean to integer (1 for True, 0 for False, None stays None)
        decision_correct_int = None
        if decision_correct is not None:
            decision_correct_int = 1 if decision_correct else 0
        
        cursor.execute("""
            INSERT INTO trade_executions (
                timestamp, analysis_id, action, percentage, order_id, order_status,
                amount_usd, amount_doge, current_price,
                balance_usd_before, balance_doge_before, balance_usd_after, balance_doge_after,
                order_details_json, success, error_message, reflection, decision_correct, 
                decision_quality_label, decision_quality_score, reflection_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, analysis_id, action, percentage, order_id, order_status,
            amount_usd, amount_doge, current_price,
            balance_usd_before, balance_doge_before, balance_usd_after, balance_doge_after,
            order_details_json, success, error_message, reflection, decision_correct_int,
            decision_quality_label, decision_quality_score, reflection_timestamp
        ))
        
        trade_id = cursor.lastrowid
        self.conn.commit()
        print(f"✅ Trade execution saved to database (ID: {trade_id})")
        return trade_id
    
    def get_recent_analyses(self, limit: int = 10):
        """Get recent analysis results."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM analysis_results 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()
    
    def get_recent_trades(self, limit: int = 10):
        """Get recent trade executions."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM trade_executions 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()
    
    def get_market_data_history(self, limit: int = 100):
        """Get market data history."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM market_data 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()
    
    def update_trade_reflection(self, trade_id: int, reflection: str, decision_correct: Optional[bool] = None,
                               decision_quality_label: Optional[str] = None,
                               decision_quality_score: Optional[int] = None) -> bool:
        """
        Update reflection on a trade execution.
        
        Args:
            trade_id: ID of the trade execution record
            reflection: Reflection/remarks on the decision
            decision_correct: Boolean indicating if the decision was correct (True/False/None)
            decision_quality_label: Granular quality label (e.g., 'extremely_good', 'moderately_bad')
            decision_quality_score: Quality score (-4 to +4)
        
        Returns:
            True if update was successful, False otherwise
        """
        cursor = self.conn.cursor()
        reflection_timestamp = datetime.now().isoformat()
        
        # Convert decision_correct boolean to integer
        decision_correct_int = None
        if decision_correct is not None:
            decision_correct_int = 1 if decision_correct else 0
        
        cursor.execute("""
            UPDATE trade_executions 
            SET reflection = ?, decision_correct = ?, decision_quality_label = ?, 
                decision_quality_score = ?, reflection_timestamp = ?
            WHERE id = ?
        """, (reflection, decision_correct_int, decision_quality_label, decision_quality_score, 
              reflection_timestamp, trade_id))
        
        if cursor.rowcount > 0:
            self.conn.commit()
            print(f"✅ Trade reflection updated (Trade ID: {trade_id})")
            return True
        else:
            print(f"⚠️  Trade ID {trade_id} not found")
            return False
    
    def get_trades_needing_reflection(self, limit: int = 10):
        """
        Get trades that don't have a reflection yet.
        
        Args:
            limit: Maximum number of trades to return
        
        Returns:
            List of trade execution records without reflections
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM trade_executions 
            WHERE reflection IS NULL OR reflection = ''
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()
    
    def get_trade_by_id(self, trade_id: int):
        """
        Get a specific trade execution by ID.
        
        Args:
            trade_id: ID of the trade execution record
        
        Returns:
            Trade execution record or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM trade_executions 
            WHERE id = ?
        """, (trade_id,))
        return cursor.fetchone()
    
    def get_analysis_by_id(self, analysis_id: int):
        """
        Get a specific analysis result by ID.
        
        Args:
            analysis_id: ID of the analysis_results record
        
        Returns:
            Analysis result record or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM analysis_results 
            WHERE id = ?
        """, (analysis_id,))
        return cursor.fetchone()
    
    def get_market_data_by_id(self, market_data_id: int):
        """
        Get a specific market data snapshot by ID.
        
        Args:
            market_data_id: ID of the market_data record
        
        Returns:
            Market data record or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM market_data 
            WHERE id = ?
        """, (market_data_id,))
        return cursor.fetchone()
    
    def get_cached_news_for_date(self, cache_date: str):
        """
        Get cached news and sentiment for a calendar date (YYYY-MM-DD).
        Used to avoid SerpAPI cost when running mvp.py every 6 hours.
        
        Returns:
            Tuple of (news_data dict, news_sentiment str) or (None, None) if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT news_data_json, news_sentiment_text FROM news_cache WHERE cache_date = ?
        """, (cache_date,))
        row = cursor.fetchone()
        if not row:
            return None, None
        try:
            news_data = json.loads(row[0]) if row[0] else None
            news_sentiment = row[1] if row[1] else None
            return news_data, news_sentiment
        except (json.JSONDecodeError, TypeError):
            return None, None
    
    def save_news_cache(self, cache_date: str, news_data: Dict[str, Any], news_sentiment: Optional[str] = None):
        """Save news data and sentiment for a calendar date (YYYY-MM-DD)."""
        cursor = self.conn.cursor()
        news_json = json.dumps(news_data) if news_data else "{}"
        cursor.execute("""
            INSERT OR REPLACE INTO news_cache (cache_date, news_data_json, news_sentiment_text, created_at)
            VALUES (?, ?, ?, ?)
        """, (cache_date, news_json, news_sentiment, datetime.now().isoformat()))
        self.conn.commit()
    
    def get_all_trades(self, days: Optional[int] = None):
        """
        Get all trade executions, optionally filtered by days.
        
        Args:
            days: If provided, only return trades from the last N days
        
        Returns:
            List of trade execution records, ordered by timestamp (oldest first)
        """
        cursor = self.conn.cursor()
        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            cursor.execute("""
                SELECT * FROM trade_executions 
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            """, (cutoff_date.isoformat(),))
        else:
            cursor.execute("""
                SELECT * FROM trade_executions 
                ORDER BY timestamp ASC
            """)
        return cursor.fetchall()
    
    def get_labeled_trades_with_indicators(self, limit: int = 100):
        """
        JOIN trade_executions → analysis_results → market_data to return labeled
        trades alongside the indicator conditions that existed at decision time.
        Only returns BUY/SELL rows that have been quality-labeled.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                te.id            AS trade_id,
                te.timestamp     AS trade_ts,
                te.action,
                te.percentage    AS trade_pct,
                te.current_price AS trade_price,
                te.decision_correct,
                te.decision_quality_label,
                te.decision_quality_score,
                md.rsi,
                md.bb_upper,
                md.bb_middle,
                md.bb_lower,
                md.fear_greed_index,
                md.volume_imbalance,
                md.technical_indicators_json
            FROM trade_executions te
            JOIN analysis_results ar ON te.analysis_id = ar.id
            JOIN market_data md     ON ar.market_data_id = md.id
            WHERE te.decision_quality_label IS NOT NULL
              AND te.action IN ('BUY', 'SELL')
            ORDER BY te.timestamp DESC
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()

    def close(self):
        """Close database connection."""
        self.conn.close()
        print("✅ Database connection closed")

