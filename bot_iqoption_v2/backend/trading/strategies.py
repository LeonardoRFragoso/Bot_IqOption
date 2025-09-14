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
            try:
                self._log(f"GATE MHI | min_bloco={minute_in_block} | sec={sec:.2f}", "DEBUG")
            except Exception:
                pass
            return self._gate_once('mhi', st)
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
            try:
                self._log(f"GATE TORRES | min_bloco={minute_in_block} | sec={sec:.2f}", "DEBUG")
            except Exception:
                pass
            return self._gate_once('torres', st)
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
            try:
                self._log(f"GATE MHI5 | min_bloco30={minute_in_block_30} | sec={sec:.2f}", "DEBUG")
            except Exception:
                pass
            return self._gate_once('mhi_m5', st)
        return False

    # ------------------ Execution helpers ------------------
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
    
    def _determine_operation_type(self, asset: str) -> Tuple[str, str]:
        """Determine best operation type and asset based on payouts"""
        # Operação automática: somente DIGITAL ou BINARY (sem TURBO)
        if self.config.tipo == 'automatico':
            payouts = self.api.get_payout(asset)
            digital = payouts.get('digital', 0) or 0
            binary = payouts.get('binary', 0) or 0
            # Heurísticas para reduzir atraso de entrada:
            # - Preferir SEMPRE BINARY em OTC (evita quedas e atrasos de digital nos fins de semana)
            # - Preferir BINARY em caso de empate de payout (reduz risco de atraso no ACK do digital)
            # - Preferir BINARY se já passamos de 1s do minuto (entrada tardia em digital costuma atrasar)
            # - Usar DIGITAL apenas quando vantagem for significativa e ainda estivermos no início do minuto
            try:
                st = float(self.api.get_server_timestamp())
                sec = st % 60.0
            except Exception:
                sec = 0.0
            asset_upper = str(asset).upper()
            is_otc = asset_upper.endswith('-OTC')
            digital_better_margin = digital - binary  # margem de vantagem do digital
            # Regra 1: OTC → BINARY (evita atrasos recorrentes nas digitais OTC)
            if is_otc and binary > 0:
                self._log("OTC detectado — preferindo BINARY para evitar atrasos", "INFO")
                return 'binary', asset
            # Regra 2: Se payouts forem IGUAIS (>0), preferir BINARY por estabilidade
            if digital > 0 and digital == binary and binary > 0:
                self._log("Payouts iguais — preferindo BINARY por estabilidade/latência", "INFO")
                return 'binary', asset
            # Regra 3: Após 1s do minuto → BINARY (para 1m)
            if sec > 1.0 and binary > 0:
                self._log("Segundo atual > 1s — preferindo BINARY para entrada imediata", "INFO")
                return 'binary', asset
            # Regra 4: DIGITAL somente com vantagem relevante (>=10pp) e no início do minuto
            if digital >= binary + 10 and sec <= 1.0 and digital > 0:
                self._log("Operações serão realizadas nas digital (vantagem significativa)", "INFO")
                return 'digital', asset
            # Padrão: se ambos > 0, escolher o maior payout
            if max(digital, binary) > 0:
                chosen = 'digital' if digital >= binary else 'binary'
                self._log(f"Operações serão realizadas nas {chosen}", "INFO")
                return chosen, asset
            # Se DIGITAL indisponível, tentar encontrar outro ativo com DIGITAL disponível
            alt = None
            try:
                alt = self.api.get_best_available_asset()
            except Exception:
                pass
            if alt and alt != asset:
                self._log(f"Par {asset} sem payout digital. Alternando para {alt}", "WARNING")
                return self._determine_operation_type(alt)
            # Como último recurso, permitir BINARY (não-turbo) para compatibilidade
            if binary > 0:
                self._log("Digital indisponível. Utilizando binary.", "WARNING")
                return 'binary', asset
            self._log("Par fechado, escolha outro", "ERROR")
            return None, None
        else:
            # Check if current asset is available
            payouts = self.api.get_payout(asset)
            # Remover TURBO da consideração
            if payouts['digital'] == 0 and payouts['binary'] == 0:
                # Try to find alternative asset
                alternative_asset = self.api.get_best_available_asset()
                if alternative_asset:
                    self._log(f"Ativo {asset} fechado, mudando para {alternative_asset}", "WARNING")
                    asset = alternative_asset
                    payouts = self.api.get_payout(asset)
                else:
                    self._log("Nenhum ativo disponível no momento", "ERROR")
                    return None, None
            # Mapear configuração manual 'turbo' para 'digital'
            tipo = getattr(self.config, 'tipo', 'digital')
            if str(tipo).lower() == 'turbo':
                self._log("Operações TURBO desativadas. Usando DIGITAL.", "WARNING")
                tipo = 'digital'
            return tipo, asset
            
        payouts = self.api.get_payout(asset)
        self._log(f"Payouts - Binary: {payouts['binary']}%, Digital: {payouts['digital']}%", "INFO")
        
        # Check if any payout is available
        if payouts['digital'] == 0 and payouts['binary'] == 0:
            # Try to find alternative asset automatically
            alternative_asset = self.api.get_best_available_asset()
            if alternative_asset:
                self._log(f"Ativo {asset} fechado, mudando para {alternative_asset}", "WARNING")
                alt_payouts = self.api.get_payout(alternative_asset)
                
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
            alt_payouts = self.api.get_payout(alternative_asset)
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
            # Log attempt details
            try:
                total_levels = martingale_levels
                label = 'Entrada' if gale_level == 0 else f'Gale {gale_level}'
                st_dbg = float(self.api.get_server_timestamp())
                hhmmss = datetime.utcfromtimestamp(st_dbg).strftime('%H:%M:%S')
                sec_dbg = int(st_dbg % 60)
                self._log(
                    f"Tentativa {label} | Nível {gale_level}/{total_levels} | Valor calculado: ${entry_value} | server={hhmmss} (sec={sec_dbg:02d})",
                    "INFO"
                )
            except Exception:
                pass
            
            # Determinar tipo efetivo sem forçar DIGITAL (respeita decisão anterior)
            actual_operation_type = operation_type

            # Diagnostic log before attempting to buy
            try:
                st_dbg2 = float(self.api.get_server_timestamp())
                hhmmss2 = datetime.utcfromtimestamp(st_dbg2).strftime('%H:%M:%S')
                sec_dbg2 = int(st_dbg2 % 60)
                self._log(
                    f"Preparando ordem | Par: {asset} | Tipo: {actual_operation_type} | Direção: {direction.upper()} | Expiração: {expiration}m | Valor: ${entry_value} | server={hhmmss2} (sec={sec_dbg2:02d})",
                    "INFO"
                )
            except Exception:
                self._log(
                    f"Preparando ordem | Par: {asset} | Tipo: {actual_operation_type} | Direção: {direction.upper()} | Expiração: {expiration}m | Valor: ${entry_value}",
                    "INFO"
                )
            
            # Place order
            success, order_id = self.api.buy_option(
                asset=asset,
                amount=entry_value,
                direction=direction,
                expiration=expiration,
                option_type=actual_operation_type
            )
            
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
            
            gale_text = f' (Gale {gale_level})' if gale_level > 0 else ''
            self._log(f"Ordem aberta{gale_text} | Par: {asset} | Valor: ${entry_value}", "INFO")
            
            # Wait for result using the actual operation type
            result = self._wait_for_result(operation, actual_operation_type)
            
            if result and result > 0:
                # Win - break martingale sequence
                self._handle_win(operation, result, gale_level)
                return True
            elif result is not None:
                # Loss or draw
                self._handle_loss(operation, result, gale_level)
                # Execute next Gale immediately on the next candle (no extra 1-minute wait)
                if gale_level < martingale_levels:
                    self._log("Executando Gale imediatamente na próxima vela...", "INFO")
                    # Pequeno descanso para garantir sincronização após recebimento do resultado
                    time.sleep(0.1)
                
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
        
        # Handle Soros progression
        if self.config.soros_usar:
            self._update_soros_progression(True, result)
        
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
        
        # Handle Soros progression
        if self.config.soros_usar:
            self._update_soros_progression(False, result)
        
        gale_text = f' (Gale {gale_level})' if gale_level > 0 else ''
        self._log(f"{result_text}{gale_text}", "ERROR" if result < 0 else "WARNING")
    
    def _update_soros_progression(self, won: bool, result: float):
        """Update Soros progression"""
        if won:
            # Increment Soros level on win
            current_level = getattr(self.session, 'soros_level', 0)
            if current_level < self.config.soros_niveis:
                setattr(self.session, 'soros_level', current_level + 1)
                current_value = getattr(self.session, 'soros_value', 0)
                setattr(self.session, 'soros_value', current_value + result)
        else:
            # Reset Soros on loss
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
                            if operation_type == 'digital' and hasattr(self.api, '_api_lock') and getattr(self.api, 'api', None):
                                with self.api._api_lock:
                                    if hasattr(self.api.api, 'subscribe_strike_list'):
                                        self.api.api.subscribe_strike_list(asset, 1)
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
            # Selecionar SEMPRE as 3 últimas velas fechadas imediatamente anteriores ao momento da análise
            c_sel = [candles[-3], candles[-2], candles[-1]]
            keys = [int(c_sel[0]['from']), int(c_sel[1]['from']), int(c_sel[2]['from'])]
            # Debug de seleção
            try:
                ts0 = datetime.fromtimestamp(keys[0])
                ts1 = datetime.fromtimestamp(keys[1])
                ts2 = datetime.fromtimestamp(keys[2])
                idx0 = (keys[0] // 60) % 5
                idx1 = (keys[1] // 60) % 5
                idx2 = (keys[2] // 60) % 5
                self._log(
                    f"MHI DEBUG | sel0={ts0.strftime('%H:%M:%S')}(m%5={idx0}) "
                    f"sel1={ts1.strftime('%H:%M:%S')}(m%5={idx1}) "
                    f"sel2={ts2.strftime('%H:%M:%S')}(m%5={idx2})",
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
        
        while self.running and self._check_stop_conditions():
            try:
                # Precise gate (same cadence as MHI M1)
                if self._is_entry_time_torres():
                    direction = self._analyze_torres_pattern(asset)
                    
                    if direction in ['put', 'call']:
                        self._execute_trade(asset, direction, 1, operation_type)
                        self._log("-" * 30, "INFO")
                
                time.sleep(0.1)
                
            except Exception as e:
                self._log(f"Erro na estratégia Torres Gêmeas: {str(e)}", "ERROR")
                time.sleep(5)
    
    def _analyze_torres_pattern(self, asset: str) -> Optional[str]:
        """Analyze Torres Gêmeas pattern (1 candle analysis)"""
        timeframe = 60
        candles_count = 4
        
        # Get moving averages if configured
        if self.config.analise_medias:
            candles = self.api.get_candles(asset, timeframe, self.config.velas_medias)
            if candles:
                trend = self._analyze_moving_averages(candles, self.config.velas_medias)
        else:
            candles = self.api.get_candles(asset, timeframe, candles_count)
            trend = None
        
        if not candles or len(candles) < 4:
            self._log("Erro ao obter vela para análise", "ERROR")
            return None
        
        try:
            # Analyze 4th candle back
            vela4 = 'Verde' if candles[-4]['open'] < candles[-4]['close'] else ('Vermelha' if candles[-4]['open'] > candles[-4]['close'] else 'Doji')
            
            # Check for doji
            if vela4 == 'Doji':
                self._log(f"Vela de análise: {vela4}", "WARNING")
                self._log("Entrada abortada - Foi encontrado um doji na análise.", "WARNING")
                return None
            
            # Determine direction (same as candle color)
            direction = 'call' if vela4 == 'Verde' else 'put'
            
            # Check against trend if configured
            if self.config.analise_medias and trend:
                if direction != trend:
                    self._log(f"Vela de análise: {vela4}", "WARNING")
                    self._log("Entrada abortada - Contra Tendência.", "WARNING")
                    return None
            
            self._log(f"Vela de análise: {vela4} - Entrada para {direction.upper()}", "INFO")
            return direction
            
        except Exception as e:
            self._log(f"Erro na análise Torres Gêmeas: {str(e)}", "ERROR")
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
        
        while self.running and self._check_stop_conditions():
            try:
                # Precise gate for MHI M5 entries (minutes 29 and 59 end)
                if self._is_entry_time_mhi_m5():
                    direction = self._analyze_mhi_m5_pattern(asset)
                    
                    if direction in ['put', 'call']:
                        self._execute_trade(asset, direction, 5, operation_type)  # 5-minute expiration
                        self._log("-" * 30, "INFO")
                
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


# Strategy factory
STRATEGIES = {
    'mhi': MHIStrategy,
    'torres_gemeas': TorresGemeasStrategy,
    'mhi_m5': MHIM5Strategy,
}


def get_strategy(strategy_name: str, api: IQOptionAPI, session: TradingSession) -> Optional[BaseStrategy]:
    """Get strategy instance by name"""
    strategy_class = STRATEGIES.get(strategy_name.lower())
    if strategy_class:
        return strategy_class(api, session)
    return None
