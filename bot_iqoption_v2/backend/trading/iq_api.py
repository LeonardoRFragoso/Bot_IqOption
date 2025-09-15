"""
IQ Option API integration module
Handles connection and trading operations with IQ Option platform
"""

import time
import logging
import traceback
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import os
import sys
# Garante que o vendor local (backend/iqoptionapi) seja priorizado sobre site-packages
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Importa o vendor local por caminho absoluto de pacote
from iqoptionapi.stable_api import IQ_Option  # type: ignore
import iqoptionapi.constants as IQC  # type: ignore
from iqoptionapi.expiration import get_expiration_time  # type: ignore
import iqoptionapi.global_value as IQGV  # type: ignore
import sys
from django.conf import settings
from django.db import transaction
from .models import TradingLog, MarketData

logger = logging.getLogger(__name__)

class IQOptionAPI:
    """Wrapper class for IQ Option API with enhanced error handling and reconnection"""
    
    def __init__(self, email: str, password: str, user=None):
        self.email = email
        self.password = password
        self.user = user
        self.api = None
        self.connected = False
        self.account_type = 'PRACTICE'
        self.max_reconnect_attempts = 5
        self._api_lock = threading.RLock()
        # Track the last effective order type actually placed at the vendor ('digital' or 'binary')
        self._last_effective_option_type: Optional[str] = None
        # Map each order_id to the effective option type actually used ('digital' or 'binary')
        self._order_type_by_id: Dict[str, str] = {}
        # Lightweight payout cache: asset -> (payouts dict, ts)
        self._payout_cache: Dict[str, Tuple[Dict[str, float], float]] = {}
        
    def connect(self) -> Tuple[bool, str]:
        """Connect to IQ Option platform"""
        try:
            with self._api_lock:
                self.api = IQ_Option(self.email, self.password)
                check, reason = self.api.connect()
        
            if check:
                self.connected = True
                try:
                    mod = sys.modules.get(IQ_Option.__module__)
                    mod_path = getattr(mod, '__file__', 'unknown')
                    self._log_message(f"Vendor iqoptionapi em uso: {mod_path}", "DEBUG")
                except Exception:
                    pass
                self._log_message("Conectado com sucesso à IQ Option", "INFO")
                return True, "Conectado com sucesso"
            else:
                self.connected = False
                error_msg = self._parse_connection_error(reason)
                self._log_message(f"Falha na conexão: {error_msg}", "ERROR")
                return False, error_msg
                
        except Exception as e:
            self.connected = False
            error_msg = f"Erro na conexão: {str(e)}"
            self._log_message(error_msg, "ERROR")
            return False, error_msg
    
    def disconnect(self):
        """Disconnect from IQ Option platform"""
        if self.api:
            try:
                with self._api_lock:
                    self._safe_close()
                self.connected = False
                self.api = None
                self._log_message("Desconectado da IQ Option", "INFO")
            except Exception as e:
                # Não gerar WARNING aqui para não poluir logs; usar DEBUG
                self._log_message(f"Erro ao desconectar (ignorado): {str(e)}", "DEBUG")

    def _safe_close(self):
        """Attempt to close underlying connections using multiple strategies safely"""
        try:
            # 1) Método direto close() se existir
            if hasattr(self.api, 'close') and callable(getattr(self.api, 'close', None)):
                try:
                    self.api.close()
                except Exception:
                    pass
            # 2) Objeto interno 'api' pode expor close()
            inner = getattr(self.api, 'api', None)
            if inner is not None and hasattr(inner, 'close') and callable(getattr(inner, 'close', None)):
                try:
                    inner.close()
                except Exception:
                    pass
            # 3) WebSocket interno
            ws = getattr(self.api, 'websocket', None)
            if ws is not None and hasattr(ws, 'close') and callable(getattr(ws, 'close', None)):
                try:
                    ws.close()
                except Exception:
                    pass
        except Exception:
            # Silencioso por segurança
            pass
    
    def _attempt_reconnection(self) -> bool:
        """Try to reconnect to the IQ Option platform using stored credentials.
        Keeps logs low-noise and restores the previously selected account type.
        """
        try:
            for attempt in range(1, self.max_reconnect_attempts + 1):
                try:
                    # Close current connection if any
                    with self._api_lock:
                        try:
                            self._safe_close()
                        except Exception:
                            pass

                        # Recreate API client and reconnect
                        self.api = IQ_Option(self.email, self.password)
                        ok, reason = self.api.connect()

                    if ok:
                        self.connected = True
                        # Try to restore account type
                        try:
                            with self._api_lock:
                                self.api.change_balance(self.account_type)
                        except Exception:
                            # If it fails, keep default but continue
                            pass
                        self._log_message(f"Reconexão bem-sucedida (tentativa {attempt})", "DEBUG")
                        return True
                    else:
                        self.connected = False
                        # Keep logs as DEBUG to avoid noise during transient issues
                        self._log_message(f"Falha ao reconectar (tentativa {attempt}): {reason}", "DEBUG")
                        time.sleep(1)
                except Exception as e:
                    # Keep it quiet unless last attempt
                    if attempt == self.max_reconnect_attempts:
                        self._log_message(f"Erro na reconexão: {str(e)}", "DEBUG")
                    time.sleep(1)
        except Exception:
            pass
        return False
    
    def change_account(self, account_type: str) -> Tuple[bool, str]:
        """Change account type (PRACTICE or REAL)"""
        if not self.connected:
            return False, "Não conectado à IQ Option"
        
        try:
            with self._api_lock:
                self.api.change_balance(account_type)
            self.account_type = account_type
            balance = self.get_balance()
            
            msg = f"Conta {account_type} selecionada. Saldo: ${balance}"
            self._log_message(msg, "INFO")
            return True, msg
            
        except Exception as e:
            error_msg = f"Erro ao trocar conta: {str(e)}"
            self._log_message(error_msg, "ERROR")
            return False, error_msg
    
    def get_balance(self) -> float:
        """Get current account balance"""
        if not self.connected or not self.api:
            return 0.0
        
        try:
            with self._api_lock:
                # Double check API is still valid before calling
                if not self.api:
                    self.connected = False
                    return 0.0
                return float(self.api.get_balance())
        except Exception as e:
            self._log_message(f"Erro ao obter saldo: {str(e)}", "ERROR")
            return 0.0
    
    def get_profile(self) -> Optional[Dict]:
        """Get user profile information"""
        if not self.connected or not self.api:
            return None
        
        try:
            with self._api_lock:
                # Double check API is still valid before calling
                if not self.api:
                    self.connected = False
                    return None
                return self.api.get_profile_ansyc()
        except Exception as e:
            self._log_message(f"Erro ao obter perfil: {str(e)}", "ERROR")
            return None

    def get_last_effective_option_type(self) -> Optional[str]:
        """Return the last effective option type ('digital' or 'binary') used when placing an order."""
        try:
            return self._last_effective_option_type
        except Exception:
            return None
    
    def ensure_active_mapping(self, asset: str) -> bool:
        """Ensure the IQC.ACTIVES mapping contains the given asset symbol.
        Attempts to update the mapping once using the underlying API. Returns True if present after update.
        """
        try:
            if asset in IQC.ACTIVES:
                return True
            if not self.connected or not self.api:
                return False
            with self._api_lock:
                try:
                    # Double check API is still valid before calling
                    if not self.api:
                        self.connected = False
                        return False
                    self.api.update_ACTIVES_OPCODE()
                except Exception:
                    pass
            return asset in IQC.ACTIVES
        except Exception:
            return False

    def get_candles(self, asset: str, timeframe: int, count: int = 100, attempts: int = 5) -> Optional[List[Dict]]:
        """Get candle data with retry mechanism and auto-reconnection"""
        if not self.connected or not self.api:
            return None
        
        # Skip clearly unsupported or option/composite symbols only
        # Allow standard forex pairs (including those starting with USD) and OTC variants
        if (
            '-op' in asset or
            '/' in asset or
            asset in ['IMXUSD-OTC', 'ATOMUSD-OTC', 'XNGUSD-OTC', 'Dollar_Index', 'Yen_Index']
        ):
            return None
        
        # Prepare timeframe and fallback control
        actual_timeframe = timeframe
        count_multiplier = 1
        # Minimum amount of candles we consider acceptable for the caller
        required_min = max(3, count)

        for attempt in range(attempts):
            try:
                # Use different timeframe approach: start with requested timeframe,
                # then fallback to M1 if M5 fails on first attempt
                # Prefer server timestamp when available and align to last closed candle
                server_ts = self.get_server_timestamp()
                end_ts = int(server_ts) - 2
                if actual_timeframe > 0:
                    end_ts = end_ts - (end_ts % actual_timeframe)
                # Ensure ACTIVES mapping contains the asset before requesting candles
                try:
                    if asset not in IQC.ACTIVES:
                        with self._api_lock:
                            # Double check API is still valid before calling
                            if not self.api:
                                self.connected = False
                                continue
                            self.api.update_ACTIVES_OPCODE()
                    if asset not in IQC.ACTIVES:
                        self._log_message(f"Ativo sem mapeamento ACTIVES: {asset} - pulando get_candles", "DEBUG")
                        return None
                except Exception:
                    pass
                with self._api_lock:
                    # Double check API is still valid before calling
                    if not self.api:
                        self.connected = False
                        return None
                    candles = self.api.get_candles(asset, actual_timeframe, count * count_multiplier, end_ts)
                
                # More robust validation (only require fields we actually use)
                if candles and isinstance(candles, list) and len(candles) >= required_min:
                    # Validate candle structure
                    valid_candles = []
                    for candle in candles:
                        if isinstance(candle, dict) and all(key in candle for key in ['open', 'close', 'from']):
                            valid_candles.append(candle)
                    
                    if len(valid_candles) >= required_min:
                        # Store candles in database
                        self._store_candles(asset, timeframe, valid_candles)
                        return valid_candles
                    else:
                        self._log_message(f"Tentativa {attempt + 1}: Velas insuficientes válidas para {asset} ({len(valid_candles)}/{required_min})", "DEBUG")
                else:
                    self._log_message(f"Tentativa {attempt + 1}: Dados de velas inválidos para {asset} (tipo: {type(candles)}, len: {len(candles) if candles else 0})", "DEBUG")
                    # If no data returned, try a quick reconnection for next attempt
                    if attempt < attempts - 1:
                        if self._attempt_reconnection():
                            time.sleep(2)
                    # Enable fallback from M5 to M1 for next attempts
                    if timeframe == 300 and actual_timeframe == 300:
                        actual_timeframe = 60
                        count_multiplier = 5
                    
            except Exception as e:
                error_msg = str(e).lower()
                if 'reconnect' in error_msg or 'socket' in error_msg or 'closed' in error_msg or 'failed' in error_msg:
                    # Silently handle reconnection errors - they're too noisy
                    if attempt == attempts - 1:  # Only log on final attempt
                        self._log_message(f"Conexão instável para {asset} - pulando", "DEBUG")
                    if self._attempt_reconnection():
                        time.sleep(2)
                        continue
                    else:
                        return None
                else:
                    self._log_message(f"Erro ao obter velas para {asset}: {str(e)}", "DEBUG")
                
            if attempt < attempts - 1:
                time.sleep(1)  # Reduced wait time
        
        # Don't log as ERROR - too noisy, use DEBUG
        return None
    
    def get_open_assets(self) -> List[str]:
        """Get list of currently open assets with fallback to hardcoded list"""
        if not self.connected or not self.api:
            return self._get_fallback_assets()
        
        try:
            # Wrap the API call in additional error handling
            try:
                with self._api_lock:
                    # Double check API is still valid before calling
                    if not self.api:
                        self.connected = False
                        return self._get_fallback_assets()
                    all_assets = self.api.get_all_open_time()
            except Exception as api_error:
                # Log only for debugging purposes, not as error since fallback works
                self._log_message(f"API temporariamente indisponível, usando ativos padrão", "INFO")
                return self._get_fallback_assets()
            
            # Verificar se retornou uma lista ao invés de dict (novo erro identificado)
            if isinstance(all_assets, list):
                self._log_message("Usando ativos padrão (formato de resposta alternativo)", "INFO")
                return self._get_fallback_assets()
            
            if not all_assets or not isinstance(all_assets, dict):
                self._log_message("Usando ativos padrão (dados não disponíveis)", "INFO")
                return self._get_fallback_assets()
            
            # Log da estrutura recebida para debug (apenas as chaves principais)
            try:
                main_keys = list(all_assets.keys()) if isinstance(all_assets, dict) else []
                self._log_message(f"Estrutura da API recebida com chaves: {main_keys}", "DEBUG")
            except Exception:
                pass
            
            assets = []
            
            # Tentar extrair ativos apenas de DIGITAL e BINARY (sem TURBO)
            for market_type in ['digital', 'binary']:
                try:
                    extracted = self._extract_assets_from_structure(all_assets, market_type)
                    if extracted:
                        assets.extend(extracted)
                        self._log_message(f"Extraídos {len(extracted)} ativos de {market_type}", "DEBUG")
                except Exception as e:
                    self._log_message(f"Erro ao extrair ativos {market_type}: {str(e)}", "DEBUG")
                    continue
            
            # Remover duplicatas mantendo ordem
            unique_assets = []
            for asset in assets:
                if asset and isinstance(asset, str) and asset not in unique_assets:
                    unique_assets.append(asset)
            
            if unique_assets:
                self._log_message(f"Encontrados {len(unique_assets)} ativos disponíveis via API", "INFO")
                return unique_assets
            else:
                self._log_message("Usando ativos padrão (nenhum ativo encontrado)", "INFO")
                return self._get_fallback_assets()
            
        except Exception as e:
            error_msg = str(e).lower()
            # Log stack trace for debugging
            stack_trace = traceback.format_exc()
            self._log_message(f"Stack trace completo: {stack_trace}", "DEBUG")
            
            if 'socket' in error_msg or 'closed' in error_msg:
                self._log_message(f"Erro de conexão ao obter ativos: {str(e)}", "ERROR")
                if self._attempt_reconnection():
                    return self.get_open_assets()  # Retry after reconnection
            else:
                self._log_message(f"Erro geral ao obter ativos abertos: {str(e)}", "ERROR")
            return self._get_fallback_assets()
    
    def _extract_assets_from_structure(self, all_assets: dict, market_type: str) -> List[str]:
        """Extract assets from a specific market type structure with bulletproof error handling"""
        assets = []
        
        if not isinstance(all_assets, dict):
            return assets
        
        try:
            # Verificar se o market_type existe na estrutura
            if market_type not in all_assets:
                return assets
            
            market_data = all_assets[market_type]
            
            # Verificar se market_data é um dict válido
            if not isinstance(market_data, dict):
                return assets
            
            # Log da estrutura para debug
            try:
                market_keys = list(market_data.keys()) if isinstance(market_data, dict) else []
                self._log_message(f"Chaves encontradas em {market_type}: {market_keys}", "DEBUG")
            except Exception:
                pass
            
            # Helper: detect standard FX pairs and -OTC variants from key names
            allowed_ccy = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "XAU", "XAG"}
            def _is_fx(sym: str) -> bool:
                return isinstance(sym, str) and sym.isalpha() and len(sym) == 6 and sym[:3].upper() in allowed_ccy and sym[3:].upper() in allowed_ccy
            def _is_fx_otc(sym: str) -> bool:
                return isinstance(sym, str) and sym.endswith('-OTC') and _is_fx(sym[:-4])

            # Método 1: Estrutura direta - verificar chaves no nível raiz (exceto 'underlying')
            try:
                for key in list(market_data.keys()):  # Criar lista para evitar modificação durante iteração
                    if not isinstance(key, str) or key == 'underlying':
                        continue
                    
                    # Priorizar coleta por padrão de nome (FX e OTC)
                    if _is_fx(key) or _is_fx_otc(key):
                        assets.append(key)
                        continue
                    
                    # Fallback para validação robusta
                    try:
                        value = market_data[key]
                        if self._is_valid_asset(key, value):
                            assets.append(key)
                    except (KeyError, TypeError, AttributeError) as e:
                        self._log_message(f"Erro ao acessar {key} em {market_type}: {str(e)}", "DEBUG")
                        continue
                        
            except Exception as e:
                self._log_message(f"Erro no método 1 para {market_type}: {str(e)}", "DEBUG")
            
            # Método 2: Estrutura com 'underlying' - verificar se existe e é dict
            try:
                if 'underlying' in market_data and isinstance(market_data['underlying'], dict):
                    underlying_data = market_data['underlying']
                    
                    for key in list(underlying_data.keys()):
                        if not isinstance(key, str):
                            continue
                        
                        # Priorizar coleta por padrão de nome (FX e OTC)
                        if _is_fx(key) or _is_fx_otc(key):
                            assets.append(key)
                            continue
                        
                        try:
                            value = underlying_data[key]
                            if self._is_valid_asset(key, value):
                                assets.append(key)
                        except (KeyError, TypeError, AttributeError) as e:
                            self._log_message(f"Erro ao acessar underlying.{key} em {market_type}: {str(e)}", "DEBUG")
                            continue
                            
            except Exception as e:
                self._log_message(f"Erro no método 2 para {market_type}: {str(e)}", "DEBUG")
            
            # Método 3: Estrutura aninhada - verificar outros níveis (evitando 'underlying')
            try:
                for key in list(market_data.keys()):
                    if not isinstance(key, str) or key == 'underlying':
                        continue
                    
                    try:
                        value = market_data[key]
                        if isinstance(value, dict):
                            for sub_key in list(value.keys()):
                                if not isinstance(sub_key, str):
                                    continue
                                
                                try:
                                    sub_value = value[sub_key]
                                    if self._is_valid_asset(sub_key, sub_value):
                                        assets.append(sub_key)
                                except (KeyError, TypeError, AttributeError) as e:
                                    self._log_message(f"Erro ao acessar {key}.{sub_key} em {market_type}: {str(e)}", "DEBUG")
                                    continue
                                    
                    except (KeyError, TypeError, AttributeError) as e:
                        self._log_message(f"Erro ao acessar subnível {key} em {market_type}: {str(e)}", "DEBUG")
                        continue
                        
            except Exception as e:
                self._log_message(f"Erro geral ao extrair ativos de {market_type}: {str(e)}", "DEBUG")
                            
        except Exception as e:
            self._log_message(f"Erro geral ao extrair ativos de {market_type}: {str(e)}", "DEBUG")
        
        # Remover duplicatas locais
        unique_assets = []
        for asset in assets:
            if asset and isinstance(asset, str) and asset not in unique_assets:
                unique_assets.append(asset)
        
        return unique_assets
    
    def _is_valid_asset(self, key: str, value) -> bool:
        """Check if a key-value pair represents a valid open asset with bulletproof validation"""
        try:
            # Verificar se a chave é uma string válida (nome do ativo)
            if not isinstance(key, str) or len(key) < 3:
                return False
            
            # Filtrar chaves que não são nomes de ativos
            invalid_keys = ['underlying', 'open', 'close', 'enabled', 'disabled', 'status', 'config', 'settings']
            if key.lower() in invalid_keys:
                return False
            
            # Verificar se o valor é None ou vazio
            if value is None:
                return False
            
            # Verificar se o valor é um dicionário com status 'open'
            if isinstance(value, dict):
                # Tentar diferentes chaves que podem indicar se o ativo está aberto
                open_indicators = ['open', 'enabled', 'active', 'available']
                for indicator in open_indicators:
                    try:
                        if indicator in value:
                            status = value[indicator]
                            if isinstance(status, bool):
                                return status
                            elif isinstance(status, (int, str)):
                                return str(status).lower() in ['true', '1', 'yes', 'open', 'enabled', 'active']
                    except (KeyError, TypeError, AttributeError):
                        continue
                
                # Se não encontrou indicadores específicos, assumir que é válido se é um dict não vazio
                return len(value) > 0
            
            # Verificar se o valor é um booleano True (formato simplificado)
            if isinstance(value, bool):
                return value
            
            # Verificar se o valor é um número (pode indicar payout ou status)
            if isinstance(value, (int, float)):
                return value > 0
            
            # Verificar se o valor é uma string indicando status
            if isinstance(value, str):
                return value.lower() in ['true', '1', 'yes', 'open', 'enabled', 'active']
                
            return False
            
        except Exception as e:
            # Log do erro para debug mas não falhar
            try:
                logger.debug(f"Erro na validação do ativo {key}: {str(e)}")
            except:
                pass
            return False
    
    def _get_fallback_assets(self) -> List[str]:
        """Return a hardcoded list of common trading assets as fallback"""
        fallback_assets = [
            'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD',
            'EURJPY', 'EURGBP', 'EURAUD', 'GBPJPY', 'AUDJPY', 'CADJPY', 'CHFJPY',
            'GOLD', 'SILVER', 'OIL', 'BTCUSD', 'ETHUSD'
        ]
        # Downgrade to DEBUG to avoid noisy logs when not connected
        self._log_message(f"Usando {len(fallback_assets)} ativos padrão como fallback", "DEBUG")
        return fallback_assets
    
    def get_best_available_asset(self, preferred_assets: List[str] = None) -> Optional[str]:
        """Get the best available asset for trading"""
        if preferred_assets is None:
            preferred_assets = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD']
        
        open_assets = self.get_open_assets()
        
        # Filter to standard FX pairs and their -OTC variants (Binary/Digital scope)
        allowed_ccy = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "XAU", "XAG"}
        def _is_standard_fx(sym: str) -> bool:
            return isinstance(sym, str) and sym.isalpha() and len(sym) == 6 and sym[:3] in allowed_ccy and sym[3:] in allowed_ccy
        def _is_standard_fx_otc(sym: str) -> bool:
            return isinstance(sym, str) and sym.endswith('-OTC') and _is_standard_fx(sym[:-4])
        allowed_assets = [a for a in open_assets if _is_standard_fx(a) or _is_standard_fx_otc(a)]
        
        if not open_assets:
            self._log_message("Nenhum ativo disponível no momento", "WARNING")
            return None
        
        # Try to find a preferred asset that is open
        for preferred in preferred_assets:
            if preferred in allowed_assets:
                payout = self.get_payout(preferred)
                total_payout = (payout['binary'] or 0) + (payout['digital'] or 0)
                if total_payout > 0:
                    self._log_message(f"Ativo selecionado: {preferred} (Payouts: Binary: {payout['binary']}%, Digital: {payout['digital']}%)", "INFO")
                    return preferred
        
        # If no preferred asset is available, take the first one with payout > 0
        for asset in allowed_assets:
            payout = self.get_payout(asset)
            total_payout = (payout['binary'] or 0) + (payout['digital'] or 0)
            if total_payout > 0:
                self._log_message(f"Ativo alternativo selecionado: {asset} (Payouts: Binary: {payout['binary']}%, Digital: {payout['digital']}%)", "INFO")
                return asset
        
        # Silenciar warning recorrente - usar apenas DEBUG
        self._log_message(f"Ativos disponíveis sem payout: {', '.join(allowed_assets[:5])}", "DEBUG")
        return allowed_assets[0] if allowed_assets else None
    
    def is_market_open(self, asset: str = None) -> bool:
        """Check if markets are generally open based on time"""
        now_utc = datetime.now(timezone.utc)
        
        # Convert to different market timezones
        ny_time = now_utc - timedelta(hours=5)  # EST/EDT
        london_time = now_utc + timedelta(hours=0)  # GMT/BST
        tokyo_time = now_utc + timedelta(hours=9)  # JST
        
        # Check if it's weekend
        if now_utc.weekday() >= 5:  # Saturday = 5, Sunday = 6
            # Weekend - only crypto might be available
            if asset and any(crypto in asset.upper() for crypto in ['BTC', 'ETH', 'LTC', 'XRP']):
                return True
            return False
        
        # Forex markets (most common)
        if not asset or any(pair in asset.upper() for pair in ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF']):
            # Forex is open 24/5, closed from Friday 5PM EST to Sunday 5PM EST
            if now_utc.weekday() == 4 and ny_time.hour >= 17:  # Friday after 5PM EST
                return False
            if now_utc.weekday() == 6 and ny_time.hour < 17:  # Sunday before 5PM EST
                return False
            return True
        
        # Stock markets
        if asset and any(stock in asset.upper() for stock in ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN']):
            # US market hours: 9:30 AM - 4:00 PM EST
            if 9.5 <= ny_time.hour + ny_time.minute/60 <= 16:
                return True
            return False
        
        # Commodities (Gold, Oil, etc.)
        if asset and any(commodity in asset.upper() for commodity in ['GOLD', 'OIL', 'SILVER']):
            # Generally follow forex hours
            return True
        
        # Default: assume market might be open
        return True
    
    def get_market_status_info(self) -> Dict[str, str]:
        """Get detailed market status information"""
        now_utc = datetime.now(timezone.utc)
        ny_time = now_utc - timedelta(hours=5)
        london_time = now_utc + timedelta(hours=0)
        tokyo_time = now_utc + timedelta(hours=9)
        
        status = {
            'current_utc': now_utc.strftime('%Y-%m-%d %H:%M:%S UTC'),
            'new_york': ny_time.strftime('%H:%M EST'),
            'london': london_time.strftime('%H:%M GMT'),
            'tokyo': tokyo_time.strftime('%H:%M JST'),
            'is_weekend': now_utc.weekday() >= 5,
            'forex_open': self.is_market_open('EURUSD'),
            'us_stocks_open': self.is_market_open('AAPL'),
        }
        
        return status
    
    def get_payout(self, asset: str, force_refresh: bool = False) -> Dict[str, float]:
        """Get payout information for an asset
        
        Args:
            asset: Asset symbol to get payout for
            force_refresh: If True, bypass cache and fetch fresh data
        """
        if not self.connected or not self.api:
            return {'binary': 0, 'turbo': 0, 'digital': 0}
        
        # Check cache first unless force_refresh is requested
        if not force_refresh:
            cached = self.get_payout_cached(asset, ttl=60)  # Reduced TTL to 60 seconds
            if cached:
                self._log_message(f"[PAYOUT-CACHE] Usando cache para {asset}: Binary={cached['binary']}%, Digital={cached['digital']}%", "DEBUG")
                return cached
        
        try:
            with self._api_lock:
                # Double check API is still valid before calling
                if not self.api:
                    self.connected = False
                    return {'binary': 0, 'turbo': 0, 'digital': 0}
                try:
                    self._log_message(f"[PAYOUT-FETCH] Buscando dados frescos para {asset}{'(FORCE)' if force_refresh else ''}", "DEBUG")
                    profit = self.api.get_all_profit()
                    all_assets = self.api.get_all_open_time()
                except Exception as vend_e:
                    # Vendor can raise transient errors during init (e.g., get_all_init_v2 late ...)
                    # Return safe fallback to avoid breaking strategies
                    self._log_message(
                        f"Falha vendor ao obter profit/open_time para {asset}: {str(vend_e)} — aplicando fallback padrão (80/80)",
                        "WARNING"
                    )
                    return {'binary': 80, 'turbo': 0, 'digital': 80}
            
            result = {'binary': 0, 'turbo': 0, 'digital': 0}
            
            # Verificar se os dados estão disponíveis
            if not profit:
                self._log_message(f"Dados de profit não disponíveis para {asset}", "WARNING")
                return result
            # Tratar open_time como opcional (pode estar indisponível/transiente)
            if not all_assets or not isinstance(all_assets, dict):
                all_assets = {}
            
            # Prepare candidate asset keys for profit lookup
            candidates = []
            try:
                base = str(asset).upper()
                candidates = [base]
                if base.endswith('-OTC'):
                    candidates.append(base.replace('-OTC', ''))
                if base.endswith('-OP'):
                    candidates.append(base.replace('-OP', ''))
                # Some APIs might also use names without suffixes generally
                if '/' in base:
                    candidates.append(base.split('/')[0])
            except Exception:
                candidates = [asset]

            # Map candidate symbols to active IDs (handles profit keyed by IDs)
            candidate_ids = []
            try:
                # Ensure ACTIVES mapping is up to date
                for sym in list(dict.fromkeys(candidates)):
                    act_id = IQC.ACTIVES.get(sym)
                    if act_id is None:
                        try:
                            with self._api_lock:
                                # Double check API is still valid before calling
                                if not self.api:
                                    self.connected = False
                                    continue
                                self.api.update_ACTIVES_OPCODE()
                            act_id = IQC.ACTIVES.get(sym)
                        except Exception:
                            pass
                    try:
                        if act_id is not None:
                            candidate_ids.append(int(act_id))
                    except Exception:
                        # If cannot cast to int, ignore
                        pass
            except Exception:
                candidate_ids = []

            # Binary payout
            try:
                asset_data = None
                profit_data = None
                
                # Tentar acessar dados binários com verificações robustas
                if isinstance(all_assets, dict) and 'binary' in all_assets:
                    binary_data = all_assets['binary']
                    if isinstance(binary_data, dict):
                        # Método 1: Acesso direto
                        for cand in candidates:
                            if cand in binary_data:
                                asset_data = binary_data[cand]
                                break
                        # Método 1b: Acesso por active_id quando chaves são inteiras
                        if asset_data is None and candidate_ids:
                            for act_id in candidate_ids:
                                if act_id in binary_data:
                                    asset_data = binary_data[act_id]
                                    break
                        # Método 2: Acesso via 'underlying' com verificação segura
                        if 'underlying' in binary_data:
                            try:
                                underlying = binary_data['underlying']
                                # Verificar se underlying é dict e não lista
                                if isinstance(underlying, dict):
                                    for cand in candidates:
                                        if cand in underlying:
                                            asset_data = underlying[cand]
                                            break
                                    # IDs dentro de underlying
                                    if asset_data is None and candidate_ids:
                                        for act_id in candidate_ids:
                                            if act_id in underlying:
                                                asset_data = underlying[act_id]
                                                break
                                elif isinstance(underlying, list):
                                    # Se for lista, procurar pelo asset
                                    for item in underlying:
                                        if isinstance(item, dict) and item.get('active_id') in candidates:
                                            asset_data = item
                                            break
                            except (KeyError, TypeError, AttributeError, Exception):
                                pass
                
                # Tentar acessar dados de profit com verificações robustas
                if isinstance(profit, dict):
                    for cand in candidates:
                        try:
                            if cand in profit:
                                asset_profit = profit[cand]
                                if isinstance(asset_profit, dict) and 'binary' in asset_profit:
                                    profit_data = asset_profit['binary']
                                    if profit_data:
                                        break
                        except (KeyError, TypeError, AttributeError):
                            continue
                
                    # Tentar via active_id quando as chaves são inteiras
                    if not profit_data and candidate_ids:
                        for act_id in candidate_ids:
                            try:
                                if act_id in profit:
                                    asset_profit = profit[act_id]
                                    if isinstance(asset_profit, dict) and 'binary' in asset_profit:
                                        profit_data = asset_profit['binary']
                                    elif isinstance(asset_profit, (int, float)):
                                        profit_data = asset_profit
                                    if profit_data:
                                        break
                            except (KeyError, TypeError, AttributeError):
                                continue
                elif isinstance(profit, list):
                    # Se profit for lista, procurar pelo asset
                    try:
                        for item in profit:
                            if isinstance(item, dict) and item.get('active_id') in candidates:
                                if 'binary' in item:
                                    profit_data = item['binary']
                                break
                    except (KeyError, TypeError, AttributeError):
                        pass
                
                # Determine openness more flexibly
                is_open = None
                if isinstance(asset_data, dict):
                    if 'open' in asset_data:
                        is_open = bool(asset_data.get('open'))
                    elif 'enabled' in asset_data:
                        is_open = bool(asset_data.get('enabled'))
                    elif 'active' in asset_data:
                        is_open = bool(asset_data.get('active'))

                if (profit_data and isinstance(profit_data, (int, float)) and profit_data > 0):
                    # Honor profit value regardless of open_time flag (market detection can be unreliable)
                    result['binary'] = round(profit_data * 100, 2)
                    self._log_message(f"[PAYOUT-BINARY] {asset}: {result['binary']}% (raw: {profit_data}, open_time={is_open})", "DEBUG")
                    if is_open is False:
                        self._log_message(
                            f"[PAYOUT-NOTE] open_time indica fechado para {asset}, mas lucro está disponível. Usando payout mesmo assim.",
                            "DEBUG"
                        )
                    
            except Exception as e:
                self._log_message(f"Erro ao obter payout binary para {asset}: {str(e)}", "DEBUG")
            
            # TURBO desativado: manter payout turbo em 0
            try:
                result['turbo'] = 0
            except Exception:
                pass
            
            # Digital payout
            try:
                digital_payout_val = None
                # Nem todas as versões da API possuem get_digital_payout
                if hasattr(self.api, 'get_digital_payout') and callable(getattr(self.api, 'get_digital_payout', None)):
                    with self._api_lock:
                        digital_payout_val = self.api.get_digital_payout(asset)
                # Se o método não existir ou não retornar valor válido, usar heurística baseada no binary
                if isinstance(digital_payout_val, (int, float)) and digital_payout_val > 0:
                    result['digital'] = round(digital_payout_val, 2)
                    self._log_message(f"[PAYOUT-DIGITAL] {asset}: {result['digital']}% (método direto)", "DEBUG")
                else:
                    heuristic = result['binary']
                    if heuristic > 0:
                        result['digital'] = heuristic
                        self._log_message(f"[PAYOUT-DIGITAL] {asset}: {result['digital']}% (heurística baseada em binary)", "DEBUG")

                # FAST-PATH: Tentar via quotes digitais SPT (pré-aquecimento curto) SEMPRE que possível
                # Mesmo quando já temos heurística baseada no binary, se as quotes trouxerem um valor plausível,
                # fazemos override para refletir o payout da plataforma (ex.: 85%).
                try:
                    # Pré-aquecer rapidamente a lista de strikes digitais para 1 minuto
                    try:
                        self.subscribe_strike_list(asset, int(expiration))
                    except Exception:
                        pass
                    start_q = time.time()
                    val = None
                    # Janela curta para não bloquear (até ~0.7s)
                    while time.time() - start_q < 0.7:
                        try:
                            if hasattr(self.api, 'get_digital_current_profit') and callable(getattr(self.api, 'get_digital_current_profit', None)):
                                v = self.api.get_digital_current_profit(asset, int(expiration))
                                if isinstance(v, (int, float)) and v:
                                    val = float(v)
                                    break
                        except Exception:
                            pass
                        time.sleep(0.05)
                    if val is not None:
                        # Normalizar valor retornado (algumas variantes retornam fração 0-1, outras percentuais)
                        pct = val
                        if pct <= 1.5:
                            pct = pct * 100.0
                        # Sanitizar para faixa plausível
                        if 40.0 <= pct <= 100.0:
                            prev = float(result.get('digital', 0) or 0)
                            new_pct = round(pct, 2)
                            # Override se quotes trouxerem valor maior ou se ainda estava 0
                            if new_pct != prev and (prev <= 0 or new_pct > prev - 0.1):
                                result['digital'] = new_pct
                                self._log_message(f"[PAYOUT-DIGITAL-OVERRIDE] {asset}: {result['digital']}% (via quotes SPT)", "DEBUG")
                except Exception:
                    pass
            except Exception as payout_e:
                # Manter silêncio em DEBUG para evitar ruído
                self._log_message(f"Payout digital não disponível para {asset} (usando heurística). Detalhe: {str(payout_e)}", "DEBUG")
            
            # Se nenhum payout foi determinado, usar fallback padrão para evitar zeros silenciosos
            if result['binary'] == 0 and result['digital'] == 0:
                self._log_message(f"Payouts indisponíveis para {asset}, aplicando fallback padrão (binary/digital=80%)", "DEBUG")
                fb = {'binary': 80, 'turbo': 0, 'digital': 80}
                try:
                    self._payout_cache[str(asset).upper()] = (dict(fb), time.time())
                except Exception:
                    pass
                return fb
            # Cachear resultado obtido
            try:
                cache_key = str(asset).upper()
                self._payout_cache[cache_key] = (dict(result), time.time())
                self._log_message(f"[PAYOUT-RESULT] {asset}: Binary={result['binary']}%, Digital={result['digital']}% (cached)", "INFO")
            except Exception:
                pass
            return result
            
        except Exception as e:
            # Silenciar erros conhecidos de 'underlying' e degradar 'NoneType' como transiente
            error_msg = str(e).lower()
            if 'underlying' in error_msg:
                # Quiet these to avoid noise
                pass
            elif 'nonetype' in error_msg:
                self._log_message(
                    f"Payout vendor transiente (NoneType) para {asset}. Aplicando fallback padrão (80/80). Detalhe: {str(e)}",
                    "WARNING"
                )
            else:
                self._log_message(f"Erro geral ao obter payout para {asset}: {str(e)}", "ERROR")
            return {'binary': 80, 'turbo': 0, 'digital': 80}  # Default payout, TURBO desativado
    
    def get_payout_cached(self, asset: str, ttl: int = 60) -> Optional[Dict[str, float]]:
        """Return cached payout if fresh, else None. Avoids heavy vendor calls in time-critical paths.
        
        Args:
            asset: Asset symbol
            ttl: Time-to-live in seconds (default: 60 seconds, reduced from 180)
        """
        try:
            key = str(asset).upper()
            cached = self._payout_cache.get(key)
            if cached and isinstance(cached, tuple) and len(cached) == 2:
                data, ts = cached
                age = time.time() - ts
                if isinstance(data, dict) and age <= ttl:
                    self._log_message(f"[PAYOUT-CACHE-HIT] {asset}: idade={age:.1f}s, TTL={ttl}s", "DEBUG")
                    return dict(data)
                else:
                    self._log_message(f"[PAYOUT-CACHE-MISS] {asset}: idade={age:.1f}s > TTL={ttl}s", "DEBUG")
        except Exception:
            pass
        return None
    
    def buy_option(self, asset: str, amount: float, direction: str, expiration: int, option_type: str = 'binary', urgent: bool = False) -> Tuple[bool, Optional[str]]:
        """Place a buy order"""
        if not self.connected or not self.api:
            return False, None
        
        try:
            # Normalize inputs
            option_type = (option_type or 'binary').lower().strip()
            direction = (direction or '').lower().strip()
            amount = round(float(amount), 2)

            # Ensure ACTIVES mapping exists for non-digital orders only
            if option_type != 'digital':
                try:
                    mapped = asset in IQC.ACTIVES
                    if not mapped and hasattr(self, 'ensure_active_mapping'):
                        mapped = self.ensure_active_mapping(asset)
                    if not mapped:
                        self._log_message(f"Ativo sem mapeamento ACTIVES para compra: {asset}", "WARNING")
                        return False, None
                except Exception:
                    pass

            # Quick openness check for digital to avoid vendor hangs — with FAST PATH at candle start
            fast_path = False
            try:
                if option_type == 'digital':
                    st_fp = float(self.get_server_timestamp())
                    sec_fp = st_fp % 60.0
                    # For 1m ops, widen the fast-path window to ~2.0s to tolerate small delays.
                    # When urgent=True (e.g., Gale), force fast-path regardless of current second.
                    if int(expiration) == 1:
                        if urgent:
                            fast_path = True
                        elif sec_fp <= 2.0:
                            fast_path = True
            except Exception:
                fast_path = False

            if option_type == 'digital' and not fast_path:
                try:
                    payouts = self.get_payout(asset)
                    if payouts.get('digital', 0) <= 0:
                        self._log_message(f"Digital sem payout para {asset} — impedindo compra", "WARNING")
                        return False, None
                    # open_time check desativado para DIGITAL (vendor é inconsistente). Confiar apenas em payout>0.
                except Exception:
                    pass
            elif option_type == 'digital' and fast_path:
                # Informative log to indicate we are prioritizing timing over pre-checks
                try:
                    self._log_message("FAST PATH digital 1m: pulando checagens pesadas para entrar no segundo 00", "DEBUG")
                except Exception:
                    pass

            self._log_message(
                f"Enviando ordem | ativo={asset} | tipo={option_type} | direcao={direction} | expiracao={expiration}m | valor=${amount} | server={datetime.utcfromtimestamp(float(self.get_server_timestamp())).strftime('%H:%M:%S')} (sec={int(float(self.get_server_timestamp()) % 60):02d})",
                "DEBUG"
            )

            # Worker to perform the blocking buy call
            result_holder = {'done': False, 'success': False, 'order_id': None, 'error': None}

            # Não atrasar envio digital M1 na virada — priorizar execução imediata
            # Mantemos apenas o FAST PATH já aplicado acima; nenhuma espera adicional aqui

            def _buy_worker():
                try:
                    # Evitar tentar fallback binary múltiplas vezes quando o ativo está suspenso
                    binary_suspended_local = False
                    if option_type == 'digital':
                        # Construir instrument_id e enviar via websocket sem bloquear indefinidamente
                        action = 'P' if direction == 'put' else 'C'
                        # Use wrapper to get server timestamp; IQ_Option doesn't expose .timesync directly
                        ts = int(self.get_server_timestamp())
                        # Evitar borda de minuto para 1m (ACK pode falhar quando muito próximo do flip)
                        if int(expiration) == 1:
                            try:
                                # Não aguardar 2s no início da vela; priorizar envio imediato no M1
                                # Apenas computa 'rem' se precisar para diagnósticos (sem sleep)
                                rem = (60 - (ts % 60)) % 60
                            except Exception:
                                pass
                        # Evitar chamada pesada de mapeamento no caminho crítico
                        try:
                            pass
                        except Exception:
                            pass
                        if int(expiration) == 1:
                            exp, _ = get_expiration_time(ts, 1)
                        else:
                            now_date = datetime.fromtimestamp(ts) + timedelta(minutes=1, seconds=30)
                            while True:
                                if now_date.minute % int(expiration) == 0 and time.mktime(now_date.timetuple()) - ts > 30:
                                    break
                                now_date = now_date + timedelta(minutes=1)
                            exp = time.mktime(now_date.timetuple())
                        date_formatted = datetime.utcfromtimestamp(exp).strftime("%Y%m%d%H%M")
                        instrument_id = f"do{asset}{date_formatted}PT{int(expiration)}M{action}SPT"
                        # Pré-aquecimento: assinar lista de strikes digitais para 1 minuto
                        try:
                            self.subscribe_strike_list(asset, int(expiration))
                        except Exception:
                            pass
                        # FAST PATH: não aguardar pré-aquecimento; enviar imediatamente no gate
                        quotes_ready = False
                        quotes_contains_id = False
                        if not fast_path:
                            try:
                                start_q = time.time()
                                # Janela curta para não bloquear (até ~0.7s)
                                while time.time() - start_q < 0.7:
                                    try:
                                        table = getattr(self.api.api, 'instrument_quites_generated_data', {})
                                        period = int(expiration) * 60
                                        data = None
                                        if isinstance(table, dict) and asset in table and period in table[asset]:
                                            data = table[asset][period]
                                        if data and isinstance(data, dict) and len(data) > 0:
                                            quotes_ready = True
                                            if instrument_id in data:
                                                quotes_contains_id = True
                                                break
                                    except Exception:
                                        pass
                                    time.sleep(0.05)
                            except Exception:
                                pass
                        try:
                            self._log_message(
                                f"Pré-aquecimento digital | quotes_ready={quotes_ready} | has_instrument_id={quotes_contains_id}",
                                "DEBUG"
                            )
                        except Exception:
                            pass
                        # Se o pré-aquecimento não encontrou o instrument_id esperado, tentar fallback imediato
                        # para garantir a entrada no minuto correto (evita ficar aguardando ACK digital que não virá)
                        if not quotes_contains_id:
                            # Caminho crítico: preferir cache (sem chamadas pesadas). Para ordens urgentes (ex.: Gale),
                            # permitir fallback sem cache, desde que ACTIVES esteja mapeado, para não perder o timing.
                            bin_payout = 0
                            try:
                                cached = self.get_payout_cached(asset, ttl=180)
                                if isinstance(cached, dict):
                                    bin_payout = int(cached.get('binary', 0) or 0)
                            except Exception:
                                bin_payout = 0
                            try:
                                fallback_allowed = False  # Do not attempt binary fallback from digital path; strategy handles Binary->Digital
                                if fallback_allowed:
                                    # Garantir mapeamento ACTIVES antes de tentar comprar em binary
                                    try:
                                        with self._api_lock:
                                            mapped = asset in IQC.ACTIVES
                                            if (not mapped) and hasattr(self, 'ensure_active_mapping'):
                                                mapped = self.ensure_active_mapping(asset)
                                    except Exception:
                                        mapped = False
                                    if not mapped:
                                        self._log_message(
                                            "Fallback binary-options abortado: ativo sem mapeamento ACTIVES",
                                            "WARNING"
                                        )
                                    else:
                                        if bin_payout <= 0 and urgent:
                                            self._log_message(
                                                "Fallback binary-options (urgente) sem payout em cache — tentando mesmo assim",
                                                "WARNING"
                                            )
                                        with self._api_lock:
                                            fb_ok, fb_id = self.api.buy(amount, asset, direction, int(expiration))
                                        if fb_ok:
                                            self._log_message(
                                                f"Fallback binary-options OK | order_id={fb_id} | server={self._format_server_time()}",
                                                "INFO"
                                            )
                                            # Register effective order type mapping for this order
                                            try:
                                                self._last_effective_option_type = 'binary'
                                                self._order_type_by_id[str(fb_id)] = 'binary'
                                            except Exception:
                                                pass
                                            result_holder['success'] = True
                                            result_holder['order_id'] = fb_id
                                            result_holder['effective_type'] = 'binary'
                                            result_holder['done'] = True
                                            return
                                        else:
                                            self._log_message(
                                                f"Fallback binary-options falhou | detalhe={fb_id}",
                                                "ERROR"
                                            )
                                            try:
                                                if isinstance(fb_id, str) and 'suspended' in fb_id.lower():
                                                    binary_suspended_local = True
                                                    self._log_message(
                                                        "Detecção: ativo binary suspenso — próximas tentativas de fallback serão puladas",
                                                        "INFO"
                                                    )
                                            except Exception:
                                                pass
                                else:
                                    self._log_message(
                                        "Fallback binary-options não tentado: binary fechado/suspenso ou sem payout em cache",
                                        "INFO"
                                    )
                            except Exception as fb_ex:
                                self._log_message(f"Erro no fallback binary-options: {str(fb_ex)}", "ERROR")
                            # Sem instrument_id e sem fallback viável -> não abortar; prosseguir com envio digital direto
                            try:
                                cond_no_binary = False  # Never abort here due to missing instrument_id
                            except Exception:
                                cond_no_binary = False
                            if cond_no_binary:
                                try:
                                    self._log_message(
                                        "Abortando envio digital: sem instrument_id e binary indisponível/suspenso",
                                        "WARNING"
                                    )
                                except Exception:
                                    pass
                                result_holder['success'] = False
                                result_holder['order_id'] = None
                                result_holder['done'] = True
                                return
                            # Se cond_no_binary for falso, prosseguimos para envio digital direto
                            
                            # Tentativa de envio digital mesmo sem instrument_id no cache de quotes
                            try:
                                self._log_message(
                                    f"Tentando envio digital direto | instrument_id={instrument_id}",
                                    "DEBUG"
                                )
                                with self._api_lock:
                                    # Use vendor API to build digital instrument internally and place order
                                    # Signature: buy_digital_spot(active, amount, action, duration)
                                    if hasattr(self.api, 'buy_digital_spot_v2') and callable(getattr(self.api, 'buy_digital_spot_v2', None)):
                                        try:
                                            self._log_message("Digital path: usando buy_digital_spot_v2", "DEBUG")
                                        except Exception:
                                            pass
                                        digital_ok, digital_id = self.api.buy_digital_spot_v2(asset, amount, direction, int(expiration))
                                    else:
                                        try:
                                            self._log_message("Digital path: usando buy_digital_spot (legacy)", "DEBUG")
                                        except Exception:
                                            pass
                                        # Legacy path
                                        digital_ok, digital_id = self.api.buy_digital_spot(asset, amount, direction, int(expiration))
                                
                                if digital_ok:
                                    self._log_message(
                                        f"Ordem digital OK | order_id={digital_id} | server={self._format_server_time()}",
                                        "INFO"
                                    )
                                    # Register effective order type mapping for this order
                                    try:
                                        self._last_effective_option_type = 'digital'
                                        self._order_type_by_id[str(digital_id)] = 'digital'
                                    except Exception:
                                        pass
                                    result_holder['success'] = True
                                    result_holder['order_id'] = digital_id
                                    result_holder['effective_type'] = 'digital'
                                    result_holder['done'] = True
                                    return
                                else:
                                    # Resilient fallback: if v2 failed (or returned None), try legacy method once
                                    try:
                                        can_try_legacy = hasattr(self.api, 'buy_digital_spot') and callable(getattr(self.api, 'buy_digital_spot', None))
                                        used_v2 = hasattr(self.api, 'buy_digital_spot_v2') and callable(getattr(self.api, 'buy_digital_spot_v2', None))
                                        if can_try_legacy and used_v2:
                                            try:
                                                self._log_message("Digital path fallback: tentando buy_digital_spot (legacy)", "WARNING")
                                            except Exception:
                                                pass
                                            with self._api_lock:
                                                legacy_ok, legacy_id = self.api.buy_digital_spot(asset, amount, direction, int(expiration))
                                            if legacy_ok:
                                                self._log_message(
                                                    f"Ordem digital (fallback legacy) OK | order_id={legacy_id} | server={self._format_server_time()}",
                                                    "INFO"
                                                )
                                                try:
                                                    self._last_effective_option_type = 'digital'
                                                    self._order_type_by_id[str(legacy_id)] = 'digital'
                                                except Exception:
                                                    pass
                                                result_holder['success'] = True
                                                result_holder['order_id'] = legacy_id
                                                result_holder['effective_type'] = 'digital'
                                                result_holder['done'] = True
                                                return
                                    except Exception:
                                        pass
                                    self._log_message(
                                        f"Ordem digital falhou | detalhe={digital_id}",
                                        "ERROR"
                                    )
                                    result_holder['success'] = False
                                    result_holder['order_id'] = digital_id
                                    result_holder['done'] = True
                                    return
                            except Exception as digital_ex:
                                self._log_message(f"Erro no envio digital: {str(digital_ex)}", "ERROR")
                                result_holder['success'] = False
                                result_holder['order_id'] = None
                                result_holder['done'] = True
                                return

                    else:
                        # Binary options path for non-digital orders
                        try:
                            with self._api_lock:
                                binary_ok, binary_id = self.api.buy(amount, asset, direction, int(expiration))
                            
                            if binary_ok:
                                self._log_message(
                                    f"Ordem binary OK | order_id={binary_id} | server={self._format_server_time()}",
                                    "INFO"
                                )
                                # Register effective order type mapping for this order
                                try:
                                    self._last_effective_option_type = 'binary'
                                    self._order_type_by_id[str(binary_id)] = 'binary'
                                except Exception:
                                    pass
                                result_holder['success'] = True
                                result_holder['order_id'] = binary_id
                                result_holder['effective_type'] = 'binary'
                                result_holder['done'] = True
                                return
                            else:
                                self._log_message(
                                    f"Ordem binary falhou | detalhe={binary_id}",
                                    "ERROR"
                                )
                                # Não fazer fallback DIGITAL aqui; a estratégia é responsável por Binary->Digital
                                self._log_message("Binary falhou - sem fallback interno; estratégia fará DIGITAL", "WARNING")
                                result_holder['success'] = False
                                result_holder['order_id'] = binary_id
                                result_holder['done'] = True
                                return
                        except Exception as binary_ex:
                            self._log_message(f"Erro no envio binary: {str(binary_ex)}", "ERROR")
                            result_holder['success'] = False
                            result_holder['order_id'] = None
                            result_holder['done'] = True
                            return

                except Exception as be:
                    result_holder['error'] = str(be)
                finally:
                    # Se não houve return antecipado, marcar done no final do worker
                    if not result_holder.get('done'):
                        result_holder['done'] = True

            if option_type == 'digital' and fast_path:
                # Executar inline para evitar timeouts artificiais de thread.join
                _buy_worker()
            else:
                t = threading.Thread(target=_buy_worker, daemon=True)
                t.start()
                # Timeout para outros tipos e também para digital quando não for FAST PATH
                timeout_secs = 12 if option_type == 'digital' else 6
                t.join(timeout_secs)

            if not result_holder['done']:
                self._log_message(
                    f"Timeout ao enviar ordem para {asset}/{option_type}{' após '+str(timeout_secs)+'s' if option_type!='digital' else ''}. Considerando falha.",
                    "ERROR"
                )
                # Fallback TURBO desativado por política
                self._log_message("Fallback para TURBO desativado. Retornando falha.", "WARNING")
                return False, None

            if result_holder['error'] is not None:
                self._log_message(f"Erro ao abrir ordem: {result_holder['error']}", "ERROR")
                return False, None

            success = result_holder['success']
            order_id = result_holder['order_id']

            # Log raw vendor response for diagnostics
            self._log_message(
                f"Retorno da compra | success={success} | order_id={order_id} | server={datetime.utcfromtimestamp(float(self.get_server_timestamp())).strftime('%H:%M:%S')} (sec={int(float(self.get_server_timestamp()) % 60):02d})",
                "DEBUG"
            )

            if success:
                # Persist effective type mapping for check_win(); default to requested option_type unless overridden by worker
                try:
                    eff_type = result_holder.get('effective_type') or option_type
                    eff_type = 'digital' if str(eff_type).lower().strip() == 'digital' else 'binary'
                    self._last_effective_option_type = eff_type
                    self._order_type_by_id[str(order_id)] = eff_type
                except Exception:
                    pass
                self._log_message(
                    f"Ordem aberta: {asset} {direction} ${amount} | server={datetime.utcfromtimestamp(float(self.get_server_timestamp())).strftime('%H:%M:%S')} (sec={int(float(self.get_server_timestamp()) % 60):02d})",
                    "INFO"
                )
                return True, str(order_id)
            else:
                try:
                    extra = f" | motivo: {order_id}" if order_id is not None else ""
                except Exception:
                    extra = ""
                self._log_message(f"Falha ao abrir ordem: {asset} {direction} ${amount}{extra}", "ERROR")
                return False, None

        except Exception as e:
            self._log_message(f"Erro ao abrir ordem: {str(e)}", "ERROR")
            return False, None

    def is_asset_open(self, asset: str, instrument_type: str) -> bool:
        """Check if a given asset is open for a specific instrument type (binary/turbo/digital)."""
        if not self.connected or not self.api:
            return True  # Assume open to avoid blocking when offline; strategies handle payout checks
        try:
            with self._api_lock:
                open_time = self.api.get_all_open_time()
            if not isinstance(open_time, dict):
                return True
            instrument_type = instrument_type.lower().strip()
            if instrument_type not in open_time:
                return True
            market_block = open_time[instrument_type]
            # market_block is a nested defaultdict; guard accesses
            try:
                entry = market_block.get(asset)
                if isinstance(entry, dict) and 'open' in entry:
                    return bool(entry['open'])
                # Some structures may have direct boolean
                if isinstance(entry, bool):
                    return entry
            except Exception:
                pass
            # Fallback: scan keys case-insensitively
            for k, v in getattr(market_block, 'items', lambda: [])():
                try:
                    if isinstance(k, str) and k.upper() == asset.upper():
                        if isinstance(v, dict) and 'open' in v:
                            return bool(v['open'])
                        if isinstance(v, bool):
                            return v
                except Exception:
                    continue
            return True
        except Exception as e:
            self._log_message(f"Erro ao verificar ativo aberto {asset}/{instrument_type}: {str(e)}", "DEBUG")
            return True
    
    def check_win(self, order_id: str, option_type: str = 'binary') -> Tuple[bool, Optional[float]]:
        """Check if an order won and return profit/loss"""
        if not self.connected or not self.api:
            return False, None
        
        try:
            # Use effective order type mapping when available to avoid mismatched checks
            effective_type = None
            try:
                effective_type = self._order_type_by_id.get(str(order_id))
            except Exception:
                effective_type = None
            chosen_type = (effective_type or option_type or 'binary').lower().strip()

            # Cast order_id to int when possible (vendor methods often expect int)
            vendor_order_id = order_id
            try:
                if isinstance(order_id, str) and order_id.isdigit():
                    vendor_order_id = int(order_id)
            except Exception:
                vendor_order_id = order_id

            with self._api_lock:
                if chosen_type == 'digital':
                    try:
                        status, result = self.api.check_win_digital_v2(vendor_order_id)
                    except Exception:
                        # Fallback to binary check if digital path fails
                        result = self.api.check_win_v3(vendor_order_id)
                        status = True
                else:
                    try:
                        result = self.api.check_win_v3(vendor_order_id)
                        status = True
                    except Exception:
                        # If binary path fails unexpectedly, make a best-effort digital check
                        status, result = self.api.check_win_digital_v2(vendor_order_id)

            
            if status and result is not None:
                return True, float(result)
            
            return False, None
            
        except Exception as e:
            self._log_message(f"Erro ao verificar resultado da ordem {order_id}: {str(e)}", "ERROR")
            return False, None
    
    def get_server_timestamp(self) -> float:
        """Get server timestamp"""
        if not self.connected or not self.api:
            return time.time()
        
        try:
            with self._api_lock:
                return self.api.get_server_timestamp()
        except Exception as e:
            self._log_message(f"Erro ao obter timestamp do servidor: {str(e)}", "WARNING")
            return time.time()
    
    def subscribe_strike_list(self, asset: str, expiration_period: int) -> None:
        """Wrapper to subscribe digital strike list (preheat) safely on the vendor API."""
        try:
            if not self.connected or not self.api:
                return
            with self._api_lock:
                # Preferred stable_api method
                if hasattr(self.api, 'subscribe_strike_list') and callable(getattr(self.api, 'subscribe_strike_list', None)):
                    self.api.subscribe_strike_list(asset, int(expiration_period))
                    return
                # Fallback to inner API method if exposed
                inner = getattr(self.api, 'api', None)
                if inner and hasattr(inner, 'subscribe_instrument_quites_generated') and callable(getattr(inner, 'subscribe_instrument_quites_generated', None)):
                    inner.subscribe_instrument_quites_generated(asset, int(expiration_period))
        except Exception:
            # Never break flow due to preheat issues
            pass
    
    def unsubscribe_strike_list(self, asset: str, expiration_period: int) -> None:
        """Wrapper to unsubscribe digital strike list on the vendor API (best-effort)."""
        try:
            if not self.connected or not self.api:
                return
            with self._api_lock:
                if hasattr(self.api, 'unsubscribe_strike_list') and callable(getattr(self.api, 'unsubscribe_strike_list', None)):
                    try:
                        self.api.unsubscribe_strike_list(asset, int(expiration_period))
                        return
                    except Exception:
                        pass
                inner = getattr(self.api, 'api', None)
                if inner and hasattr(inner, 'unsubscribe_instrument_quites_generated') and callable(getattr(inner, 'unsubscribe_instrument_quites_generated', None)):
                    try:
                        inner.unsubscribe_instrument_quites_generated(asset, int(expiration_period))
                    except Exception:
                        pass
        except Exception:
            pass
    
    def _format_server_time(self) -> str:
        """Return server time formatted for logs (HH:MM:SS with seconds-of-minute)."""
        try:
            st = float(self.get_server_timestamp())
            hhmmss = datetime.utcfromtimestamp(st).strftime('%H:%M:%S')
            sec = int(st % 60)
            return f"{hhmmss} (sec={sec:02d})"
        except Exception:
            try:
                return datetime.utcnow().strftime('%H:%M:%S') + " (sec=??)"
            except Exception:
                return "unknown"
    
    def _parse_connection_error(self, reason: str) -> str:
        """Parse connection error and return user-friendly message"""
        reason_str = str(reason).lower()
        
        if "invalid_credentials" in reason_str:
            return "Email ou senha incorretos"
        elif "blocked" in reason_str:
            return "Conta bloqueada pela IQ Option. Entre em contato com o suporte da IQ Option para resolver esta questão."
        elif "connection" in reason_str:
            return "Problema de conexão com a IQ Option"
        elif "suspended" in reason_str:
            return "Conta suspensa. Verifique seu status na plataforma IQ Option."
        else:
            return f"Erro na conexão: {reason}"
    
    def _store_candles(self, asset: str, timeframe: int, candles: List[Dict]):
        """Store candle data in database"""
        if not self.user:
            return

        try:
            for candle in candles[-10:]:  # Store only last 10 candles to avoid too much data
                attempts = 3
                for attempt in range(attempts):
                    try:
                        with transaction.atomic():
                            MarketData.objects.update_or_create(
                                asset=asset,
                                timeframe=timeframe,
                                timestamp=datetime.fromtimestamp(candle['from'], tz=timezone.utc),
                                defaults={
                                    'open_price': candle['open'],
                                    'high_price': candle.get('max', candle.get('high', candle['close'])),
                                    'low_price': candle.get('min', candle.get('low', candle['open'])),
                                    'close_price': candle['close'],
                                    'volume': candle.get('volume', 0)
                                }
                            )
                        break  # stored successfully; next candle
                    except Exception as e:
                        msg = str(e).lower()
                        if 'locked' in msg or 'database is locked' in msg:
                            if attempt < attempts - 1:
                                time.sleep(2)
                                continue
                        # On non-locked errors or after retries, log and skip to next candle
                        logger.error(f"Erro ao armazenar velas (tentativa {attempt+1}/{attempts}): {str(e)}")
                        break
        except Exception as e:
            logger.error(f"Erro ao armazenar velas (bloco externo): {str(e)}")
    
    # Duplicated methods removed. Canonical implementations of _safe_close, disconnect,
    # and _attempt_reconnection are defined earlier in this class.
    
    def _log_message(self, message: str, level: str = "INFO"):
        """Log message to database and console"""
        try:
            if self.user:
                TradingLog.objects.create(
                    user=self.user,
                    level=level,
                    message=f"[IQ API] {message}"
                )
            
            # Also log to console
            if level == "ERROR":
                logger.error(f"[IQ API] {message}")
            elif level == "WARNING":
                logger.warning(f"[IQ API] {message}")
            elif level == "DEBUG":
                logger.debug(f"[IQ API] {message}")
            else:
                logger.info(f"[IQ API] {message}")
                
        except Exception as e:
            logger.error(f"Erro ao registrar log: {str(e)}")


# Singleton instance manager
class IQOptionManager:
    """Manages IQ Option API instances for users"""
    
    _instances = {}
    
    @classmethod
    def get_instance(cls, user) -> Optional[IQOptionAPI]:
        """Get or create IQ Option API instance for user"""
        user_id = user.id
        
        if user_id in cls._instances:
            return cls._instances[user_id]
        
        # Get user credentials
        email, password = user.get_iq_credentials()
        if not email or not password:
            return None
        
        # Create new instance
        instance = IQOptionAPI(email, password, user)
        cls._instances[user_id] = instance
        
        return instance
    
    @classmethod
    def remove_instance(cls, user):
        """Remove and disconnect instance for user"""
        user_id = user.id
        
        if user_id in cls._instances:
            instance = cls._instances[user_id]
            instance.disconnect()
            del cls._instances[user_id]
    
    @classmethod
    def disconnect_all(cls):
        """Disconnect all instances"""
        for instance in cls._instances.values():
            instance.disconnect()
        cls._instances.clear()
