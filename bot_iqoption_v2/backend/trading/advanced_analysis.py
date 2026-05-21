"""
Advanced Analysis Module
Provides enhanced analysis capabilities including:
- Multi-timeframe analysis
- Asset correlation detection
- Trend detection
- Volume analysis
- Smart asset selection
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import statistics
from collections import defaultdict

logger = logging.getLogger(__name__)


# Asset correlation groups - assets that tend to move together
CORRELATION_GROUPS = {
    'EUR_PAIRS': ['EURUSD', 'EURGBP', 'EURJPY', 'EURAUD', 'EURCHF', 'EURNZD', 'EURCAD',
                  'EURUSD-OTC', 'EURGBP-OTC', 'EURJPY-OTC', 'EURAUD-OTC', 'EURCHF-OTC'],
    'USD_PAIRS': ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'AUDUSD', 'NZDUSD',
                  'EURUSD-OTC', 'GBPUSD-OTC', 'USDJPY-OTC', 'USDCHF-OTC', 'USDCAD-OTC'],
    'GBP_PAIRS': ['GBPUSD', 'EURGBP', 'GBPJPY', 'GBPAUD', 'GBPCAD', 'GBPCHF', 'GBPNZD',
                  'GBPUSD-OTC', 'EURGBP-OTC', 'GBPJPY-OTC', 'GBPAUD-OTC', 'GBPCAD-OTC'],
    'JPY_PAIRS': ['USDJPY', 'EURJPY', 'GBPJPY', 'AUDJPY', 'CADJPY', 'CHFJPY', 'NZDJPY',
                  'USDJPY-OTC', 'EURJPY-OTC', 'GBPJPY-OTC', 'AUDJPY-OTC', 'CADJPY-OTC'],
    'COMMODITIES': ['XAUUSD', 'XAGUSD', 'XAUUSD-OTC', 'XAGUSD-OTC'],
    'CRYPTO': ['BTCUSD', 'ETHUSD', 'LTCUSD'],
}


class TrendAnalyzer:
    """Analyzes market trends across multiple timeframes"""
    
    TREND_UP = 'UP'
    TREND_DOWN = 'DOWN'
    TREND_SIDEWAYS = 'SIDEWAYS'
    
    @staticmethod
    def calculate_trend(candles: List[Dict], lookback: int = 20) -> Tuple[str, float]:
        """
        Calculate trend direction and strength
        Returns: (trend_direction, strength_percentage)
        """
        if not candles or len(candles) < lookback:
            return TrendAnalyzer.TREND_SIDEWAYS, 0.0
        
        recent_candles = candles[-lookback:]
        closes = [float(c.get('close', c.get('close_price', 0))) for c in recent_candles]
        
        if len(closes) < 2:
            return TrendAnalyzer.TREND_SIDEWAYS, 0.0
        
        # Calculate simple linear regression slope
        n = len(closes)
        sum_x = sum(range(n))
        sum_y = sum(closes)
        sum_xy = sum(i * closes[i] for i in range(n))
        sum_x2 = sum(i * i for i in range(n))
        
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return TrendAnalyzer.TREND_SIDEWAYS, 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        
        # Calculate strength based on slope relative to price
        avg_price = sum_y / n
        if avg_price == 0:
            return TrendAnalyzer.TREND_SIDEWAYS, 0.0
        
        # Normalize slope as percentage of average price
        strength = abs(slope / avg_price) * 100 * n
        strength = min(strength, 100)  # Cap at 100%
        
        if slope > 0.00001:
            return TrendAnalyzer.TREND_UP, strength
        elif slope < -0.00001:
            return TrendAnalyzer.TREND_DOWN, strength
        else:
            return TrendAnalyzer.TREND_SIDEWAYS, strength
    
    @staticmethod
    def get_support_resistance(candles: List[Dict], lookback: int = 50) -> Dict:
        """Calculate support and resistance levels"""
        if not candles or len(candles) < lookback:
            return {'support': None, 'resistance': None}
        
        recent_candles = candles[-lookback:]
        highs = [float(c.get('high', c.get('high_price', 0))) for c in recent_candles]
        lows = [float(c.get('low', c.get('low_price', 0))) for c in recent_candles]
        
        return {
            'support': min(lows) if lows else None,
            'resistance': max(highs) if highs else None,
            'avg_high': statistics.mean(highs) if highs else None,
            'avg_low': statistics.mean(lows) if lows else None,
        }


class MultiTimeframeAnalyzer:
    """Analyzes signals across multiple timeframes for confirmation"""
    
    def __init__(self, api):
        self.api = api
        self.trend_analyzer = TrendAnalyzer()
    
    def analyze_multi_timeframe(self, asset: str, timeframes: List[int] = None) -> Dict:
        """
        Analyze asset across multiple timeframes
        timeframes: list of timeframe in seconds (e.g., [60, 300, 900] for M1, M5, M15)
        """
        if timeframes is None:
            timeframes = [60, 300]  # Default: M1 and M5
        
        results = {
            'asset': asset,
            'timeframes': {},
            'consensus': None,
            'strength': 0,
            'recommendation': None
        }
        
        trends = []
        strengths = []
        
        for tf in timeframes:
            try:
                candles = self.api.get_candles(asset, tf, 50)
                if candles:
                    trend, strength = self.trend_analyzer.calculate_trend(candles)
                    sr_levels = self.trend_analyzer.get_support_resistance(candles)
                    
                    results['timeframes'][tf] = {
                        'trend': trend,
                        'strength': round(strength, 2),
                        'support': sr_levels['support'],
                        'resistance': sr_levels['resistance'],
                    }
                    
                    trends.append(trend)
                    strengths.append(strength)
            except Exception as e:
                logger.warning(f"Error analyzing {asset} on timeframe {tf}: {e}")
                results['timeframes'][tf] = {'error': str(e)}
        
        # Calculate consensus
        if trends:
            up_count = trends.count(TrendAnalyzer.TREND_UP)
            down_count = trends.count(TrendAnalyzer.TREND_DOWN)
            
            if up_count > down_count and up_count > len(trends) / 2:
                results['consensus'] = TrendAnalyzer.TREND_UP
                results['recommendation'] = 'CALL'
            elif down_count > up_count and down_count > len(trends) / 2:
                results['consensus'] = TrendAnalyzer.TREND_DOWN
                results['recommendation'] = 'PUT'
            else:
                results['consensus'] = TrendAnalyzer.TREND_SIDEWAYS
                results['recommendation'] = 'WAIT'
            
            results['strength'] = round(statistics.mean(strengths), 2) if strengths else 0
        
        return results


class CorrelationManager:
    """Manages asset correlations to avoid over-exposure"""
    
    def __init__(self):
        self.active_positions = defaultdict(list)  # group -> [assets]
    
    def get_correlation_group(self, asset: str) -> Optional[str]:
        """Get the correlation group for an asset"""
        asset_upper = asset.upper()
        for group, assets in CORRELATION_GROUPS.items():
            if asset_upper in [a.upper() for a in assets]:
                return group
        return None
    
    def can_trade_asset(self, asset: str, max_per_group: int = 2) -> Tuple[bool, str]:
        """
        Check if we can trade this asset without over-exposure
        Returns: (can_trade, reason)
        """
        group = self.get_correlation_group(asset)
        if not group:
            return True, "Asset não pertence a grupo correlacionado"
        
        current_count = len(self.active_positions.get(group, []))
        if current_count >= max_per_group:
            return False, f"Limite de {max_per_group} ativos do grupo {group} atingido"
        
        return True, "OK"
    
    def add_position(self, asset: str):
        """Register a new position"""
        group = self.get_correlation_group(asset)
        if group:
            if asset not in self.active_positions[group]:
                self.active_positions[group].append(asset)
    
    def remove_position(self, asset: str):
        """Remove a closed position"""
        group = self.get_correlation_group(asset)
        if group and asset in self.active_positions[group]:
            self.active_positions[group].remove(asset)
    
    def get_active_correlations(self) -> Dict:
        """Get current correlation exposure"""
        return dict(self.active_positions)


class SmartAssetSelector:
    """Intelligently selects the best asset to trade based on multiple factors"""
    
    def __init__(self, api, user):
        self.api = api
        self.user = user
        self.mtf_analyzer = MultiTimeframeAnalyzer(api)
        self.correlation_manager = CorrelationManager()
    
    def get_best_assets(
        self,
        catalog_results: List[Dict],
        min_win_rate: float = 60.0,
        min_gale1_rate: float = 75.0,
        max_results: int = 5,
        check_trend: bool = True,
        check_correlation: bool = True
    ) -> List[Dict]:
        """
        Select the best assets to trade based on:
        - Win rate from catalog
        - Gale rates
        - Multi-timeframe trend alignment
        - Correlation exposure
        """
        candidates = []
        
        for result in catalog_results:
            win_rate = float(result.get('win_rate', 0))
            gale1_rate = float(result.get('gale1_rate', 0))
            
            # Filter by minimum rates
            if win_rate < min_win_rate:
                continue
            if gale1_rate < min_gale1_rate:
                continue
            
            asset = result.get('asset', '')
            strategy = result.get('strategy', '')
            
            # Check correlation
            if check_correlation:
                can_trade, reason = self.correlation_manager.can_trade_asset(asset)
                if not can_trade:
                    logger.debug(f"Skipping {asset}: {reason}")
                    continue
            
            # Calculate composite score
            score = self._calculate_score(result)
            
            # Check trend alignment if requested
            trend_data = None
            if check_trend:
                try:
                    trend_data = self.mtf_analyzer.analyze_multi_timeframe(asset)
                    # Boost score if trend is strong and aligned
                    if trend_data.get('strength', 0) > 50:
                        score *= 1.2
                except Exception as e:
                    logger.warning(f"Error checking trend for {asset}: {e}")
            
            candidates.append({
                'asset': asset,
                'strategy': strategy,
                'win_rate': win_rate,
                'gale1_rate': gale1_rate,
                'gale2_rate': float(result.get('gale2_rate', 0)),
                'gale3_rate': float(result.get('gale3_rate', 0)),
                'total_samples': result.get('total_samples', 0),
                'score': round(score, 2),
                'trend': trend_data,
                'analyzed_at': result.get('analyzed_at'),
            })
        
        # Sort by score descending
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        return candidates[:max_results]
    
    def _calculate_score(self, result: Dict) -> float:
        """Calculate a composite score for an asset"""
        win_rate = float(result.get('win_rate', 0))
        gale1_rate = float(result.get('gale1_rate', 0))
        gale2_rate = float(result.get('gale2_rate', 0))
        gale3_rate = float(result.get('gale3_rate', 0))
        samples = result.get('total_samples', 0)
        
        # Base score from win rate
        score = win_rate * 1.0
        
        # Bonus for high gale rates (recovery potential)
        if gale1_rate >= 80:
            score += 10
        if gale2_rate >= 90:
            score += 5
        if gale3_rate >= 95:
            score += 3
        
        # Bonus for sample size (reliability)
        if samples >= 30:
            score += 5
        elif samples >= 20:
            score += 3
        elif samples < 10:
            score -= 10  # Penalty for low sample size
        
        return score


class TradingScheduler:
    """Manages trading schedules and allowed trading hours"""
    
    # Best trading hours by session (UTC)
    TRADING_SESSIONS = {
        'ASIAN': {'start': 0, 'end': 8, 'pairs': ['USDJPY', 'EURJPY', 'GBPJPY', 'AUDJPY', 'AUDUSD', 'NZDUSD']},
        'EUROPEAN': {'start': 7, 'end': 16, 'pairs': ['EURUSD', 'EURGBP', 'GBPUSD', 'EURJPY', 'EURCHF', 'GBPCHF']},
        'AMERICAN': {'start': 13, 'end': 22, 'pairs': ['EURUSD', 'GBPUSD', 'USDCAD', 'USDJPY', 'USDCHF']},
        'OTC': {'start': 0, 'end': 24, 'pairs': []},  # OTC available 24/7
    }
    
    @staticmethod
    def get_current_session() -> List[str]:
        """Get current active trading sessions"""
        current_hour = datetime.utcnow().hour
        active_sessions = []
        
        for session, info in TradingScheduler.TRADING_SESSIONS.items():
            if info['start'] <= current_hour < info['end']:
                active_sessions.append(session)
        
        return active_sessions
    
    @staticmethod
    def is_good_time_for_asset(asset: str) -> Tuple[bool, str]:
        """Check if current time is good for trading this asset"""
        if '-OTC' in asset.upper():
            return True, "OTC disponível 24/7"
        
        current_sessions = TradingScheduler.get_current_session()
        asset_upper = asset.upper()
        
        for session in current_sessions:
            session_info = TradingScheduler.TRADING_SESSIONS.get(session, {})
            recommended_pairs = session_info.get('pairs', [])
            
            if asset_upper in [p.upper() for p in recommended_pairs]:
                return True, f"Ativo recomendado para sessão {session}"
        
        if current_sessions:
            return True, f"Sessão ativa: {', '.join(current_sessions)}"
        
        return False, "Fora do horário recomendado de trading"
    
    @staticmethod
    def get_recommended_assets() -> List[str]:
        """Get list of recommended assets for current time"""
        current_sessions = TradingScheduler.get_current_session()
        recommended = set()
        
        for session in current_sessions:
            session_info = TradingScheduler.TRADING_SESSIONS.get(session, {})
            recommended.update(session_info.get('pairs', []))
        
        return list(recommended)


class ConsecutiveLossTracker:
    """Tracks consecutive losses and implements safety stops"""
    
    def __init__(self, max_consecutive_losses: int = 3):
        self.max_consecutive_losses = max_consecutive_losses
        self.consecutive_losses = 0
        self.total_losses_today = 0
        self.last_reset_date = datetime.utcnow().date()
    
    def record_result(self, is_win: bool) -> Tuple[bool, str]:
        """
        Record a trade result
        Returns: (should_continue, message)
        """
        # Reset daily counter if new day
        today = datetime.utcnow().date()
        if today != self.last_reset_date:
            self.total_losses_today = 0
            self.last_reset_date = today
        
        if is_win:
            self.consecutive_losses = 0
            return True, "Vitória registrada"
        else:
            self.consecutive_losses += 1
            self.total_losses_today += 1
            
            if self.consecutive_losses >= self.max_consecutive_losses:
                return False, f"Stop por {self.consecutive_losses} perdas consecutivas"
            
            return True, f"Perda {self.consecutive_losses}/{self.max_consecutive_losses}"
    
    def reset(self):
        """Reset consecutive loss counter"""
        self.consecutive_losses = 0
    
    def get_status(self) -> Dict:
        """Get current status"""
        return {
            'consecutive_losses': self.consecutive_losses,
            'max_consecutive_losses': self.max_consecutive_losses,
            'total_losses_today': self.total_losses_today,
            'can_continue': self.consecutive_losses < self.max_consecutive_losses
        }


class AssetBlacklist:
    """Manages blacklisted assets that should not be traded"""
    
    def __init__(self):
        self.blacklist = set()
        self.temporary_blacklist = {}  # asset -> expiry_time
    
    def add_to_blacklist(self, asset: str, temporary: bool = False, duration_minutes: int = 60):
        """Add asset to blacklist"""
        asset_upper = asset.upper()
        if temporary:
            expiry = datetime.utcnow() + timedelta(minutes=duration_minutes)
            self.temporary_blacklist[asset_upper] = expiry
        else:
            self.blacklist.add(asset_upper)
    
    def remove_from_blacklist(self, asset: str):
        """Remove asset from blacklist"""
        asset_upper = asset.upper()
        self.blacklist.discard(asset_upper)
        self.temporary_blacklist.pop(asset_upper, None)
    
    def is_blacklisted(self, asset: str) -> Tuple[bool, str]:
        """Check if asset is blacklisted"""
        asset_upper = asset.upper()
        
        if asset_upper in self.blacklist:
            return True, "Ativo na blacklist permanente"
        
        if asset_upper in self.temporary_blacklist:
            expiry = self.temporary_blacklist[asset_upper]
            if datetime.utcnow() < expiry:
                remaining = (expiry - datetime.utcnow()).seconds // 60
                return True, f"Ativo bloqueado temporariamente ({remaining} min restantes)"
            else:
                # Expired, remove from temporary blacklist
                del self.temporary_blacklist[asset_upper]
        
        return False, "OK"
    
    def get_blacklist(self) -> Dict:
        """Get current blacklist status"""
        # Clean expired temporary entries
        now = datetime.utcnow()
        expired = [a for a, exp in self.temporary_blacklist.items() if now >= exp]
        for a in expired:
            del self.temporary_blacklist[a]
        
        return {
            'permanent': list(self.blacklist),
            'temporary': {
                asset: expiry.isoformat()
                for asset, expiry in self.temporary_blacklist.items()
            }
        }


# Singleton instances for use across the application
_correlation_managers = {}
_loss_trackers = {}
_blacklists = {}


def get_correlation_manager(user_id: int) -> CorrelationManager:
    """Get or create correlation manager for user"""
    if user_id not in _correlation_managers:
        _correlation_managers[user_id] = CorrelationManager()
    return _correlation_managers[user_id]


def get_loss_tracker(user_id: int, max_losses: int = 3) -> ConsecutiveLossTracker:
    """Get or create loss tracker for user"""
    if user_id not in _loss_trackers:
        _loss_trackers[user_id] = ConsecutiveLossTracker(max_losses)
    return _loss_trackers[user_id]


def get_blacklist(user_id: int) -> AssetBlacklist:
    """Get or create blacklist for user"""
    if user_id not in _blacklists:
        _blacklists[user_id] = AssetBlacklist()
    return _blacklists[user_id]
