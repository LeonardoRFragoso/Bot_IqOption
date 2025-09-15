"""
Trading strategies implementation
Migrated from legacy v1 with improvements and modern architecture
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
from .engulfing_strategy import EngulfingStrategy
from .candlestick_strategy import CandlestickStrategy
from .macd_strategy import MACDStrategy

logger = logging.getLogger(__name__)


class BaseStrategy:
    """Base class for all trading strategies"""
    
    def __init__(self, api: IQOptionAPI, session: TradingSession):
        self.api = api
        self.session = session
        self.user = session.user
        self.config = session.user.trading_config
        self.running = False
        # Prevent multiple entries within the same minute for time-gated strategies
        self._last_entry_idx = {}
        
    def start(self):
        """Start strategy execution"""
        self.running = True
        self._log("Estratégia iniciada", "INFO")
        
        # Log filtros ativos para visibilidade
        if hasattr(self.config, 'filtros_ativos'):
            filtros = getattr(self.config, 'filtros_ativos', [])
            # Verificar se filtros é uma lista válida e não vazia
            if isinstance(filtros, list) and len(filtros) > 0:
                self._log(f"[FILTROS] Ativos: {filtros}", "INFO")
                
                # Log parâmetros específicos dos filtros apenas se há filtros ativos
                if hasattr(self.config, 'media_movel_threshold'):
                    self._log(f"[FILTROS] Media Movel: {self.config.media_movel_threshold}", "INFO")
                if hasattr(self.config, 'rodrigo_risco_threshold'):
                    self._log(f"[FILTROS] Rodrigo Risco: {self.config.rodrigo_risco_threshold}", "INFO")
            else:
                self._log("[FILTROS] Nenhum filtro ativo - usando estrategia base", "INFO")
        
    def stop(self):
        """Stop strategy execution"""
        # Idempotent stop to avoid duplicate logs when called multiple times
        if not self.running:
            return
        self.running = False
        self._log("Estratégia parada", "INFO")
        
    def _log(self, message: str, level: str = "INFO"):
        """Log message to database"""
        TradingLog.objects.create(
            session=self.session,
            user=self.user,
            level=level,
            message=message
        )
        logger.info(f"[{self.session.strategy}] {message}")
    
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

        # v1-compatible: thresholds <= 0 disable the respective stop
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

    # ------------------ WS helpers ------------------
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
            # Never break strategy due to WS errors
            pass

    # ------------------ Time gating helpers ------------------
    def _server_dt(self):
        """Return (timestamp, local naive datetime) from server time (v1-compatible)."""
        st = self.api.get_server_timestamp()
        # v1 used datetime.fromtimestamp(...) without tz awareness
        dt = datetime.fromtimestamp(st)
        return st, dt

    def _gate_once(self, key: str, st: float) -> bool:
        """Allow trigger only once per minute for a given gate key."""
        minute_idx = int(st) // 60
        if self._last_entry_idx.get(key) == minute_idx:
            return False
        self._last_entry_idx[key] = minute_idx
        return True

    def _is_entry_time_mhi(self) -> bool:
        """MHI M1: analyze minutes 2-3-4 inside each 5m block and enter at the start of minute 0 of the next block.
        Gate when minute%5 == 0 with a <=1s window.
        """
        st, dt = self._server_dt()
        try:
            sec = float(st) % 60.0
            minute_idx = int(st) // 60
            minute_in_block = minute_idx % 5
        except Exception:
            sec = 0.0
            try:
                minute_idx = int(time.time()) // 60
                minute_in_block = minute_idx % 5
            except Exception:
                minute_in_block = 0
        if (minute_in_block == 0) and (sec <= 1.0):
            allowed = self._gate_once('mhi', st)
            if allowed:
                try:
                    self._log(f"GATE MHI | min_bloco={minute_in_block} | sec={sec:.2f}", "DEBUG")
                except Exception:
                    pass
            return allowed
        return False

    def _is_entry_time_torres(self) -> bool:
        """Torres Gêmeas: fire at minute 4,9,14,... with a <=1s window"""
        st, dt = self._server_dt()
        try:
            sec = float(st) % 60.0
            minute_idx = int(st) // 60
            minute_in_block = minute_idx % 5
        except Exception:
            sec = 0.0
            try:
                minute_idx = int(time.time()) // 60
                minute_in_block = minute_idx % 5
            except Exception:
                minute_in_block = 0
        if (minute_in_block == 4) and (sec <= 1.0):
            allowed = self._gate_once('torres', st)
            if allowed:
                try:
                    self._log(f"GATE TORRES | min_bloco={minute_in_block} | sec={sec:.2f}", "DEBUG")
                except Exception:
                    pass
            return allowed
        return False

    def _is_entry_time_mhi_m5(self) -> bool:
        """MHI M5: fire at minute 00 and 30 with a <=1s window"""
        st, dt = self._server_dt()
        try:
            sec = float(st) % 60.0
            minute_idx = int(st) // 60
            minute_in_block_30 = minute_idx % 30
        except Exception:
            sec = 0.0
            try:
                minute_idx = int(time.time()) // 60
                minute_in_block_30 = minute_idx % 30
            except Exception:
                minute_in_block_30 = 0
        if (minute_in_block_30 == 0) and (sec <= 1.0):
            allowed = self._gate_once('mhi_m5', st)
            if allowed:
                try:
                    self._log(f"GATE MHI5 | min_bloco30={minute_in_block_30} | sec={sec:.2f}", "DEBUG")
                except Exception:
                    pass
            return allowed
        return False

    # ------------------ Execution helpers ------------------
    def _determine_operation_type(self, asset: str) -> Tuple[Optional[str], Optional[str]]:
        """Determine best operation type and asset based on payouts"""
        # Check if current asset is available
        payouts = self.api.get_payout(asset, force_refresh=True)
        self._log(f"[DEBUG] Payouts para {asset}: {payouts}", "DEBUG")
        
        # Remover TURBO da consideração
        if payouts['digital'] == 0 and payouts['binary'] == 0:
            # Try to find alternative asset
            alternative_asset = self.api.get_best_available_asset()
            if alternative_asset:
                self._log(f"Ativo {asset} fechado, mudando para {alternative_asset}", "WARNING")
                asset = alternative_asset
                payouts = self.api.get_payout(asset, force_refresh=True)
            else:
                self._log("Nenhum ativo disponível no momento", "ERROR")
                return None, None
        
        # Mapear configuração manual 'turbo' para 'digital'
        tipo = getattr(self.config, 'tipo', 'digital')
        if str(tipo).lower() == 'turbo':
            self._log("Operações TURBO desativadas. Usando DIGITAL.", "WARNING")
            tipo = 'digital'
        
        # Operação automática: somente DIGITAL ou BINARY (sem TURBO)
        if tipo == 'automatico':
            digital = payouts.get('digital', 0) or 0
            binary = payouts.get('binary', 0) or 0
            
            # Prioritize binary first, digital as fallback
            if binary > 0:
                self._log(f"Operações serão realizadas nas BINARY (payout: {binary}%)", "INFO")
                return 'binary', asset
            if digital > 0:
                self._log(f"BINARY indisponível - usando DIGITAL como fallback (payout: {digital}%)", "INFO")
                return 'digital', asset
            
            # Se nenhum payout disponível, tentar ativo alternativo
            alternative_asset = self.api.get_best_available_asset()
            if alternative_asset and alternative_asset != asset:
                self._log(f"Ativo {asset} fechado, tentando {alternative_asset}", "WARNING")
                alt_payouts = self.api.get_payout(alternative_asset, force_refresh=True)
                alt_binary = alt_payouts.get('binary', 0) or 0
                alt_digital = alt_payouts.get('digital', 0) or 0
                
                if alt_binary > 0:
                    self._log(f"Operações serão realizadas nas BINARY com {alternative_asset} (payout: {alt_binary}%)", "INFO")
                    return 'binary', alternative_asset
                if alt_digital > 0:
                    self._log(f"Operações serão realizadas nas DIGITAL com {alternative_asset} (payout: {alt_digital}%)", "INFO")
                    return 'digital', alternative_asset
            
            self._log("Nenhum ativo disponível no momento", "ERROR")
            return None, None
        else:
            # Modo manual - usar tipo configurado
            if payouts[tipo] > 0:
                self._log(f"Operações serão realizadas nas {tipo.upper()} (payout: {payouts[tipo]}%)", "INFO")
                return tipo, asset
            else:
                self._log(f"Tipo {tipo} não disponível para {asset}", "ERROR")
                return None, None

    def _wait_next_minute_edge(self, buffer_seconds: float = 0.5):
        """Sleep until the start of the next minute plus a small buffer.
        Uses server time to align entries for gale execution.
        """
        try:
            st = self.api.get_server_timestamp()
            # seconds elapsed in current minute
            secs = int(st) % 60
            wait = (60 - secs) + max(0.0, float(buffer_seconds))
            if wait > 0:
                time.sleep(min(wait, 30))  # never sleep more than 30s as a guard
        except Exception:
            # Fallback: short sleep
            time.sleep(1)
            
        payouts = self.api.get_payout(asset, force_refresh=True)
        self._log(f"Payouts - Binary: {payouts['binary']}%, Digital: {payouts['digital']}%", "INFO")
        
        # Check if any payout is available
        if payouts['digital'] == 0 and payouts['binary'] == 0:
            # Try to find alternative asset automatically
            alternative_asset = self.api.get_best_available_asset()
            if alternative_asset:
                self._log(f"Ativo {asset} fechado, mudando para {alternative_asset}", "WARNING")
                alt_payouts = self.api.get_payout(alternative_asset, force_refresh=True)
                
                # Prefer open instruments with highest payout
                alt_open = {
                    'digital': getattr(self.api, 'is_asset_open', lambda a, t: True)(alternative_asset, 'digital'),
                    'binary': getattr(self.api, 'is_asset_open', lambda a, t: True)(alternative_asset, 'binary'),
                }
                ordered = sorted([
                    ('digital', alt_payouts['digital'], alt_open['digital']),
                    ('binary', alt_payouts['binary'], alt_open['binary'])
                ], key=lambda x: x[1], reverse=True)
                for t, p, is_open in ordered:
                    if p > 0 and is_open:
                        self._log(f"Operações serão realizadas nas {t}", "INFO")
                        return t, alternative_asset
            
            self._log("Nenhum ativo disponível no momento", "ERROR")
            return None, None
        
        # Prefer open instruments with highest payout for the requested asset
        open_types = {
            'digital': getattr(self.api, 'is_asset_open', lambda a, t: True)(asset, 'digital'),
            'binary': getattr(self.api, 'is_asset_open', lambda a, t: True)(asset, 'binary'),
        }
        ordered = sorted([
            ('digital', payouts['digital'], open_types['digital']),
            ('binary', payouts['binary'], open_types['binary'])
        ], key=lambda x: x[1], reverse=True)
        for t, p, is_open in ordered:
            if p > 0:
                # If the intended instrument is not open for the base asset, try OTC variant
                if not is_open:
                    otc_asset = f"{asset}-OTC"
                    try:
                        if self.api.is_asset_open(otc_asset, t):
                            self._log(f"{t.capitalize()} fechado em {asset}, mudando para {otc_asset}", "WARNING")
                            return t, otc_asset
                    except Exception:
                        pass
                if is_open:
                    self._log(f"Operações serão realizadas nas {t}", "INFO")
                    return t, asset
        
        # If none of the instruments are open for this asset, try alternative asset
        alternative_asset = self.api.get_best_available_asset()
        if alternative_asset:
            alt_payouts = self.api.get_payout(alternative_asset, force_refresh=True)
            alt_open = {
                'digital': getattr(self.api, 'is_asset_open', lambda a, t: True)(alternative_asset, 'digital'),
                'binary': getattr(self.api, 'is_asset_open', lambda a, t: True)(alternative_asset, 'binary'),
            }
            ordered = sorted([
                ('digital', alt_payouts['digital'], alt_open['digital']),
                ('binary', alt_payouts['binary'], alt_open['binary'])
            ], key=lambda x: x[1], reverse=True)
            for t, p, is_open in ordered:
                if p > 0:
                    if not is_open:
                        otc_alt = f"{alternative_asset}-OTC"
                        try:
                            if self.api.is_asset_open(otc_alt, t):
                                self._log(f"{t.capitalize()} fechado em {alternative_asset}, mudando para {otc_alt}", "WARNING")
                                return t, otc_alt
                        except Exception:
                            pass
                    if is_open:
                        self._log(f"Ativo {asset} fechado, mudando para {alternative_asset}", "WARNING")
                        self._log(f"Operações serão realizadas nas {t}", "INFO")
                        return t, alternative_asset
        
        self._log("Par fechado, escolha outro", "ERROR")
        return None, None
    
    def _find_best_open_asset(self) -> Optional[str]:
        """Find the best open asset with highest payout"""
        open_assets = self.api.get_open_assets()
        if not open_assets:
            self._log("Nenhum ativo disponível para trading", "ERROR")
            return None
        
        best_asset = None
        best_payout = 0
        
        for asset in open_assets[:10]:  # Check first 10 assets to avoid too many API calls
            try:
                payouts = self.api.get_payout(asset)
                # TURBO desativado: considerar somente digital e binary
                max_payout = max(payouts['digital'], payouts['binary'])
                
                if max_payout > best_payout:
                    best_payout = max_payout
                    best_asset = asset
                    
            except Exception as e:
                continue
        
        if best_asset:
            self._log(f"Melhor ativo encontrado: {best_asset} com payout de {best_payout}%", "INFO")
        
        return best_asset
    
    def _analyze_moving_averages(self, candles: List[Dict], period: int) -> str:
        """Analyze moving averages trend"""
        if len(candles) < period:
            return None
            
        total = sum(candle['close'] for candle in candles[-period:])
        ma = total / period
        
        return 'put' if ma > candles[-1]['close'] else 'call'
    
    def _execute_trade(self, asset: str, direction: str, expiration: int, operation_type: str) -> bool:
        """Execute trade with martingale and soros logic"""
        entry_value = float(self.config.valor_entrada)
        # Track cumulative P/L for the entire Gale series (used for Soros net calculation)
        series_profit = 0.0
        
        # Apply Soros if configured
        if self.config.soros_usar and hasattr(self.session, 'soros_level'):
            soros_level = getattr(self.session, 'soros_level', 0)
            soros_value = getattr(self.session, 'soros_value', 0)
            
            if soros_level > 0 and soros_value > 0:
                entry_value += float(soros_value)
        
        # Execute martingale sequence
        martingale_levels = self.config.martingale_niveis if self.config.martingale_usar else 0

        # Log current martingale configuration for transparency
        try:
            self._log(
                f"Config Martingale | usar={self.config.martingale_usar} | niveis={self.config.martingale_niveis} | fator={self.config.martingale_fator}",
                "INFO"
            )
        except Exception:
            pass
        
        for gale_level in range(martingale_levels + 1):
            if not self.running or not self._check_stop_conditions():
                return False
            
            # Apply martingale multiplier
            if gale_level > 0:
                entry_value = round(entry_value * float(self.config.martingale_fator), 2)
            # Log attempt details (optimized - no server timestamp calls)
            try:
                total_levels = martingale_levels
                label = 'Entrada' if gale_level == 0 else f'Gale {gale_level}'
                self._log(
                    f"Tentativa {label} | Nível {gale_level}/{total_levels} | Valor: ${entry_value}",
                    "INFO"
                )
            except Exception:
                pass
            
            # Determinar tipo efetivo sem forçar DIGITAL (respeita decisão anterior)
            actual_operation_type = operation_type

            # Pré-aquecimento já feito no pré-cálculo - pular para reduzir delay

            # Skip diagnostic log to reduce delay - direct order execution
            
            # Place order
            success, order_id = self.api.buy_option(
                asset=asset,
                amount=entry_value,
                direction=direction,
                expiration=expiration,
                option_type=actual_operation_type,
                urgent=bool(gale_level > 0 and int(expiration) == 1)
            )

            # If Binary was chosen and failed, try immediate Digital fallback (non-OTC often has binary suspended)
            if (not success) and actual_operation_type == 'binary':
                try:
                    self._log("Binary falhou - tentando fallback DIGITAL", "WARNING")
                except Exception:
                    pass
                fb_success, fb_order_id = self.api.buy_option(
                    asset=asset,
                    amount=entry_value,
                    direction=direction,
                    expiration=expiration,
                    option_type='digital',
                    urgent=False
                )
                if fb_success:
                    success = True
                    order_id = fb_order_id
                    actual_operation_type = 'digital'
                    try:
                        self._log(f"Fallback DIGITAL retornou sucesso | order_id={order_id}", "INFO")
                    except Exception:
                        pass

            # Diagnostic: log immediate result from API
            if success:
                self._log(f"buy_option retornou sucesso | order_id={order_id}", "INFO")
            else:
                self._log(f"buy_option falhou imediatamente | order_id={order_id}", "ERROR")
                self._log(f"Erro ao abrir ordem no ativo {asset}", "ERROR")
                # Não houve entrada. Abortar sequência (sem Gale).
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
            # Broadcast operation open
            try:
                payload = OperationSerializer(operation).data
                self._ws_send('operation_update', payload)
            except Exception:
                pass
            
            gale_text = f' (Gale {gale_level})' if gale_level > 0 else ''
            self._log(f"Ordem aberta{gale_text} | Par: {asset} | Valor: ${entry_value}", "INFO")
            
            # Wait for result using the actual operation type
            result = self._wait_for_result(operation, actual_operation_type)
            
            if result and result > 0:
                # accumulate series P/L
                try:
                    series_profit += float(result)
                except Exception:
                    pass
                # Win - break martingale sequence
                self._handle_win(operation, result, gale_level)
                # Soros progression based on NET series profit (win result minus previous Gale losses)
                if self.config.soros_usar:
                    try:
                        self._log(f"Soros: lucro líquido da série = ${series_profit:.2f}", "INFO")
                    except Exception:
                        pass
                    self._update_soros_progression(True, series_profit)
                return True
            elif result is not None:
                # Loss or draw
                self._handle_loss(operation, result, gale_level)
                # accumulate series P/L (result is 0 for draw or negative for loss)
                try:
                    series_profit += float(result)
                except Exception:
                    pass
                # Execute next Gale immediately on the next candle (no extra 1-minute wait)
                if gale_level < martingale_levels:
                    self._log("Executando Gale imediatamente na próxima vela...", "INFO")
                    # Sem descanso adicional: enviar imediatamente para minimizar atraso no início da vela
                    pass
                
        # Full series ended without a win: reset Soros progression
        if self.config.soros_usar:
            try:
                self._log(f"Soros: série finalizada sem vitória. Lucro líquido da série = ${series_profit:.2f}. Resetando Soros.", "WARNING")
            except Exception:
                pass
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
                
            # periodic debug every ~10s
            elapsed = time.time() - start_time
            if int(elapsed) % 10 == 0:
                try:
                    self._log(f"Aguardando resultado... {int(elapsed)}s", "DEBUG")
                except Exception:
                    pass
            time.sleep(1)
        
        # On timeout, consider it as a loss to allow Gale progression
        self._log(f"Timeout aguardando resultado da operação {operation.id}. Considerando perda para prosseguir com Gale.", "WARNING")
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
        # WS broadcast updates
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
        # WS broadcast updates
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
            # Only advance Soros if the net profit is positive
            try:
                net_profit = float(result)
            except Exception:
                net_profit = 0.0
            if net_profit > 0:
                # Increment Soros level on win
                current_level = getattr(self.session, 'soros_level', 0)
                if current_level < self.config.soros_niveis:
                    setattr(self.session, 'soros_level', current_level + 1)
                    current_value = getattr(self.session, 'soros_value', 0)
                    setattr(self.session, 'soros_value', current_value + net_profit)
        else:
            # Reset Soros on loss (full series loss)
            setattr(self.session, 'soros_level', 0)
            setattr(self.session, 'soros_value', 0)
        
        self.session.save()


class MHIStrategy(BaseStrategy):
    """MHI Strategy - Análise de 3 velas"""
    
    def run(self, asset: str):
        """Execute MHI strategy"""
        self._log(f"Iniciando estratégia MHI para {asset}", "INFO")
        
        operation_type, current_asset = self._determine_operation_type(asset)
        if not operation_type or not current_asset:
            self._log(f"[DEBUG] Estratégia parada: operation_type={operation_type}, current_asset={current_asset}", "ERROR")
            return
        
        # Update asset if it was changed
        if current_asset != asset:
            asset = current_asset
        
        # Pré-cálculo de direção para reduzir atraso: compute próximo sinal no final da vela atual
        pending_target_idx = None
        pending_direction = None
        
        while self.running and self._check_stop_conditions():
            try:
                # Periodically check if asset is still available
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

                # Pré-cálculo no fim da vela (evita atrasar a entrada no início da próxima)
                try:
                    st, dt = self._server_dt()
                    sec = float(st) % 60.0
                    minute_idx = int(st) // 60
                    minute_in_block = dt.minute % 5
                except Exception:
                    sec = 0.0
                    minute_idx = int(time.time()) // 60
                    try:
                        minute_in_block = datetime.fromtimestamp(time.time()).minute % 5
                    except Exception:
                        minute_in_block = 0

                # Pré-cálculo apenas no minuto 4 do bloco (analisando implicitamente as 3 últimas velas fechadas 2-3-4),
                # para entrar no minuto 0 do próximo bloco
                if minute_in_block == 4 and 58.0 <= sec <= 59.9 and pending_target_idx != minute_idx + 1:
                    # Calcular direção baseada nas 3 últimas velas fechadas
                    d = self._analyze_mhi_pattern(asset)
                    if d in ['put', 'call']:
                        pending_direction = d
                        pending_target_idx = minute_idx + 1
                        # Pré-aquecer DIGITAL: assinar strike list com antecedência quando planejamos entrar na próxima vela
                        try:
                            # Sempre pré-aquecer DIGITAL, mesmo quando a operação preferida é BINARY
                            if hasattr(self.api, '_api_lock') and getattr(self.api, 'subscribe_strike_list', None):
                                with self.api._api_lock:
                                    self.api.subscribe_strike_list(asset, 1)
                        except Exception:
                            pass
                        try:
                            self._log(
                                f"Pré-cálculo MHI pronto | direção={d.upper()} | alvo_min_idx={pending_target_idx} | minuto_bloco={minute_in_block}",
                                "DEBUG"
                            )
                        except Exception:
                            pass

                # Gate exato no início da vela nova
                if self._is_entry_time_mhi():
                    # Usar direção pré-calculada para o minuto atual, se existir
                    st_now = self.api.get_server_timestamp()
                    curr_minute_idx = int(st_now) // 60
                    if pending_direction in ['put', 'call'] and pending_target_idx == curr_minute_idx:
                        direction = pending_direction
                    else:
                        direction = self._analyze_mhi_pattern(asset)
                    
                    if direction in ['put', 'call']:
                        self._execute_trade(asset, direction, 1, operation_type)
                        self._log("-" * 30, "INFO")
                    # Resetar pré-cálculo após tentativa de entrada
                    pending_direction = None
                    pending_target_idx = None
                
                time.sleep(0.1)
                
            except Exception as e:
                self._log(f"Erro na estratégia MHI: {str(e)}", "ERROR")
                time.sleep(5)
    
    def _analyze_mhi_pattern(self, asset: str) -> Optional[str]:
        """Analyze MHI pattern (3 candles analysis)"""
        timeframe = 60
        candles_count = 5  # buscar algumas velas a mais, mas usaremos sempre as 3 últimas fechadas
        
        # Get moving averages if configured
        if self.config.analise_medias:
            candles = self.api.get_candles(asset, timeframe, self.config.velas_medias)
            if candles:
                trend = self._analyze_moving_averages(candles, self.config.velas_medias)
        else:
            candles = self.api.get_candles(asset, timeframe, candles_count)
            trend = None
        
        if not candles or len(candles) < 3:
            self._log("Erro ao obter velas para análise", "ERROR")
            return None
        
        try:
            # Validate that returned candles are M1 (60 seconds timeframe)
            if len(candles) >= 3:
                step1 = int(candles[-1]['from']) - int(candles[-2]['from'])
                step2 = int(candles[-2]['from']) - int(candles[-3]['from'])
                if not (50 <= step1 <= 70 and 50 <= step2 <= 70):
                    # One quick re-fetch attempt
                    alt = self.api.get_candles(asset, timeframe, max(candles_count, 5))
                    if alt and len(alt) >= 3:
                        s1 = int(alt[-1]['from']) - int(alt[-2]['from'])
                        s2 = int(alt[-2]['from']) - int(alt[-3]['from'])
                        if 50 <= s1 <= 70 and 50 <= s2 <= 70:
                            candles = alt
                        else:
                            self._log("MHI M1: timeframe inconsistente (dados não são M1). Abortando análise.", "WARNING")
                            return None
                    else:
                        self._log("MHI M1: histórico insuficiente após re-tentativa. Abortando análise.", "WARNING")
                        return None
        except Exception:
            # Fail safe: proceed without validation
            pass
        
        try:
            # Selecionar SEMPRE as 3 últimas velas fechadas imediatamente anteriores ao momento da análise
            c_sel = [candles[-3], candles[-2], candles[-1]]
            keys = [int(c_sel[0]['from']), int(c_sel[1]['from']), int(c_sel[2]['from'])]
            # Debug de seleção
            try:
                ts0 = datetime.fromtimestamp(keys[0])
                ts1 = datetime.fromtimestamp(keys[1])
                ts2 = datetime.fromtimestamp(keys[2])
                self._log(
                    f"MHI M1 DEBUG | sel0={ts0.strftime('%H:%M:%S')} "
                    f"sel1={ts1.strftime('%H:%M:%S')} "
                    f"sel2={ts2.strftime('%H:%M:%S')}",
                    "DEBUG"
                )
            except Exception:
                pass
            # Analyze selected 3 candles
            vela1 = 'Verde' if c_sel[0]['open'] < c_sel[0]['close'] else ('Vermelha' if c_sel[0]['open'] > c_sel[0]['close'] else 'Doji')
            vela2 = 'Verde' if c_sel[1]['open'] < c_sel[1]['close'] else ('Vermelha' if c_sel[1]['open'] > c_sel[1]['close'] else 'Doji')
            vela3 = 'Verde' if c_sel[2]['open'] < c_sel[2]['close'] else ('Vermelha' if c_sel[2]['open'] > c_sel[2]['close'] else 'Doji')
            
            colors = [vela1, vela2, vela3]
            
            # Check for doji
            if 'Doji' in colors:
                self._log(f"Velas: {vela1}, {vela2}, {vela3}", "WARNING")
                self._log("Entrada abortada - Foi encontrado um doji na análise.", "WARNING")
                return None
            
            # Determine direction
            green_count = colors.count('Verde')
            red_count = colors.count('Vermelha')
            
            if green_count > red_count:
                direction = 'put'
            elif red_count > green_count:
                direction = 'call'
            else:
                return None
            
            # Check against trend if configured
            if self.config.analise_medias and trend:
                if direction != trend:
                    self._log(f"Velas: {vela1}, {vela2}, {vela3}", "WARNING")
                    self._log("Entrada abortada - Contra Tendência.", "WARNING")
                    return None
            
            self._log(f"Velas: {vela1}, {vela2}, {vela3} - Entrada para {direction.upper()}", "INFO")
            return direction
            
        except Exception as e:
            self._log(f"Erro na análise MHI: {str(e)}", "ERROR")
            return None


class TorresGemeasStrategy(BaseStrategy):
    """Torres Gêmeas Strategy - Análise de 1 vela"""
    
    def run(self, asset: str):
        """Execute Torres Gêmeas strategy"""
        self._log(f"Iniciando estratégia Torres Gêmeas para {asset}", "INFO")
        
        operation_type, current_asset = self._determine_operation_type(asset)
        if not operation_type or not current_asset:
            return
        
        if current_asset != asset:
            asset = current_asset
        # Manter pré-aquecimento DIGITAL persistente para reduzir misses de instrument_id
        try:
            if operation_type == 'digital':
                with self.api._api_lock:
                    if getattr(self.api, 'subscribe_strike_list', None):
                        self.api.subscribe_strike_list(asset, 1)
                setattr(self, '_torres_digital_sub_asset', asset)
        except Exception:
            pass
        
        while self.running and self._check_stop_conditions():
            try:
                # Periodically check if asset is still available/best (mirror MHI loop)
                if hasattr(self, '_last_asset_check_torres'):
                    if time.time() - self._last_asset_check_torres > 300:  # Check every 5 minutes
                        new_operation_type, new_asset = self._determine_operation_type(asset)
                        if new_asset and new_asset != asset:
                            self._log(f"Mudando de {asset} para {new_asset}", "INFO")
                            # Atualizar assinatura digital persistente ao trocar de ativo
                            try:
                                if operation_type == 'digital':
                                    prev = getattr(self, '_torres_digital_sub_asset', None)
                                    if prev and prev != new_asset and getattr(self.api, 'unsubscribe_strike_list', None):
                                        with self.api._api_lock:
                                            self.api.unsubscribe_strike_list(prev, 1)
                                    with self.api._api_lock:
                                        if getattr(self.api, 'subscribe_strike_list', None):
                                            self.api.subscribe_strike_list(new_asset, 1)
                                    setattr(self, '_torres_digital_sub_asset', new_asset)
                            except Exception:
                                pass
                            asset = new_asset
                            operation_type = new_operation_type
                        self._last_asset_check_torres = time.time()
                else:
                    self._last_asset_check_torres = time.time()
                # Payout cache warm-up (executed sparingly to avoid heavy vendor calls in the gate)
                try:
                    warm_interval = int(getattr(self.config, 'torres_payout_warmup_sec', 90))
                except Exception:
                    warm_interval = 90
                try:
                    last_warm = getattr(self, '_torres_last_payout_warm', 0)
                except Exception:
                    last_warm = 0
                try:
                    if time.time() - float(last_warm or 0) >= max(30, warm_interval):
                        # This fetches and stores both digital and binary payouts in the API cache
                        _ = self.api.get_payout(asset)
                        try:
                            setattr(self, '_torres_last_payout_warm', time.time())
                        except Exception:
                            pass
                except Exception:
                    # Never break loop due to warm-up failures
                    pass
                # Opcional: disparo por evento (sem gate de minuto) quando habilitado em config
                try:
                    event_driven = bool(getattr(self.config, 'torres_event_driven', False))
                    cooldown = int(getattr(self.config, 'torres_event_cooldown_sec', 45))
                except Exception:
                    event_driven = False
                    cooldown = 45
                if event_driven:
                    last_sig = getattr(self, '_torres_last_signal_time', 0)
                    if time.time() - float(last_sig or 0) >= max(5, cooldown):
                        direction_ev = self._analyze_torres_pattern(asset)
                        if direction_ev in ['put', 'call']:
                            # Pré-aquecer DIGITAL se for o tipo preferido
                            try:
                                if operation_type == 'digital' and hasattr(self.api, '_api_lock') and getattr(self.api, 'subscribe_strike_list', None):
                                    with self.api._api_lock:
                                        self.api.subscribe_strike_list(asset, 1)
                            except Exception:
                                pass
                            self._execute_trade(asset, direction_ev, 1, operation_type)
                            self._log("-" * 30, "INFO")
                            try:
                                setattr(self, '_torres_last_signal_time', time.time())
                            except Exception:
                                pass
                            # Evitar dupla entrada no mesmo ciclo
                            time.sleep(0.1)
                            continue
                # Precise gate (same cadence as MHI M1)
                if self._is_entry_time_torres():
                    direction = self._analyze_torres_pattern(asset)
                
                    if direction in ['put', 'call']:
                        # Pré-aquecer DIGITAL: assinar strike list antes de enviar ordem
                        try:
                            if operation_type == 'digital' and hasattr(self.api, '_api_lock') and getattr(self.api, 'subscribe_strike_list', None):
                                with self.api._api_lock:
                                    self.api.subscribe_strike_list(asset, 1)
                        except Exception:
                            pass
                        self._execute_trade(asset, direction, 1, operation_type)
                        self._log("-" * 30, "INFO")
                
                time.sleep(0.1)
                
            except Exception as e:
                self._log(f"Erro na estratégia Torres Gêmeas: {str(e)}", "ERROR")
                time.sleep(5)
    
    def _analyze_torres_pattern(self, asset: str) -> Optional[str]:
        """Analyze Torres Gêmeas (Twin Towers) pattern using neckline breakout confirmation.
        - Double Top (PUT): duas máximas similares (A e C) com um vale (B) entre elas, entra no rompimento ABAIXO da neckline (mínimo entre A e C).
        - Double Bottom (CALL): duas mínimas similares (A e C) com um pico (B) entre elas, entra no rompimento ACIMA da neckline (máximo entre A e C).
        """
        timeframe = int(getattr(self.config, 'torres_timeframe', 60))  # M1 por padrão
        lookback = int(getattr(self.config, 'torres_lookback', 60))    # histórico p/ detectar A-B-C

        # Buscar candles e, opcionalmente, tendência por médias
        trend = None
        candles = None
        try:
            candles = self.api.get_candles(asset, timeframe, max(lookback, getattr(self.config, 'velas_medias', 20)))
            if self.config.analise_medias and candles:
                trend = self._analyze_moving_averages(candles, self.config.velas_medias)
        except Exception as e:
            self._log(f"Erro ao obter candles para Torres Gêmeas: {str(e)}", "ERROR")
            candles = None

        if not candles or len(candles) < 10:
            self._log("Erro ao obter velas para análise Torres Gêmeas (histórico insuficiente)", "ERROR")
            return None

        try:
            highs = [c['max'] if 'max' in c else c.get('high', c['close']) for c in candles]
            lows = [c['min'] if 'min' in c else c.get('low', c['close']) for c in candles]
            closes = [c['close'] for c in candles]
            n = len(candles)

            def is_top(i: int) -> bool:
                return highs[i] > highs[i-1] and highs[i] > highs[i+1]

            def is_bottom(i: int) -> bool:
                return lows[i] < lows[i-1] and lows[i] < lows[i+1]

            top_idx = [i for i in range(2, n-2) if is_top(i)]
            bot_idx = [i for i in range(2, n-2) if is_bottom(i)]

            # Parâmetros de similaridade/rompimento
            tolerance_pct = float(getattr(self.config, 'torres_tolerancia_pct', 0.05))  # 0.05% ~ 5 pips
            break_buffer_pct = float(getattr(self.config, 'torres_break_buffer_pct', 0.0))

            signal = None
            signal_idx = -1

            # 1) Double Top (PUT)
            if len(top_idx) >= 2:
                t2 = top_idx[-1]
                t1 = top_idx[-2]
                if t1 < t2:
                    # Vale(s) entre t1 e t2 e neckline = menor LOW nesse intervalo
                    if any((t1 < b < t2) for b in bot_idx):
                        neckline_low = min(lows[t1:t2+1])
                        # Similaridade das máximas
                        ref = (highs[t1] + highs[t2]) / 2.0
                        if ref > 0:
                            diff_pct = abs(highs[t1] - highs[t2]) / ref * 100.0
                            if diff_pct <= tolerance_pct:
                                last_close = closes[-1]
                                thresh = neckline_low * (1.0 - break_buffer_pct/100.0)
                                broken = last_close < thresh
                                try:
                                    self._log(
                                        f"TwinTop det.: A={highs[t1]:.5f}@{t1}, C={highs[t2]:.5f}@{t2}, neck={neckline_low:.5f}, close={last_close:.5f}, diff={diff_pct:.3f}% -> romp={broken}",
                                        "DEBUG"
                                    )
                                except Exception:
                                    pass
                                if broken:
                                    signal = 'put'
                                    signal_idx = max(t1, t2)

            # 2) Double Bottom (CALL)
            if len(bot_idx) >= 2:
                b2 = bot_idx[-1]
                b1 = bot_idx[-2]
                if b1 < b2:
                    # Pico(s) entre b1 e b2 e neckline = maior HIGH nesse intervalo
                    if any((b1 < t < b2) for t in top_idx):
                        neckline_high = max(highs[b1:b2+1])
                        # Similaridade das mínimas
                        ref = (lows[b1] + lows[b2]) / 2.0
                        if ref > 0:
                            diff_pct = abs(lows[b1] - lows[b2]) / ref * 100.0
                            if diff_pct <= tolerance_pct:
                                last_close = closes[-1]
                                thresh = neckline_high * (1.0 + break_buffer_pct/100.0)
                                broken = last_close > thresh
                                try:
                                    self._log(
                                        f"TwinBottom det.: A={lows[b1]:.5f}@{b1}, C={lows[b2]:.5f}@{b2}, neck={neckline_high:.5f}, close={last_close:.5f}, diff={diff_pct:.3f}% -> romp={broken}",
                                        "DEBUG"
                                    )
                                except Exception:
                                    pass
                                if broken:
                                    # Se já houver PUT, escolher o padrão mais recente
                                    if signal is None or b2 > signal_idx:
                                        signal = 'call'
                                        signal_idx = max(b1, b2)

            if signal in ['put', 'call']:
                # Respeitar filtro de tendência, se habilitado
                if self.config.analise_medias and trend:
                    if signal != trend:
                        self._log("Entrada abortada - Contra Tendência.", "WARNING")
                        return None
                self._log(f"Torres Gêmeas (neckline) confirmado - Entrada para {signal.upper()}", "INFO")
                return signal

            return None
        except Exception as e:
            self._log(f"Erro na análise Torres Gêmeas (neckline): {str(e)}", "ERROR")
            return None


class MHIM5Strategy(BaseStrategy):
    """MHI M5 Strategy - Análise de 3 velas em timeframe de 5 minutos"""
    
    def run(self, asset: str):
        """Execute MHI M5 strategy"""
        self._log(f"Iniciando estratégia MHI M5 para {asset}", "INFO")
        
        operation_type, current_asset = self._determine_operation_type(asset)
        if not operation_type or not current_asset:
            return
        if current_asset != asset:
            asset = current_asset
        
        # Pré-cálculo de direção para reduzir atraso: compute próximo sinal no final da vela atual
        pending_target_idx = None
        pending_direction = None
        
        while self.running and self._check_stop_conditions():
            try:
                # Periodically check if asset is still available
                if hasattr(self, '_last_asset_check_mhi5'):
                    if time.time() - self._last_asset_check_mhi5 > 300:  # Check every 5 minutes
                        new_operation_type, new_asset = self._determine_operation_type(asset)
                        if new_asset and new_asset != asset:
                            self._log(f"Mudando de {asset} para {new_asset}", "INFO")
                            asset = new_asset
                            operation_type = new_operation_type
                        self._last_asset_check_mhi5 = time.time()
                else:
                    self._last_asset_check_mhi5 = time.time()

                # Pré-cálculo no fim da vela (evita atrasar a entrada no início da próxima)
                try:
                    st, dt = self._server_dt()
                    sec = float(st) % 60.0
                    minute_idx = int(st) // 60
                    minute_in_block_30 = minute_idx % 30
                except Exception:
                    sec = 0.0
                    minute_idx = int(time.time()) // 60
                    try:
                        minute_in_block_30 = minute_idx % 30
                    except Exception:
                        minute_in_block_30 = 0

                # Pré-cálculo apenas no minuto 29 do bloco (analisando as 3 últimas velas M5 fechadas),
                # para entrar no minuto 0 do próximo bloco (30 min)
                if minute_in_block_30 == 29 and 58.0 <= sec <= 59.9 and pending_target_idx != minute_idx + 1:
                    # Calcular direção baseada nas 3 últimas velas M5 fechadas
                    d = self._analyze_mhi_m5_pattern(asset)
                    if d in ['put', 'call']:
                        pending_direction = d
                        pending_target_idx = minute_idx + 1
                        # Pré-aquecer DIGITAL: assinar strike list com antecedência quando planejamos entrar na próxima vela
                        try:
                            # Sempre pré-aquecer DIGITAL, mesmo quando a operação preferida é BINARY
                            if hasattr(self.api, '_api_lock') and getattr(self.api, 'subscribe_strike_list', None):
                                with self.api._api_lock:
                                    self.api.subscribe_strike_list(asset, 5)  # 5-minute expiration
                                    # Aguardar um pouco para o sistema se preparar
                                    time.sleep(0.5)
                        except Exception:
                            pass
                        try:
                            self._log(
                                f"Pré-cálculo MHI M5 pronto | direção={d.upper()} | alvo_min_idx={pending_target_idx} | minuto_bloco30={minute_in_block_30}",
                                "DEBUG"
                            )
                        except Exception:
                            pass

                # Gate exato no início da vela nova (minutos 0 e 30)
                if self._is_entry_time_mhi_m5():
                    # Usar direção pré-calculada para o minuto atual, se existir
                    st_now = self.api.get_server_timestamp()
                    curr_minute_idx = int(st_now) // 60
                    if pending_direction in ['put', 'call'] and pending_target_idx == curr_minute_idx:
                        direction = pending_direction
                        self._log(f"Usando direção pré-calculada: {direction.upper()}", "INFO")
                    else:
                        direction = self._analyze_mhi_m5_pattern(asset)
                    
                    if direction in ['put', 'call']:
                        # Pré-aquecer DIGITAL imediatamente antes da entrada
                        try:
                            if hasattr(self.api, '_api_lock') and getattr(self.api, 'subscribe_strike_list', None):
                                with self.api._api_lock:
                                    self.api.subscribe_strike_list(asset, 5)
                        except Exception:
                            pass
                        self._execute_trade(asset, direction, 5, operation_type)  # 5-minute expiration
                        self._log("-" * 30, "INFO")
                    # Resetar pré-cálculo após tentativa de entrada
                    pending_direction = None
                    pending_target_idx = None
                
                time.sleep(0.1)
                
            except Exception as e:
                self._log(f"Erro na estratégia MHI M5: {str(e)}", "ERROR")
                time.sleep(5)
    
    def _analyze_mhi_m5_pattern(self, asset: str) -> Optional[str]:
        """Analyze MHI M5 pattern (3 candles in 5-minute timeframe)"""
        timeframe = 300  # 5 minutes
        candles_count = 3
        
        # Get moving averages if configured
        if self.config.analise_medias:
            candles = self.api.get_candles(asset, timeframe, self.config.velas_medias)
            if candles:
                trend = self._analyze_moving_averages(candles, self.config.velas_medias)
        else:
            candles = self.api.get_candles(asset, timeframe, candles_count)
            trend = None
        
        if not candles or len(candles) < 3:
            self._log("Erro ao obter velas para análise", "ERROR")
            return None
        
        try:
            # Analyze last 3 candles
            vela1 = 'Verde' if candles[-3]['open'] < candles[-3]['close'] else ('Vermelha' if candles[-3]['open'] > candles[-3]['close'] else 'Doji')
            vela2 = 'Verde' if candles[-2]['open'] < candles[-2]['close'] else ('Vermelha' if candles[-2]['open'] > candles[-2]['close'] else 'Doji')
            vela3 = 'Verde' if candles[-1]['open'] < candles[-1]['close'] else ('Vermelha' if candles[-1]['open'] > candles[-1]['close'] else 'Doji')
            
            colors = [vela1, vela2, vela3]
            
            # Check for doji
            if 'Doji' in colors:
                self._log(f"Velas: {vela1}, {vela2}, {vela3}", "WARNING")
                self._log("Entrada abortada - Foi encontrado um doji na análise.", "WARNING")
                return None
            
            # Determine direction
            green_count = colors.count('Verde')
            red_count = colors.count('Vermelha')
            
            if green_count > red_count:
                direction = 'put'
            elif red_count > green_count:
                direction = 'call'
            else:
                return None
            
            # Check against trend if configured
            if self.config.analise_medias and trend:
                if direction != trend:
                    self._log(f"Velas: {vela1}, {vela2}, {vela3}", "WARNING")
                    self._log("Entrada abortada - Contra Tendência.", "WARNING")
                    return None
            
            self._log(f"Velas: {vela1}, {vela2}, {vela3} - Entrada para {direction.upper()}", "INFO")
            return direction
            
        except Exception as e:
            self._log(f"Erro na análise MHI M5: {str(e)}", "ERROR")
            return None


# Import new strategies
from .rsi_strategy import RSIStrategy
from .moving_average_strategy import MovingAverageStrategy
from .bollinger_strategy import BollingerBandsStrategy

# Strategy factory - Combined existing and new strategies
STRATEGIES = {
    # Existing strategies
    'mhi': MHIStrategy,
    'torres_gemeas': TorresGemeasStrategy,
    'mhi_m5': MHIM5Strategy,
    # New strategies
    'rsi': RSIStrategy,
    'moving_average': MovingAverageStrategy,
    'bollinger_bands': BollingerBandsStrategy,
    'engulfing': EngulfingStrategy,
    'candlestick': CandlestickStrategy,
    'macd': MACDStrategy,
}


def get_strategy(strategy_name: str, api: IQOptionAPI, session: TradingSession) -> Optional[BaseStrategy]:
    """Get strategy instance by name (existing + new strategies)"""
    strategy_class = STRATEGIES.get(strategy_name.lower())
    if strategy_class:
        return strategy_class(api, session)
    return None


def get_strategy_info():
    """Get information about all available strategies"""
    return {
        # Existing strategies
        'mhi': {
            'name': 'MHI',
            'description': 'Análise de 3 velas em timeframe M1',
            'timeframe': 'M1',
            'expiration': '1 minuto',
            'type': 'candlestick_pattern'
        },
        'torres_gemeas': {
            'name': 'Torres Gêmeas',
            'description': 'Análise de padrão Twin Towers com neckline breakout',
            'timeframe': 'M1',
            'expiration': '1 minuto',
            'type': 'pattern_recognition'
        },
        'mhi_m5': {
            'name': 'MHI M5',
            'description': 'Análise de 3 velas em timeframe M5',
            'timeframe': 'M5',
            'expiration': '5 minutos',
            'type': 'candlestick_pattern'
        },
        # New strategies
        'rsi': {
            'name': 'RSI',
            'description': 'Relative Strength Index - Identifica sobrecompra/sobrevenda',
            'timeframe': 'M1',
            'expiration': '1 minuto',
            'type': 'technical_indicator',
            'parameters': {
                'rsi_period': 14,
                'rsi_oversold': 30,
                'rsi_overbought': 70
            }
        },
        'moving_average': {
            'name': 'Moving Average Crossover',
            'description': 'Cruzamento de médias móveis (Golden/Death Cross)',
            'timeframe': 'M1',
            'expiration': '1 minuto',
            'type': 'technical_indicator',
            'parameters': {
                'ma_fast_period': 9,
                'ma_slow_period': 21,
                'ma_confirmation_candles': 2
            }
        },
        'bollinger_bands': {
            'name': 'Bollinger Bands',
            'description': 'Bandas de Bollinger - Toque nas bandas superior/inferior',
            'timeframe': 'M1',
            'expiration': '1 minuto',
            'type': 'technical_indicator',
            'parameters': {
                'bb_period': 20,
                'bb_std_dev': 2.0,
                'bb_touch_threshold': 0.001
            }
        },
        'engulfing': {
            'name': 'Engolfo (Engulfing)',
            'description': 'Padrão de candlestick Engulfing - reversão de tendência',
            'timeframe': 'M1',
            'expiration': '1 minuto',
            'type': 'candlestick_pattern',
            'parameters': {
                'engulfing_min_body_ratio': 1.2,
                'engulfing_confirmation_candles': 1
            }
        },
        'candlestick': {
            'name': 'Padrões de Candlestick',
            'description': 'Múltiplos padrões: Hammer, Doji, Pin Bar, Marubozu, etc.',
            'timeframe': 'M1',
            'expiration': '1 minuto',
            'type': 'candlestick_pattern',
            'parameters': {
                'cs_body_threshold': 0.3,
                'cs_shadow_ratio': 2.0,
                'cs_doji_threshold': 0.1
            }
        },
        'macd': {
            'name': 'MACD',
            'description': 'Moving Average Convergence Divergence - cruzamentos e divergências',
            'timeframe': 'M1',
            'expiration': '1 minuto',
            'type': 'technical_indicator',
            'parameters': {
                'macd_fast_period': 12,
                'macd_slow_period': 26,
                'macd_signal_period': 9,
                'macd_min_histogram': 0.00001
            }
        },
        'enhanced': {
            'name': 'Estratégia Aprimorada',
            'description': 'Sistema com estratégia principal + filtros de confirmação para maior assertividade',
            'timeframe': 'Configurável',
            'expiration': 'Baseado na estratégia principal',
            'type': 'hybrid_system',
            'parameters': {
                'primary_strategy': 'mhi',
                'confirmation_filters': ['macd', 'bollinger_bands', 'rsi'],
                'min_confirmations': 1,
                'confirmation_weight_threshold': 0.6,
                'strategy_weights': {
                    'macd': 0.25,
                    'bollinger_bands': 0.25,
                    'rsi': 0.20,
                    'moving_average': 0.15,
                    'engulfing': 0.10,
                    'candlestick': 0.05
                }
            }
        }
    }
