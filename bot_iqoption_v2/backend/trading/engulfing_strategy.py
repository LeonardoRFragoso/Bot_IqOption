"""
Engulfing Strategy - Padrão de Engolfo
Analisa padrões de engolfo bullish e bearish em 2 candles consecutivos.

Engolfo Bullish (CALL):
- Primeira vela: Vermelha (close < open)
- Segunda vela: Verde (close > open) 
- Segunda vela engolfa completamente a primeira (open2 < close1 e close2 > open1)

Engolfo Bearish (PUT):
- Primeira vela: Verde (close > open)
- Segunda vela: Vermelha (close < open)
- Segunda vela engolfa completamente a primeira (open2 > close1 e close2 < open1)
"""

import time
from typing import Optional, Dict, Any
from datetime import datetime


class EngulfingStrategy:
    """Estratégia de Engolfo - Análise de padrões de engolfo em 2 candles"""
    
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
        Analyze engulfing pattern for given asset
        Returns: 'call', 'put', or None
        """
        try:
            # Get configuration parameters
            timeframe = getattr(self.config, 'engulfing_timeframe', 60)  # Default M1
            min_body_size = getattr(self.config, 'engulfing_min_body_size', 0.0001)
            volume_filter = getattr(self.config, 'engulfing_volume_filter', False)
            
            # Get last 3 candles (need 2 for analysis + 1 buffer)
            candles = self.api.get_candles(asset, timeframe, 3)
            if not candles or len(candles) < 2:
                self._log(f"Dados insuficientes para análise Engolfo: {len(candles) if candles else 0} velas", "WARNING")
                return None
            
            # Get the last 2 completed candles
            candle1 = candles[-2]  # Previous candle
            candle2 = candles[-1]  # Current candle
            
            # Validate candle data
            if not self._validate_candle_data(candle1) or not self._validate_candle_data(candle2):
                self._log("Dados de velas inválidos para análise Engolfo", "WARNING")
                return None
            
            # Calculate body sizes
            body1_size = abs(candle1['close'] - candle1['open'])
            body2_size = abs(candle2['close'] - candle2['open'])
            
            # Filter out very small bodies
            if body1_size < min_body_size or body2_size < min_body_size:
                return None
            
            # Detect engulfing patterns
            bullish_engulfing = self._detect_bullish_engulfing(candle1, candle2)
            bearish_engulfing = self._detect_bearish_engulfing(candle1, candle2)
            
            if bullish_engulfing:
                self._log(f"Engolfo Bullish detectado | Vela1: {candle1['open']:.5f}->{candle1['close']:.5f} | Vela2: {candle2['open']:.5f}->{candle2['close']:.5f}", "INFO")
                return 'call'
            elif bearish_engulfing:
                self._log(f"Engolfo Bearish detectado | Vela1: {candle1['open']:.5f}->{candle1['close']:.5f} | Vela2: {candle2['open']:.5f}->{candle2['close']:.5f}", "INFO")
                return 'put'
            
            return None
            
        except Exception as e:
            self._log(f"Erro na análise Engolfo: {str(e)}", "ERROR")
            return None
    
    def _validate_candle_data(self, candle: Dict[str, Any]) -> bool:
        """Validate candle has required OHLC data"""
        required_keys = ['open', 'high', 'low', 'close']
        return all(key in candle and candle[key] is not None for key in required_keys)
    
    def _detect_bullish_engulfing(self, candle1: Dict[str, Any], candle2: Dict[str, Any]) -> bool:
        """
        Detect bullish engulfing pattern
        - First candle: Bearish (red)
        - Second candle: Bullish (green) and completely engulfs first candle
        """
        # First candle must be bearish (red)
        first_bearish = candle1['close'] < candle1['open']
        
        # Second candle must be bullish (green)
        second_bullish = candle2['close'] > candle2['open']
        
        # Second candle must completely engulf first candle
        # Second open < First close AND Second close > First open
        engulfs = (candle2['open'] < candle1['close'] and 
                   candle2['close'] > candle1['open'])
        
        # Additional validation: second candle body should be significantly larger
        body1_size = abs(candle1['close'] - candle1['open'])
        body2_size = abs(candle2['close'] - candle2['open'])
        size_ratio = body2_size / body1_size if body1_size > 0 else 0
        
        # Require second candle to be at least 20% larger
        significant_size = size_ratio >= 1.2
        
        return first_bearish and second_bullish and engulfs and significant_size
    
    def _detect_bearish_engulfing(self, candle1: Dict[str, Any], candle2: Dict[str, Any]) -> bool:
        """
        Detect bearish engulfing pattern  
        - First candle: Bullish (green)
        - Second candle: Bearish (red) and completely engulfs first candle
        """
        # First candle must be bullish (green)
        first_bullish = candle1['close'] > candle1['open']
        
        # Second candle must be bearish (red)
        second_bearish = candle2['close'] < candle2['open']
        
        # Second candle must completely engulf first candle
        # Second open > First close AND Second close < First open
        engulfs = (candle2['open'] > candle1['close'] and 
                   candle2['close'] < candle1['open'])
        
        # Additional validation: second candle body should be significantly larger
        body1_size = abs(candle1['close'] - candle1['open'])
        body2_size = abs(candle2['close'] - candle2['open'])
        size_ratio = body2_size / body1_size if body1_size > 0 else 0
        
        # Require second candle to be at least 20% larger
        significant_size = size_ratio >= 1.2
        
        return first_bullish and second_bearish and engulfs and significant_size
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Return strategy information"""
        return {
            'name': 'Engolfo (Engulfing)',
            'description': 'Detecta padrões de engolfo bullish e bearish em 2 candles consecutivos',
            'timeframes': ['M1', 'M5'],
            'signals': ['CALL (Engolfo Bullish)', 'PUT (Engolfo Bearish)'],
            'parameters': {
                'engulfing_timeframe': 60,
                'engulfing_min_body_size': 0.0001,
                'engulfing_volume_filter': False
            }
        }
