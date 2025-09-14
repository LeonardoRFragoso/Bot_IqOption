"""
Moving Average Crossover Strategy - Golden/Death Cross
Estratégia baseada no cruzamento de médias móveis para identificar tendências
"""

import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from django.utils import timezone
from .iq_api import IQOptionAPI
from .models import TradingSession, Operation, TradingLog
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .serializers import OperationSerializer, TradingSessionSerializer

logger = logging.getLogger(__name__)


class MovingAverageStrategy:
    """Moving Average Crossover Strategy - Cruzamento de Médias Móveis"""
    
    def __init__(self, api: IQOptionAPI, session: TradingSession):
        self.api = api
        self.session = session
        self.user = session.user
        self.config = session.user.trading_config
        self.running = False
        # Prevent multiple entries within the same minute
        self._last_entry_idx = {}
        
        # Moving Average Configuration
        self.ma_fast_period = getattr(self.config, 'ma_fast_period', 9)  # Média rápida
        self.ma_slow_period = getattr(self.config, 'ma_slow_period', 21)  # Média lenta
        self.ma_timeframe = getattr(self.config, 'ma_timeframe', 60)  # M1 por padrão
        self.ma_confirmation_candles = getattr(self.config, 'ma_confirmation_candles', 2)  # Velas de confirmação
        
    def start(self):
        """Start strategy execution"""
        self.running = True
        self._log("Estratégia Moving Average iniciada", "INFO")
        
    def stop(self):
        """Stop strategy execution"""
        if not self.running:
            return
        self.running = False
        self._log("Estratégia Moving Average parada", "INFO")
        
    def _log(self, message: str, level: str = "INFO"):
        """Log message to database"""
        TradingLog.objects.create(
            session=self.session,
            user=self.user,
            level=level,
            message=message
        )
        logger.info(f"[MA] {message}")
    
    def _check_stop_conditions(self) -> bool:
        """Check if stop win/loss conditions are met"""
        try:
            total_pl = float(self.session.total_profit)
        except Exception:
            total_pl = 0.0
        try:
            stop_loss = float(self.config.stop_loss)
        except Exception:
            stop_loss = 0.0
        try:
            stop_win = float(self.config.stop_win)
        except Exception:
            stop_win = 0.0

        if stop_loss > 0 and total_pl <= -abs(stop_loss):
            self._log(f"STOP LOSS BATIDO: ${self.session.total_profit}", "ERROR")
            self.session.status = 'STOPPED'
            self.session.save()
            return False
            
        if stop_win > 0 and total_pl >= abs(stop_win):
            self._log(f"STOP WIN BATIDO: ${self.session.total_profit}", "INFO")
            self.session.status = 'STOPPED'
            self.session.save()
            return False
            
        return True

    def _ws_group(self) -> str:
        try:
            return f"trading_{self.user.id}"
        except Exception:
            return ""

    def _ws_send(self, event_type: str, data: dict):
        try:
            group = self._ws_group()
            if not group:
                return
            channel_layer = get_channel_layer()
            if channel_layer is None:
                return
            async_to_sync(channel_layer.group_send)(group, {
                'type': event_type,
                'data': data,
            })
        except Exception:
            pass

    def _server_dt(self):
        """Return (timestamp, local naive datetime) from server time."""
        st = self.api.get_server_timestamp()
        dt = datetime.fromtimestamp(st)
        return st, dt

    def _gate_once(self, key: str, st: float) -> bool:
        """Allow trigger only once per minute for a given gate key."""
        minute_idx = int(st) // 60
        if self._last_entry_idx.get(key) == minute_idx:
            return False
        self._last_entry_idx[key] = minute_idx
        return True

    def _is_entry_time_ma(self) -> bool:
        """MA: fire at the start of each minute with a <=2s window"""
        st, dt = self._server_dt()
        try:
            sec = float(st) % 60.0
        except Exception:
            sec = 0.0
        
        if sec <= 2.0:
            allowed = self._gate_once('ma', st)
            if allowed:
                try:
                    self._log(f"GATE MA | sec={sec:.2f}", "DEBUG")
                except Exception:
                    pass
            return allowed
        return False

    def _calculate_sma(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return None
            
        try:
            return sum(prices[-period:]) / period
        except Exception as e:
            self._log(f"Erro no cálculo da SMA: {str(e)}", "ERROR")
            return None

    def _calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return None
            
        try:
            # Start with SMA for the first EMA value
            sma = sum(prices[:period]) / period
            ema = sma
            
            # Calculate multiplier
            multiplier = 2 / (period + 1)
            
            # Calculate EMA for remaining prices
            for price in prices[period:]:
                ema = (price * multiplier) + (ema * (1 - multiplier))
            
            return ema
            
        except Exception as e:
            self._log(f"Erro no cálculo da EMA: {str(e)}", "ERROR")
            return None

    def _determine_operation_type(self, asset: str) -> Tuple[str, str]:
        """Determine best operation type and asset based on payouts"""
        if self.config.tipo == 'automatico':
            payouts = self.api.get_payout(asset)
            digital = payouts.get('digital', 0) or 0
            binary = payouts.get('binary', 0) or 0
            
            try:
                st = float(self.api.get_server_timestamp())
                sec = st % 60.0
            except Exception:
                sec = 0.0
            
            # Preferir DIGITAL quando payouts são iguais
            if digital > 0 and digital == binary:
                self._log("Payouts iguais — preferindo DIGITAL", "INFO")
                return 'digital', asset
            
            # Após 1s do minuto → BINARY para entrada imediata
            if sec > 1.0 and binary > 0:
                self._log("Segundo atual > 1s — preferindo BINARY", "INFO")
                return 'binary', asset
            
            # DIGITAL com vantagem significativa e no início do minuto
            if digital >= binary + 10 and sec <= 1.0 and digital > 0:
                self._log("Usando DIGITAL (vantagem significativa)", "INFO")
                return 'digital', asset
            
            # Escolher o maior payout
            if max(digital, binary) > 0:
                chosen = 'digital' if digital >= binary else 'binary'
                self._log(f"Operações serão realizadas nas {chosen}", "INFO")
                return chosen, asset
            
            # Tentar ativo alternativo
            alt = None
            try:
                alt = self.api.get_best_available_asset()
            except Exception:
                pass
            if alt and alt != asset:
                self._log(f"Par {asset} sem payout. Alternando para {alt}", "WARNING")
                return self._determine_operation_type(alt)
            
            if binary > 0:
                self._log("Digital indisponível. Utilizando binary.", "WARNING")
                return 'binary', asset
            
            self._log("Par fechado, escolha outro", "ERROR")
            return None, None
        else:
            # Modo manual
            payouts = self.api.get_payout(asset)
            if payouts['digital'] == 0 and payouts['binary'] == 0:
                alternative_asset = self.api.get_best_available_asset()
                if alternative_asset:
                    self._log(f"Ativo {asset} fechado, mudando para {alternative_asset}", "WARNING")
                    asset = alternative_asset
                    payouts = self.api.get_payout(asset)
                else:
                    self._log("Nenhum ativo disponível no momento", "ERROR")
                    return None, None
            
            tipo = getattr(self.config, 'tipo', 'digital')
            if str(tipo).lower() == 'turbo':
                self._log("Operações TURBO desativadas. Usando DIGITAL.", "WARNING")
                tipo = 'digital'
            return tipo, asset

    def _execute_trade(self, asset: str, direction: str, expiration: int, operation_type: str) -> bool:
        """Execute trade with martingale and soros logic"""
        entry_value = float(self.config.valor_entrada)
        series_profit = 0.0
        
        # Apply Soros if configured
        if self.config.soros_usar and hasattr(self.session, 'soros_level'):
            soros_level = getattr(self.session, 'soros_level', 0)
            soros_value = getattr(self.session, 'soros_value', 0)
            
            if soros_level > 0 and soros_value > 0:
                entry_value += float(soros_value)
        
        # Execute martingale sequence
        martingale_levels = self.config.martingale_niveis if self.config.martingale_usar else 0
        
        for gale_level in range(martingale_levels + 1):
            if not self.running or not self._check_stop_conditions():
                return False
            
            # Apply martingale multiplier
            if gale_level > 0:
                entry_value = round(entry_value * float(self.config.martingale_fator), 2)
            
            # Log attempt details
            try:
                label = 'Entrada' if gale_level == 0 else f'Gale {gale_level}'
                self._log(f"Tentativa {label} | Valor: ${entry_value}", "INFO")
            except Exception:
                pass
            
            # Place order
            success, order_id = self.api.buy_option(
                asset=asset,
                amount=entry_value,
                direction=direction,
                expiration=expiration,
                option_type=operation_type,
                urgent=bool(gale_level > 0 and int(expiration) == 1)
            )
            
            if success:
                self._log(f"Ordem aberta com sucesso | order_id={order_id}", "INFO")
            else:
                self._log(f"Falha ao abrir ordem | order_id={order_id}", "ERROR")
                return False
            
            # Create operation record
            operation = Operation.objects.create(
                session=self.session,
                asset=asset,
                direction=direction.upper(),
                entry_value=Decimal(str(entry_value)),
                expiration_time=expiration,
                operation_type='ENTRY' if gale_level == 0 else f'GALE{gale_level}',
                iq_order_id=order_id
            )
            
            # Broadcast operation
            try:
                payload = OperationSerializer(operation).data
                self._ws_send('operation_update', payload)
            except Exception:
                pass
            
            gale_text = f' (Gale {gale_level})' if gale_level > 0 else ''
            self._log(f"Ordem aberta{gale_text} | Par: {asset} | Valor: ${entry_value}", "INFO")
            
            # Wait for result
            result = self._wait_for_result(operation, operation_type)
            
            if result and result > 0:
                series_profit += float(result)
                self._handle_win(operation, result, gale_level)
                if self.config.soros_usar:
                    self._update_soros_progression(True, series_profit)
                return True
            elif result is not None:
                self._handle_loss(operation, result, gale_level)
                series_profit += float(result)
                if gale_level < martingale_levels:
                    self._log("Executando Gale na próxima vela...", "INFO")
        
        # Full series ended without win
        if self.config.soros_usar:
            self._update_soros_progression(False, series_profit)
        return False

    def _wait_for_result(self, operation: Operation, operation_type: str) -> Optional[float]:
        """Wait for operation result"""
        max_wait_time = 300  # 5 minutes max wait
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            if not self.running:
                return None
                
            status, result = self.api.check_win(operation.iq_order_id, operation_type)
            
            if status and result is not None:
                return result
                
            elapsed = time.time() - start_time
            if int(elapsed) % 10 == 0:
                try:
                    self._log(f"Aguardando resultado... {int(elapsed)}s", "DEBUG")
                except Exception:
                    pass
            time.sleep(1)
        
        self._log(f"Timeout aguardando resultado. Considerando perda.", "WARNING")
        try:
            return -float(operation.entry_value)
        except Exception:
            return -1.0

    def _handle_win(self, operation: Operation, result: float, gale_level: int):
        """Handle winning operation"""
        operation.result = 'WIN'
        operation.profit_loss = Decimal(str(result))
        operation.closed_at = timezone.now()
        operation.save()
        
        # Update session statistics
        self.session.total_operations += 1
        self.session.wins += 1
        self.session.total_profit += Decimal(str(result))
        self.session.current_balance = Decimal(str(self.api.get_balance()))
        self.session.save()
        
        # WS broadcast
        try:
            op_payload = OperationSerializer(operation).data
            sess_payload = TradingSessionSerializer(self.session).data
            self._ws_send('operation_update', op_payload)
            self._ws_send('session_update', sess_payload)
        except Exception:
            pass
        
        gale_text = f' (Gale {gale_level})' if gale_level > 0 else ''
        self._log(f"WIN{gale_text} | Lucro: ${result}", "INFO")

    def _handle_loss(self, operation: Operation, result: float, gale_level: int):
        """Handle losing operation"""
        if result == 0:
            operation.result = 'DRAW'
            self.session.draws += 1
            result_text = "EMPATE"
        else:
            operation.result = 'LOSS'
            self.session.losses += 1
            result_text = f"LOSS | Perda: ${abs(result)}"
        
        operation.profit_loss = Decimal(str(result))
        operation.closed_at = timezone.now()
        operation.save()
        
        # Update session statistics
        self.session.total_operations += 1
        self.session.total_profit += Decimal(str(result))
        self.session.current_balance = Decimal(str(self.api.get_balance()))
        self.session.save()
        
        # WS broadcast
        try:
            op_payload = OperationSerializer(operation).data
            sess_payload = TradingSessionSerializer(self.session).data
            self._ws_send('operation_update', op_payload)
            self._ws_send('session_update', sess_payload)
        except Exception:
            pass
        
        gale_text = f' (Gale {gale_level})' if gale_level > 0 else ''
        self._log(f"{result_text}{gale_text}", "ERROR" if result < 0 else "WARNING")

    def _update_soros_progression(self, won: bool, result: float):
        """Update Soros progression"""
        if won:
            try:
                net_profit = float(result)
            except Exception:
                net_profit = 0.0
            if net_profit > 0:
                current_level = getattr(self.session, 'soros_level', 0)
                if current_level < self.config.soros_niveis:
                    setattr(self.session, 'soros_level', current_level + 1)
                    current_value = getattr(self.session, 'soros_value', 0)
                    setattr(self.session, 'soros_value', current_value + net_profit)
        else:
            setattr(self.session, 'soros_level', 0)
            setattr(self.session, 'soros_value', 0)
        
        self.session.save()

    def run(self, asset: str):
        """Execute Moving Average strategy"""
        self._log(f"Iniciando estratégia Moving Average para {asset}", "INFO")
        self._log(f"Configuração: MA Rápida={self.ma_fast_period}, MA Lenta={self.ma_slow_period}", "INFO")
        
        operation_type, current_asset = self._determine_operation_type(asset)
        if not operation_type or not current_asset:
            return
        
        if current_asset != asset:
            asset = current_asset
        
        # Store previous crossover state to detect new crossovers
        previous_crossover_state = None
        
        while self.running and self._check_stop_conditions():
            try:
                # Check if asset is still available periodically
                if hasattr(self, '_last_asset_check'):
                    if time.time() - self._last_asset_check > 300:  # Check every 5 minutes
                        new_operation_type, new_asset = self._determine_operation_type(asset)
                        if new_asset and new_asset != asset:
                            self._log(f"Mudando de {asset} para {new_asset}", "INFO")
                            asset = new_asset
                            operation_type = new_operation_type
                        self._last_asset_check = time.time()
                else:
                    self._last_asset_check = time.time()

                # Entry time gate
                if self._is_entry_time_ma():
                    direction, crossover_state = self._analyze_ma_crossover(asset)
                    
                    # Only trade on new crossovers (state change)
                    if direction in ['put', 'call'] and crossover_state != previous_crossover_state:
                        self._execute_trade(asset, direction, 1, operation_type)
                        self._log("-" * 30, "INFO")
                        previous_crossover_state = crossover_state
                
                time.sleep(0.1)
                
            except Exception as e:
                self._log(f"Erro na estratégia Moving Average: {str(e)}", "ERROR")
                time.sleep(5)

    def _analyze_ma_crossover(self, asset: str) -> Tuple[Optional[str], Optional[str]]:
        """Analyze Moving Average crossover for entry signals"""
        candles_count = max(self.ma_slow_period + 10, 50)  # Extra candles for better MA calculation
        
        # Get candles
        candles = self.api.get_candles(asset, self.ma_timeframe, candles_count)
        
        if not candles or len(candles) < self.ma_slow_period:
            self._log("Erro ao obter velas para análise MA", "ERROR")
            return None, None
        
        try:
            # Extract closing prices
            closes = [candle['close'] for candle in candles]
            
            # Calculate moving averages
            ma_fast = self._calculate_sma(closes, self.ma_fast_period)
            ma_slow = self._calculate_sma(closes, self.ma_slow_period)
            
            if ma_fast is None or ma_slow is None:
                self._log("Erro no cálculo das médias móveis", "ERROR")
                return None, None
            
            # Calculate previous MAs for crossover detection
            if len(closes) >= self.ma_slow_period + self.ma_confirmation_candles:
                prev_closes = closes[:-1]  # Previous candle closes
                prev_ma_fast = self._calculate_sma(prev_closes, self.ma_fast_period)
                prev_ma_slow = self._calculate_sma(prev_closes, self.ma_slow_period)
            else:
                prev_ma_fast = ma_fast
                prev_ma_slow = ma_slow
            
            self._log(f"MA Rápida: {ma_fast:.5f} | MA Lenta: {ma_slow:.5f}", "INFO")
            
            # Determine crossover state
            current_state = 'above' if ma_fast > ma_slow else 'below'
            previous_state = 'above' if prev_ma_fast > prev_ma_slow else 'below'
            
            # Detect crossovers
            if previous_state == 'below' and current_state == 'above':
                # Golden Cross - MA rápida cruza acima da lenta (sinal de CALL)
                self._log(f"Golden Cross detectado - MA rápida ({ma_fast:.5f}) cruzou acima da lenta ({ma_slow:.5f}) - Sinal CALL", "INFO")
                return 'call', 'golden_cross'
            elif previous_state == 'above' and current_state == 'below':
                # Death Cross - MA rápida cruza abaixo da lenta (sinal de PUT)
                self._log(f"Death Cross detectado - MA rápida ({ma_fast:.5f}) cruzou abaixo da lenta ({ma_slow:.5f}) - Sinal PUT", "INFO")
                return 'put', 'death_cross'
            else:
                # No crossover detected
                self._log(f"Sem cruzamento - MA rápida {current_state} da lenta", "DEBUG")
                return None, current_state
            
        except Exception as e:
            self._log(f"Erro na análise de cruzamento de médias: {str(e)}", "ERROR")
            return None, None
