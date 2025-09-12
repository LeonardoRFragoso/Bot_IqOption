"""
Asset cataloging service
Analyzes assets and strategies to find the best performing combinations
"""

import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
from .iq_api import IQOptionAPI
from .models import AssetCatalog, TradingLog

logger = logging.getLogger(__name__)


class AssetCatalogService:
    """Service for cataloging and analyzing assets"""
    
    def __init__(self, api: IQOptionAPI, user):
        self.api = api
        self.user = user
        
    def catalog_assets(self, strategies: List[str]):
        """Catalog assets for given strategies"""
        self._log("Iniciando catalogacao de ativos", "INFO")
        
        # Get available assets and filter for reliable ones
        all_assets = self.api.get_open_assets()
        
        # Filter to focus on major forex pairs and reliable assets
        reliable_assets = []
        priority_assets = [
            'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD',
            'EURJPY', 'EURGBP', 'EURAUD', 'GBPJPY', 'AUDJPY', 'CADJPY', 'CHFJPY',
            'XAUUSD', 'BTCUSD', 'ETHUSD'
        ]
        
        # First add priority assets if available
        for asset in priority_assets:
            if asset in all_assets:
                reliable_assets.append(asset)
        
        # Add other non-OTC assets (limit to avoid API overload)
        for asset in all_assets:
            if (asset not in reliable_assets and 
                '-OTC' not in asset and 
                not asset.startswith('US') and
                '/' not in asset and
                len(reliable_assets) < 30):  # Limit total assets
                reliable_assets.append(asset)
        
        assets = reliable_assets
        self._log(f"Encontrados {len(assets)} ativos confiáveis para análise (de {len(all_assets)} disponíveis)", "INFO")
        
        results = []
        
        for strategy in strategies:
            total_assets = len(assets)
            
            for i, asset in enumerate(assets):
                progress = (i / total_assets) * 100
                self._log(f"Analisando {asset} com estratégia {strategy.upper()} ({progress:.1f}%)", "INFO")
                
                try:
                    analysis_result = self._analyze_asset_strategy(asset, strategy)
                    
                        if analysis_result and analysis_result.get('total_samples', 0) > 0:
                        # Save to database with retry mechanism for database locks
                        max_db_attempts = 3
                        db_attempt = 0
                        saved = False
                        
                        while db_attempt < max_db_attempts and not saved:
                            try:
                                from django.db import transaction
                                with transaction.atomic():
                                    catalog, created = AssetCatalog.objects.update_or_create(
                                        user=self.user,
                                        asset=asset,
                                        strategy=strategy,
                                        defaults={
                                            'win_rate': analysis_result['win_rate'],
                                            'gale1_rate': analysis_result['gale1_rate'],
                                            'gale2_rate': analysis_result['gale2_rate'],
                                            'gale3_rate': analysis_result['gale3_rate'],
                                            'total_samples': analysis_result['total_samples']
                                        }
                                    )
                                saved = True
                            except Exception as db_e:
                                db_attempt += 1
                                error_msg = str(db_e).lower()
                                if 'database is locked' in error_msg or 'locked' in error_msg:
                                    if db_attempt < max_db_attempts:
                                        time.sleep(2)  # Increased wait time
                                        continue
                                    else:
                                        # Skip this save if all retries failed
                                        self._log(f"AVISO: Falha ao salvar {asset}-{strategy} após {max_db_attempts} tentativas", "WARNING")
                                        saved = True  # Mark as saved to continue
                                        break
                                else:
                                    raise db_e
                        
                        results.append(analysis_result)
                        
                        self._log(f"OK {asset} - {strategy.upper()}: Win={analysis_result['win_rate']}%, Gale1={analysis_result['gale1_rate']}%, Gale2={analysis_result['gale2_rate']}%, Gale3={analysis_result['gale3_rate']}% ({analysis_result['total_samples']} amostras)", "INFO")
                    else:
                        self._log(f"AVISO: Nenhuma amostra valida para {asset} com {strategy}", "WARNING")
                except Exception as e:
                    self._log(f"ERRO: Falha na analise de {asset} com {strategy}: {str(e)}", "ERROR")
                
                # Small delay to avoid API rate limiting
                time.sleep(0.5)
        
        # Sort results by best win rate
        results.sort(key=lambda x: x['gale3_rate'], reverse=True)
        
        if results:
            best = results[0]
            self._log(f"Melhor resultado: {best['asset']} - {best['strategy'].upper()} - {best['gale3_rate']}%", "INFO")
        
        self._log("Catalogacao concluida", "INFO")
        return results
    
    def _analyze_asset_strategy(self, asset: str, strategy: str) -> Optional[Dict]:
        """Analyze specific asset with specific strategy"""
        timeframe = 60
        candles_count = 120
        
        if strategy == 'mhi_m5':
            candles_count = 146
            timeframe = 300
        
        # Get candles with retry logic
        attempts = 0
        max_attempts = 3
        candles = None
        
        while attempts < max_attempts and not candles:
            candles = self.api.get_candles(asset, timeframe, candles_count, int(time.time()))
            
            if not candles:
                attempts += 1
                if attempts < max_attempts:
                    self._log(f"AVISO: Tentativa {attempts}: falha ao obter velas de {asset}. Tentando novamente...", "WARNING")
                    time.sleep(2)
        
        if not candles:
            self._log(f"ERRO: Nao foi possivel obter dados de {asset} apos {max_attempts} tentativas", "ERROR")
            return None
        
        # Analyze candles based on strategy
        if strategy == 'mhi':
            return self._analyze_mhi_candles(candles, asset, strategy)
        elif strategy == 'torres_gemeas':
            return self._analyze_torres_candles(candles, asset, strategy)
        elif strategy == 'mhi_m5':
            return self._analyze_mhi_candles(candles, asset, strategy, timeframe=300)
        
        return None
    
    def _analyze_mhi_candles(self, candles: List[Dict], asset: str, strategy: str, timeframe: int = 60) -> Dict:
        """Analyze candles using MHI strategy logic"""
        results = {'doji': 0, 'win': 0, 'loss': 0, 'gale1': 0, 'gale2': 0, 'gale3': 0}
        
        for i in range(3, len(candles) - 3):
            # Check entry time based on timeframe
            if timeframe == 60:
                minutes = datetime.fromtimestamp(candles[i]['from'], tz=timezone.utc).minute
                entry_time = (minutes % 10) == 5 or (minutes % 10) == 0
            else:  # 300 seconds (5 minutes)
                minutes = datetime.fromtimestamp(candles[i]['from'], tz=timezone.utc).minute
                entry_time = minutes == 30 or minutes == 0
            
            if not entry_time:
                continue
            
            try:
                # Analyze 3 previous candles
                vela1 = 'Verde' if candles[i-3]['open'] < candles[i-3]['close'] else ('Vermelha' if candles[i-3]['open'] > candles[i-3]['close'] else 'Doji')
                vela2 = 'Verde' if candles[i-2]['open'] < candles[i-2]['close'] else ('Vermelha' if candles[i-2]['open'] > candles[i-2]['close'] else 'Doji')
                vela3 = 'Verde' if candles[i-1]['open'] < candles[i-1]['close'] else ('Vermelha' if candles[i-1]['open'] > candles[i-1]['close'] else 'Doji')
                
                colors = [vela1, vela2, vela3]
                
                # Skip if doji found
                if 'Doji' in colors:
                    results['doji'] += 1
                    continue
                
                # Determine direction
                green_count = colors.count('Verde')
                red_count = colors.count('Vermelha')
                
                if green_count > red_count:
                    direction = 'put'
                elif red_count > green_count:
                    direction = 'call'
                else:
                    continue
                
                # Check results in next 3 candles
                expected_color = 'Verde' if direction == 'call' else 'Vermelha'
                
                # Check entry candle
                entry_candle = 'Verde' if candles[i]['open'] < candles[i]['close'] else ('Vermelha' if candles[i]['open'] > candles[i]['close'] else 'Doji')
                
                if entry_candle == expected_color:
                    results['win'] += 1
                else:
                    # Check gale 1
                    if len(candles) > i + 1:
                        gale1_candle = 'Verde' if candles[i+1]['open'] < candles[i+1]['close'] else ('Vermelha' if candles[i+1]['open'] > candles[i+1]['close'] else 'Doji')
                        
                        if gale1_candle == expected_color:
                            results['gale1'] += 1
                        else:
                            # Check gale 2
                            if len(candles) > i + 2:
                                gale2_candle = 'Verde' if candles[i+2]['open'] < candles[i+2]['close'] else ('Vermelha' if candles[i+2]['open'] > candles[i+2]['close'] else 'Doji')
                                
                                if gale2_candle == expected_color:
                                    results['gale2'] += 1
                                else:
                                    # Check gale 3
                                    if len(candles) > i + 3:
                                        gale3_candle = 'Verde' if candles[i+3]['open'] < candles[i+3]['close'] else ('Vermelha' if candles[i+3]['open'] > candles[i+3]['close'] else 'Doji')
                                        
                                        if gale3_candle == expected_color:
                                            results['gale3'] += 1
                                        else:
                                            results['loss'] += 1
                                    else:
                                        results['loss'] += 1
                            else:
                                results['loss'] += 1
                    else:
                        results['loss'] += 1
                    
            except (KeyError, IndexError):
                continue
        
        return self._calculate_percentages(results, asset, strategy)
    
    def _analyze_torres_candles(self, candles: List[Dict], asset: str, strategy: str) -> Dict:
        """Analyze candles using Torres Gêmeas strategy logic"""
        results = {'doji': 0, 'win': 0, 'loss': 0, 'gale1': 0, 'gale2': 0, 'gale3': 0}
        
        for i in range(4, len(candles) - 3):
            # Check entry time (M4 and M9)
            minutes = datetime.fromtimestamp(candles[i]['from'], tz=timezone.utc).minute
            entry_time = (minutes % 10) == 4 or (minutes % 10) == 9
            
            if not entry_time:
                continue
            
            try:
                # Analyze 4th candle back
                vela4 = 'Verde' if candles[i-4]['open'] < candles[i-4]['close'] else ('Vermelha' if candles[i-4]['open'] > candles[i-4]['close'] else 'Doji')
                
                # Skip if doji found
                if vela4 == 'Doji':
                    results['doji'] += 1
                    continue
                
                # Direction is same as candle color
                direction = 'call' if vela4 == 'Verde' else 'put'
                expected_color = 'Verde' if direction == 'call' else 'Vermelha'
                
                # Check results in next 3 candles
                entry_candle = 'Verde' if candles[i]['open'] < candles[i]['close'] else ('Vermelha' if candles[i]['open'] > candles[i]['close'] else 'Doji')
                
                if entry_candle == expected_color:
                    results['win'] += 1
                else:
                    # Check gale 1
                    if len(candles) > i + 1:
                        gale1_candle = 'Verde' if candles[i+1]['open'] < candles[i+1]['close'] else ('Vermelha' if candles[i+1]['open'] > candles[i+1]['close'] else 'Doji')
                        
                        if gale1_candle == expected_color:
                            results['gale1'] += 1
                        else:
                            # Check gale 2
                            if len(candles) > i + 2:
                                gale2_candle = 'Verde' if candles[i+2]['open'] < candles[i+2]['close'] else ('Vermelha' if candles[i+2]['open'] > candles[i+2]['close'] else 'Doji')
                                
                                if gale2_candle == expected_color:
                                    results['gale2'] += 1
                                else:
                                    # Check gale 3
                                    if len(candles) > i + 3:
                                        gale3_candle = 'Verde' if candles[i+3]['open'] < candles[i+3]['close'] else ('Vermelha' if candles[i+3]['open'] > candles[i+3]['close'] else 'Doji')
                                        
                                        if gale3_candle == expected_color:
                                            results['gale3'] += 1
                                        else:
                                            results['loss'] += 1
                                    else:
                                        results['loss'] += 1
                            else:
                                results['loss'] += 1
                    else:
                        results['loss'] += 1
                    
            except (KeyError, IndexError):
                continue
        
        return self._calculate_percentages(results, asset, strategy)
    
    def _calculate_percentages(self, results: Dict, asset: str, strategy: str) -> Dict:
        """Calculate win percentages from results"""
        total_entries = results['win'] + results['loss'] + results['gale1'] + results['gale2'] + results['gale3']
        
        if total_entries == 0:
            return {
                'asset': asset,
                'strategy': strategy,
                'win_rate': 0,
                'gale1_rate': 0,
                'gale2_rate': 0,
                'gale3_rate': 0,
                'total_samples': 0
            }
        
        win_rate = round(results['win'] / total_entries * 100, 2)
        gale1_rate = round((results['win'] + results['gale1']) / total_entries * 100, 2)
        gale2_rate = round((results['win'] + results['gale1'] + results['gale2']) / total_entries * 100, 2)
        gale3_rate = round((results['win'] + results['gale1'] + results['gale2'] + results['gale3']) / total_entries * 100, 2)
        
        return {
            'asset': asset,
            'strategy': strategy,
            'win_rate': win_rate,
            'gale1_rate': gale1_rate,
            'gale2_rate': gale2_rate,
            'gale3_rate': gale3_rate,
            'total_samples': total_entries
        }
    
    def _log(self, message: str, level: str = "INFO"):
        """Log message to database with Unicode safety"""
        # Remove emojis and problematic Unicode characters
        clean_message = self._clean_unicode(message)
        
        TradingLog.objects.create(
            user=self.user,
            level=level,
            message=f"[CATALOG] {clean_message}"
        )
        logger.info(f"[CATALOG] {clean_message}")
    
    def _clean_unicode(self, text: str) -> str:
        """Remove emojis and problematic Unicode characters"""
        import re
        
        # Remove emojis and other problematic Unicode characters
        # This regex removes most emojis and symbols
        emoji_pattern = re.compile("["
                                   u"\U0001F600-\U0001F64F"  # emoticons
                                   u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                                   u"\U0001F680-\U0001F6FF"  # transport & map symbols
                                   u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                                   u"\U00002702-\U000027B0"
                                   u"\U000024C2-\U0001F251"
                                   "]+", flags=re.UNICODE)
        
        clean_text = emoji_pattern.sub('', text)
        
        # Ensure the text can be encoded in cp1252 (Windows default)
        try:
            clean_text.encode('cp1252')
            return clean_text
        except UnicodeEncodeError:
            # If still problematic, encode and decode to remove problematic chars
            return clean_text.encode('ascii', 'ignore').decode('ascii')
