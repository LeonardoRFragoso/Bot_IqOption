"""
MACD Strategy - Moving Average Convergence Divergence
Utiliza o indicador MACD para identificar sinais de entrada baseados em:
- Cruzamento da linha MACD com a linha de sinal
- Divergências do histograma
- Posição relativa à linha zero

Sinais:
- CALL: MACD cruza acima da linha de sinal (momentum bullish)
- PUT: MACD cruza abaixo da linha de sinal (momentum bearish)
"""

import time
from typing import Optional, Dict, Any, List
from datetime import datetime


class MACDStrategy:
    """Estratégia MACD - Moving Average Convergence Divergence"""
    
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
        Analyze MACD signals for given asset
        Returns: 'call', 'put', or None
        """
        try:
            # Get configuration parameters
            timeframe = getattr(self.config, 'macd_timeframe', 60)  # Default M1
            fast_period = getattr(self.config, 'macd_fast_period', 12)
            slow_period = getattr(self.config, 'macd_slow_period', 26)
            signal_period = getattr(self.config, 'macd_signal_period', 9)
            min_histogram_threshold = getattr(self.config, 'macd_min_histogram', 0.00001)
            
            # Need enough candles for MACD calculation
            required_candles = max(slow_period + signal_period + 5, 50)
            candles = self.api.get_candles(asset, timeframe, required_candles)
            
            if not candles or len(candles) < required_candles:
                self._log(f"Dados insuficientes para MACD: {len(candles) if candles else 0}/{required_candles} velas", "WARNING")
                return None
            
            # Calculate MACD components
            macd_data = self._calculate_macd(candles, fast_period, slow_period, signal_period)
            if not macd_data:
                return None
            
            # Validate MACD data structure
            if not all(key in macd_data for key in ['macd', 'signal', 'histogram']):
                self._log("Estrutura de dados MACD inválida", "ERROR")
                return None
            
            if not all(isinstance(macd_data[key], list) and len(macd_data[key]) > 0 
                      for key in ['macd', 'signal', 'histogram']):
                self._log("Dados MACD vazios ou inválidos", "ERROR")
                return None
            
            # Get current and previous values for crossover detection
            try:
                current_macd = macd_data['macd'][-1]
                current_signal = macd_data['signal'][-1]
                current_histogram = macd_data['histogram'][-1]
                
                prev_macd = macd_data['macd'][-2] if len(macd_data['macd']) > 1 else current_macd
                prev_signal = macd_data['signal'][-2] if len(macd_data['signal']) > 1 else current_signal
                prev_histogram = macd_data['histogram'][-2] if len(macd_data['histogram']) > 1 else current_histogram
            except (IndexError, TypeError, KeyError) as e:
                self._log(f"Erro ao acessar dados MACD: {str(e)}", "ERROR")
                return None
            
            # Detect crossovers
            bullish_crossover = self._detect_bullish_crossover(prev_macd, prev_signal, current_macd, current_signal)
            bearish_crossover = self._detect_bearish_crossover(prev_macd, prev_signal, current_macd, current_signal)
            
            # Additional confirmation from histogram
            histogram_confirmation = abs(current_histogram) >= min_histogram_threshold
            
            if bullish_crossover and histogram_confirmation:
                self._log(f"MACD Bullish Crossover | MACD: {current_macd:.6f} | Signal: {current_signal:.6f} | Histogram: {current_histogram:.6f}", "INFO")
                return 'call'
            elif bearish_crossover and histogram_confirmation:
                self._log(f"MACD Bearish Crossover | MACD: {current_macd:.6f} | Signal: {current_signal:.6f} | Histogram: {current_histogram:.6f}", "INFO")
                return 'put'
            
            return None
            
        except Exception as e:
            self._log(f"Erro na análise MACD: {str(e)}", "ERROR")
            return None
    
    def _calculate_macd(self, candles: List[Dict[str, Any]], fast_period: int, slow_period: int, signal_period: int) -> Optional[Dict[str, List[float]]]:
        """
        Calculate MACD, Signal line, and Histogram
        """
        try:
            closes = [float(candle['close']) for candle in candles]
            
            if len(closes) < slow_period + signal_period:
                self._log(f"Dados insuficientes para MACD: {len(closes)} velas, necessário {slow_period + signal_period}", "WARNING")
                return None
            
            # Calculate EMAs
            ema_fast = self._calculate_ema(closes, fast_period)
            ema_slow = self._calculate_ema(closes, slow_period)
            
            if not ema_fast or not ema_slow:
                self._log("Falha no cálculo das EMAs para MACD", "ERROR")
                return None
                
            if len(ema_fast) != len(ema_slow):
                self._log(f"Tamanhos diferentes das EMAs: fast={len(ema_fast)}, slow={len(ema_slow)}", "ERROR")
                return None
            
            # Calculate MACD line (EMA_fast - EMA_slow)
            # Need to align EMAs since they start at different periods
            min_ema_len = min(len(ema_fast), len(ema_slow))
            macd_line = []
            
            # Align the EMAs by taking the last min_ema_len values
            aligned_fast = ema_fast[-min_ema_len:] if len(ema_fast) > min_ema_len else ema_fast
            aligned_slow = ema_slow[-min_ema_len:] if len(ema_slow) > min_ema_len else ema_slow
            
            for i in range(len(aligned_fast)):
                macd_line.append(aligned_fast[i] - aligned_slow[i])
            
            if len(macd_line) < signal_period:
                self._log(f"MACD line muito curta para calcular sinal: {len(macd_line)} < {signal_period}", "WARNING")
                return None
            
            # Calculate Signal line (EMA of MACD line)
            signal_line = self._calculate_ema(macd_line, signal_period)
            if not signal_line:
                self._log("Falha no cálculo da linha de sinal MACD", "ERROR")
                return None
            
            # Calculate Histogram (MACD - Signal)
            # Align MACD and Signal lines
            min_len = min(len(macd_line), len(signal_line))
            histogram = []
            
            aligned_macd = macd_line[-min_len:] if len(macd_line) > min_len else macd_line
            aligned_signal = signal_line[-min_len:] if len(signal_line) > min_len else signal_line
            
            for i in range(min_len):
                histogram.append(aligned_macd[i] - aligned_signal[i])
            
            return {
                'macd': aligned_macd,
                'signal': aligned_signal,
                'histogram': histogram
            }
            
        except Exception as e:
            self._log(f"Erro no cálculo MACD: {str(e)}", "ERROR")
            return None
    
    def _calculate_ema(self, prices: List[float], period: int) -> Optional[List[float]]:
        """
        Calculate Exponential Moving Average
        """
        try:
            if not prices or len(prices) < period:
                self._log(f"Dados insuficientes para EMA: {len(prices) if prices else 0} preços, necessário {period}", "WARNING")
                return None
            
            # Validate that all prices are valid numbers
            valid_prices = []
            for price in prices:
                try:
                    valid_price = float(price)
                    if not (float('-inf') < valid_price < float('inf')):  # Check for NaN and inf
                        self._log(f"Preço inválido encontrado: {price}", "WARNING")
                        continue
                    valid_prices.append(valid_price)
                except (ValueError, TypeError):
                    self._log(f"Preço não numérico encontrado: {price}", "WARNING")
                    continue
            
            if len(valid_prices) < period:
                self._log(f"Preços válidos insuficientes para EMA: {len(valid_prices)}/{period}", "WARNING")
                return None
            
            ema_values = []
            multiplier = 2.0 / (period + 1)
            
            # First EMA value is SMA
            sma = sum(valid_prices[:period]) / period
            ema_values.append(sma)
            
            # Calculate subsequent EMA values
            for i in range(period, len(valid_prices)):
                ema = (valid_prices[i] * multiplier) + (ema_values[-1] * (1 - multiplier))
                ema_values.append(ema)
            
            return ema_values
            
        except Exception as e:
            self._log(f"Erro no cálculo EMA: {str(e)}", "ERROR")
            return None
    
    def _detect_bullish_crossover(self, prev_macd: float, prev_signal: float, current_macd: float, current_signal: float) -> bool:
        """
        Detect bullish crossover (MACD crosses above Signal line)
        """
        # Previous: MACD was below Signal
        # Current: MACD is above Signal
        was_below = prev_macd <= prev_signal
        is_above = current_macd > current_signal
        
        return was_below and is_above
    
    def _detect_bearish_crossover(self, prev_macd: float, prev_signal: float, current_macd: float, current_signal: float) -> bool:
        """
        Detect bearish crossover (MACD crosses below Signal line)
        """
        # Previous: MACD was above Signal
        # Current: MACD is below Signal
        was_above = prev_macd >= prev_signal
        is_below = current_macd < current_signal
        
        return was_above and is_below
    
    def _analyze_divergence(self, candles: List[Dict[str, Any]], macd_data: Dict[str, List[float]]) -> Optional[str]:
        """
        Analyze price vs MACD divergence (advanced feature)
        """
        try:
            if len(candles) < 10 or len(macd_data['macd']) < 10:
                return None
            
            # Get recent price and MACD data
            recent_closes = [candle['close'] for candle in candles[-10:]]
            recent_macd = macd_data['macd'][-10:]
            
            # Simple divergence detection
            price_trend = recent_closes[-1] - recent_closes[0]
            macd_trend = recent_macd[-1] - recent_macd[0]
            
            # Bullish divergence: price falling, MACD rising
            if price_trend < 0 and macd_trend > 0:
                return 'call'
            
            # Bearish divergence: price rising, MACD falling
            elif price_trend > 0 and macd_trend < 0:
                return 'put'
            
            return None
            
        except Exception:
            return None
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Return strategy information"""
        return {
            'name': 'MACD',
            'description': 'Moving Average Convergence Divergence - detecta cruzamentos e divergências',
            'timeframes': ['M1', 'M5'],
            'signals': ['CALL (Cruzamento Bullish)', 'PUT (Cruzamento Bearish)'],
            'parameters': {
                'macd_timeframe': 60,
                'macd_fast_period': 12,
                'macd_slow_period': 26,
                'macd_signal_period': 9,
                'macd_min_histogram': 0.00001
            }
        }
