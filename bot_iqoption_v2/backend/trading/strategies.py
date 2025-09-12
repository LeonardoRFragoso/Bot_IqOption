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
        
    def start(self):
        """Start strategy execution"""
        self.running = True
        self._log("Estratégia iniciada", "INFO")
        
    def stop(self):
        """Stop strategy execution"""
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
        if self.session.total_profit <= -abs(self.config.stop_loss):
            self._log(f"STOP LOSS BATIDO: ${self.session.total_profit}", "ERROR")
            self.session.status = 'STOPPED'
            self.session.save()
            return False
            
        if self.session.total_profit >= abs(self.config.stop_win):
            self._log(f"STOP WIN BATIDO: ${self.session.total_profit}", "INFO")
            self.session.status = 'STOPPED'
            self.session.save()
            return False
            
        return True
    
    def _determine_operation_type(self, asset: str) -> Tuple[str, str]:
        """Determine best operation type and asset based on payouts"""
        if self.config.tipo != 'automatico':
            # Check if current asset is available
            payouts = self.api.get_payout(asset)
            if payouts['digital'] == 0 and payouts['turbo'] == 0 and payouts['binary'] == 0:
                # Try to find alternative asset
                alternative_asset = self.api.get_best_available_asset()
                if alternative_asset:
                    self._log(f"Ativo {asset} fechado, mudando para {alternative_asset}", "WARNING")
                    return self.config.tipo, alternative_asset
                else:
                    self._log("Nenhum ativo disponível no momento", "ERROR")
                    return None, None
            return self.config.tipo, asset
            
        payouts = self.api.get_payout(asset)
        self._log(f"Payouts - Binary: {payouts['binary']}%, Turbo: {payouts['turbo']}%, Digital: {payouts['digital']}%", "INFO")
        
        # Check if any payout is available
        if payouts['digital'] == 0 and payouts['turbo'] == 0 and payouts['binary'] == 0:
            # Try to find alternative asset automatically
            alternative_asset = self.api.get_best_available_asset()
            if alternative_asset:
                self._log(f"Ativo {asset} fechado, mudando para {alternative_asset}", "WARNING")
                alt_payouts = self.api.get_payout(alternative_asset)
                
                # Prefer open instruments with highest payout
                alt_open = {
                    'digital': getattr(self.api, 'is_asset_open', lambda a, t: True)(alternative_asset, 'digital'),
                    'turbo': getattr(self.api, 'is_asset_open', lambda a, t: True)(alternative_asset, 'turbo'),
                    'binary': getattr(self.api, 'is_asset_open', lambda a, t: True)(alternative_asset, 'binary'),
                }
                ordered = sorted([
                    ('digital', alt_payouts['digital'], alt_open['digital']),
                    ('turbo', alt_payouts['turbo'], alt_open['turbo']),
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
            'turbo': getattr(self.api, 'is_asset_open', lambda a, t: True)(asset, 'turbo'),
            'binary': getattr(self.api, 'is_asset_open', lambda a, t: True)(asset, 'binary'),
        }
        ordered = sorted([
            ('digital', payouts['digital'], open_types['digital']),
            ('turbo', payouts['turbo'], open_types['turbo']),
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
                'turbo': getattr(self.api, 'is_asset_open', lambda a, t: True)(alternative_asset, 'turbo'),
                'binary': getattr(self.api, 'is_asset_open', lambda a, t: True)(alternative_asset, 'binary'),
            }
            ordered = sorted([
                ('digital', alt_payouts['digital'], alt_open['digital']),
                ('turbo', alt_payouts['turbo'], alt_open['turbo']),
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
                max_payout = max(payouts['digital'], payouts['turbo'], payouts['binary'])
                
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
        
        for gale_level in range(martingale_levels + 1):
            if not self.running or not self._check_stop_conditions():
                return False
            
            # Apply martingale multiplier
            if gale_level > 0:
                entry_value = round(entry_value * float(self.config.martingale_fator), 2)
            
            # Diagnostic log before attempting to buy
            self._log(
                f"Preparando ordem | Par: {asset} | Tipo: {operation_type} | Direção: {direction.upper()} | Expiração: {expiration}m | Valor: ${entry_value}",
                "INFO"
            )
            
            # Place order
            success, order_id = self.api.buy_option(
                asset=asset,
                amount=entry_value,
                direction=direction,
                expiration=expiration,
                option_type=operation_type
            )
            
            # Diagnostic: log immediate result from API
            if success:
                self._log(f"buy_option retornou sucesso | order_id={order_id}", "INFO")
            else:
                self._log(f"buy_option falhou imediatamente | order_id={order_id}", "ERROR")
                self._log(f"Erro ao abrir ordem no ativo {asset}", "ERROR")
                continue
            
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
            
            # Wait for result
            result = self._wait_for_result(operation, operation_type)
            
            if result and result > 0:
                # Win - break martingale sequence
                self._handle_win(operation, result, gale_level)
                return True
            elif result is not None:
                # Loss or draw
                self._handle_loss(operation, result, gale_level)
                
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
                
            time.sleep(1)
        
        self._log(f"Timeout aguardando resultado da operação {operation.id}", "WARNING")
        return None
    
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
                
                # Get server time
                server_time = self.api.get_server_timestamp()
                minutes = float(datetime.fromtimestamp(server_time, tz=timezone.utc).strftime('%M.%S'))
                
                # Check entry time (M5 and M0)
                entry_time = (minutes >= 4.59 and minutes <= 5.00) or minutes >= 9.59
                
                if entry_time:
                    direction = self._analyze_mhi_pattern(asset)
                    
                    if direction in ['put', 'call']:
                        self._execute_trade(asset, direction, 1, operation_type)
                        self._log("-" * 30, "INFO")
                    
                time.sleep(0.5)
                
            except Exception as e:
                self._log(f"Erro na estratégia MHI: {str(e)}", "ERROR")
                time.sleep(5)
    
    def _analyze_mhi_pattern(self, asset: str) -> Optional[str]:
        """Analyze MHI pattern (3 candles analysis)"""
        timeframe = 60
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
                # Get server time
                server_time = self.api.get_server_timestamp()
                minutes = float(datetime.fromtimestamp(server_time, tz=timezone.utc).strftime('%M.%S')[1:])
                
                # Check entry time (M4 and M9)
                entry_time = (minutes >= 3.59 and minutes <= 4.00) or (minutes >= 8.59 and minutes <= 9.00)
                
                if entry_time:
                    direction = self._analyze_torres_pattern(asset)
                    
                    if direction in ['put', 'call']:
                        self._execute_trade(asset, direction, 1, operation_type)
                        self._log("-" * 30, "INFO")
                    
                time.sleep(0.5)
                
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
                # Get server time
                server_time = self.api.get_server_timestamp()
                minutes = float(datetime.fromtimestamp(server_time, tz=timezone.utc).strftime('%M.%S'))
                
                # Check entry time (M30 and M0)
                entry_time = (minutes >= 29.59 and minutes <= 30.00) or minutes == 59.59
                
                if entry_time:
                    direction = self._analyze_mhi_m5_pattern(asset)
                    
                    if direction in ['put', 'call']:
                        self._execute_trade(asset, direction, 5, operation_type)  # 5-minute expiration
                        self._log("-" * 30, "INFO")
                    
                time.sleep(0.5)
                
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
