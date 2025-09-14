"""
Candlestick Patterns Strategy - Padrões de Candlestick
Detecta múltiplos padrões de candlestick para sinais de entrada.

Padrões implementados:
1. Martelo (Hammer) - CALL
2. Martelo Invertido (Inverted Hammer) - CALL  
3. Shooting Star - PUT
4. Doji - Reversão (depende da tendência)
5. Pin Bar - Direção baseada na posição do pavio
6. Marubozu - Continuação da tendência
"""

import time
from typing import Optional, Dict, Any, List
from datetime import datetime


class CandlestickStrategy:
    """Estratégia de Padrões de Candlestick - Múltiplos padrões de reversão e continuação"""
    
    def __init__(self, api, config, session, log_callback=None):
        self.api = api
        self.config = config
        self.session = session
        self._log = log_callback or (lambda msg, level: print(f"[{level}] {msg}"))
        self.running = False
    
    def start(self):
        """Start the strategy"""
        self.running = True
    
    def stop(self):
        """Stop the strategy"""
        self.running = False
    
    def analyze(self, asset: str) -> Optional[str]:
        """
        Analyze candlestick patterns for given asset
        Returns: 'call', 'put', or None
        """
        try:
            # Get configuration parameters
            timeframe = getattr(self.config, 'candlestick_timeframe', 60)  # Default M1
            patterns = getattr(self.config, 'candlestick_patterns', ['hammer', 'shooting_star', 'doji', 'pin_bar'])
            min_body_ratio = getattr(self.config, 'candlestick_min_body_ratio', 0.3)
            shadow_body_ratio = getattr(self.config, 'candlestick_shadow_body_ratio', 2.0)
            
            # Get last 5 candles for trend analysis and pattern detection
            candles = self.api.get_candles(asset, timeframe, 5)
            if not candles or len(candles) < 3:
                self._log(f"Dados insuficientes para análise Candlestick: {len(candles) if candles else 0} velas", "WARNING")
                return None
            
            # Current candle for pattern analysis
            current_candle = candles[-1]
            
            # Validate candle data
            if not self._validate_candle_data(current_candle):
                self._log("Dados de vela inválidos para análise Candlestick", "WARNING")
                return None
            
            # Analyze trend from previous candles
            trend = self._analyze_trend(candles[:-1])  # Exclude current candle
            
            # Detect patterns
            detected_patterns = []
            
            if 'hammer' in patterns:
                if self._detect_hammer(current_candle):
                    detected_patterns.append(('hammer', 'call'))
            
            if 'inverted_hammer' in patterns:
                if self._detect_inverted_hammer(current_candle):
                    detected_patterns.append(('inverted_hammer', 'call'))
            
            if 'shooting_star' in patterns:
                if self._detect_shooting_star(current_candle):
                    detected_patterns.append(('shooting_star', 'put'))
            
            if 'doji' in patterns:
                doji_signal = self._detect_doji(current_candle, trend)
                if doji_signal:
                    detected_patterns.append(('doji', doji_signal))
            
            if 'pin_bar' in patterns:
                pin_signal = self._detect_pin_bar(current_candle)
                if pin_signal:
                    detected_patterns.append(('pin_bar', pin_signal))
            
            if 'marubozu' in patterns:
                marubozu_signal = self._detect_marubozu(current_candle, trend)
                if marubozu_signal:
                    detected_patterns.append(('marubozu', marubozu_signal))
            
            # Return signal from highest priority pattern
            if detected_patterns:
                pattern_name, signal = detected_patterns[0]  # First detected pattern
                self._log(f"Padrão {pattern_name.upper()} detectado -> {signal.upper()}", "INFO")
                return signal
            
            return None
            
        except Exception as e:
            self._log(f"Erro na análise Candlestick: {str(e)}", "ERROR")
            return None
    
    def _validate_candle_data(self, candle: Dict[str, Any]) -> bool:
        """Validate candle has required OHLC data"""
        required_keys = ['open', 'high', 'low', 'close']
        return all(key in candle and candle[key] is not None for key in required_keys)
    
    def _analyze_trend(self, candles: List[Dict[str, Any]]) -> str:
        """
        Analyze trend from previous candles
        Returns: 'bullish', 'bearish', or 'neutral'
        """
        if len(candles) < 3:
            return 'neutral'
        
        # Simple trend analysis using closes
        closes = [c['close'] for c in candles[-3:]]
        
        if closes[-1] > closes[-2] > closes[-3]:
            return 'bullish'
        elif closes[-1] < closes[-2] < closes[-3]:
            return 'bearish'
        else:
            return 'neutral'
    
    def _calculate_candle_metrics(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Calculate candle body, shadows, and ratios"""
        open_price = candle['open']
        high_price = candle['high']
        low_price = candle['low']
        close_price = candle['close']
        
        # Body size and direction
        body_size = abs(close_price - open_price)
        is_bullish = close_price > open_price
        
        # Shadow sizes
        if is_bullish:
            upper_shadow = high_price - close_price
            lower_shadow = open_price - low_price
        else:
            upper_shadow = high_price - open_price
            lower_shadow = close_price - low_price
        
        # Total range
        total_range = high_price - low_price
        
        return {
            'body_size': body_size,
            'upper_shadow': upper_shadow,
            'lower_shadow': lower_shadow,
            'total_range': total_range,
            'is_bullish': is_bullish,
            'body_ratio': body_size / total_range if total_range > 0 else 0
        }
    
    def _detect_hammer(self, candle: Dict[str, Any]) -> bool:
        """
        Detect Hammer pattern
        - Small body at top of range
        - Long lower shadow (2x body size)
        - Little to no upper shadow
        """
        metrics = self._calculate_candle_metrics(candle)
        
        # Long lower shadow (at least 2x body size)
        long_lower_shadow = metrics['lower_shadow'] >= (metrics['body_size'] * 2.0)
        
        # Short upper shadow (less than 50% of body)
        short_upper_shadow = metrics['upper_shadow'] <= (metrics['body_size'] * 0.5)
        
        # Body should be in upper part of range
        body_at_top = metrics['body_size'] > 0 and metrics['upper_shadow'] <= metrics['lower_shadow'] * 0.3
        
        return long_lower_shadow and short_upper_shadow and body_at_top
    
    def _detect_inverted_hammer(self, candle: Dict[str, Any]) -> bool:
        """
        Detect Inverted Hammer pattern
        - Small body at bottom of range
        - Long upper shadow (2x body size)
        - Little to no lower shadow
        """
        metrics = self._calculate_candle_metrics(candle)
        
        # Long upper shadow (at least 2x body size)
        long_upper_shadow = metrics['upper_shadow'] >= (metrics['body_size'] * 2.0)
        
        # Short lower shadow (less than 50% of body)
        short_lower_shadow = metrics['lower_shadow'] <= (metrics['body_size'] * 0.5)
        
        # Body should be in lower part of range
        body_at_bottom = metrics['body_size'] > 0 and metrics['lower_shadow'] <= metrics['upper_shadow'] * 0.3
        
        return long_upper_shadow and short_lower_shadow and body_at_bottom
    
    def _detect_shooting_star(self, candle: Dict[str, Any]) -> bool:
        """
        Detect Shooting Star pattern
        - Small body at bottom of range
        - Long upper shadow (2x body size)
        - Little to no lower shadow
        - Bearish signal
        """
        metrics = self._calculate_candle_metrics(candle)
        
        # Long upper shadow (at least 2x body size)
        long_upper_shadow = metrics['upper_shadow'] >= (metrics['body_size'] * 2.0)
        
        # Short lower shadow (less than 30% of body)
        short_lower_shadow = metrics['lower_shadow'] <= (metrics['body_size'] * 0.3)
        
        # Small body (less than 30% of total range)
        small_body = metrics['body_ratio'] <= 0.3
        
        return long_upper_shadow and short_lower_shadow and small_body
    
    def _detect_doji(self, candle: Dict[str, Any], trend: str) -> Optional[str]:
        """
        Detect Doji pattern
        - Very small body (open ≈ close)
        - Indicates indecision and potential reversal
        """
        metrics = self._calculate_candle_metrics(candle)
        
        # Very small body (less than 10% of total range)
        is_doji = metrics['body_ratio'] <= 0.1 and metrics['total_range'] > 0
        
        if not is_doji:
            return None
        
        # Signal based on trend reversal
        if trend == 'bullish':
            return 'put'  # Reversal from bullish trend
        elif trend == 'bearish':
            return 'call'  # Reversal from bearish trend
        else:
            return None  # No clear trend to reverse
    
    def _detect_pin_bar(self, candle: Dict[str, Any]) -> Optional[str]:
        """
        Detect Pin Bar pattern
        - Long shadow on one side (2x body size)
        - Small body
        - Direction based on shadow position
        """
        metrics = self._calculate_candle_metrics(candle)
        
        # Small body (less than 40% of total range)
        small_body = metrics['body_ratio'] <= 0.4
        
        if not small_body:
            return None
        
        # Long lower shadow = bullish pin bar
        if metrics['lower_shadow'] >= (metrics['body_size'] * 2.0) and metrics['upper_shadow'] <= (metrics['body_size'] * 0.5):
            return 'call'
        
        # Long upper shadow = bearish pin bar
        elif metrics['upper_shadow'] >= (metrics['body_size'] * 2.0) and metrics['lower_shadow'] <= (metrics['body_size'] * 0.5):
            return 'put'
        
        return None
    
    def _detect_marubozu(self, candle: Dict[str, Any], trend: str) -> Optional[str]:
        """
        Detect Marubozu pattern
        - Large body with little to no shadows
        - Continuation pattern
        """
        metrics = self._calculate_candle_metrics(candle)
        
        # Large body (more than 80% of total range)
        large_body = metrics['body_ratio'] >= 0.8
        
        # Very small shadows
        small_shadows = (metrics['upper_shadow'] + metrics['lower_shadow']) <= (metrics['body_size'] * 0.1)
        
        if not (large_body and small_shadows):
            return None
        
        # Continuation signal based on candle direction
        if metrics['is_bullish']:
            return 'call'
        else:
            return 'put'
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Return strategy information"""
        return {
            'name': 'Padrões de Candlestick',
            'description': 'Detecta múltiplos padrões de candlestick (Martelo, Doji, Pin Bar, etc.)',
            'timeframes': ['M1', 'M5'],
            'patterns': ['Hammer', 'Inverted Hammer', 'Shooting Star', 'Doji', 'Pin Bar', 'Marubozu'],
            'parameters': {
                'candlestick_timeframe': 60,
                'candlestick_patterns': ['hammer', 'shooting_star', 'doji', 'pin_bar'],
                'candlestick_min_body_ratio': 0.3,
                'candlestick_shadow_body_ratio': 2.0
            }
        }
