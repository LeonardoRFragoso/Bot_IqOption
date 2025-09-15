"""
Sistema de Filtros de Confirmação para Estratégias
Permite usar qualquer estratégia como principal e adicionar filtros de confirmação
para aumentar a precisão das operações.
"""

import logging
from typing import Optional, Dict, List, Any
from .strategies import get_strategy, STRATEGIES
from .models import TradingSession
from .iq_api import IQOptionAPI

logger = logging.getLogger(__name__)


class StrategyFilterSystem:
    """
    Sistema que combina uma estratégia principal com filtros de confirmação.
    """
    
    def __init__(self, api: IQOptionAPI, session: TradingSession):
        self.api = api
        self.session = session
        self.primary_strategy = None
        self.filter_strategies = {}
        
    def configure(self, config: Dict[str, Any]) -> bool:
        """
        Configura o sistema com uma estratégia principal e filtros de confirmação.
        
        Args:
            config: {
                'strategy': 'mhi',  # Estratégia principal
                'confirmation_filters': ['macd', 'rsi'],  # Filtros opcionais
                'confirmation_threshold': 0.6,  # Threshold de confirmação
                'filter_weights': {'macd': 0.6, 'rsi': 0.4}  # Pesos dos filtros
            }
        
        Returns:
            bool: True se configurado com sucesso
        """
        try:
            strategy_name = config.get('strategy')
            if not strategy_name:
                logger.error("Estratégia principal não especificada")
                return False
            
            # Configurar estratégia principal
            self.primary_strategy = get_strategy(strategy_name, self.api, self.session)
            if not self.primary_strategy:
                logger.error(f"Estratégia principal '{strategy_name}' não encontrada")
                return False
            
            # Configurar filtros de confirmação (opcionais)
            confirmation_filters = config.get('confirmation_filters', [])
            self.filter_strategies = {}
            
            for filter_name in confirmation_filters:
                if filter_name == strategy_name:
                    continue  # Não usar a mesma estratégia como filtro
                    
                filter_strategy = get_strategy(filter_name, self.api, self.session)
                if filter_strategy:
                    self.filter_strategies[filter_name] = filter_strategy
                else:
                    logger.warning(f"Filtro '{filter_name}' não encontrado, ignorando")
            
            # Configurações do sistema de filtros
            self.confirmation_threshold = config.get('confirmation_threshold', 0.6)
            self.filter_weights = config.get('filter_weights', {})
            self.enable_filters = len(self.filter_strategies) > 0
            
            logger.info(f"Sistema configurado - Principal: {strategy_name}, "
                       f"Filtros: {list(self.filter_strategies.keys())}, "
                       f"Threshold: {self.confirmation_threshold}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao configurar sistema de filtros: {e}")
            return False
    
    def analyze(self, asset: str, timeframe: int = 1) -> Dict[str, Any]:
        """
        Analisa um ativo usando a estratégia principal e filtros de confirmação.
        
        Args:
            asset: Nome do ativo
            timeframe: Timeframe em minutos
            
        Returns:
            Dict com resultado da análise
        """
        try:
            if not self.primary_strategy:
                return {
                    'signal': 'HOLD',
                    'confidence': 0,
                    'reason': 'Sistema não configurado'
                }
            
            # 1. Obter sinal da estratégia principal
            primary_result = self.primary_strategy.analyze(asset, timeframe)
            primary_signal = primary_result.get('signal', 'HOLD')
            
            # Se estratégia principal não sinaliza, não há operação
            if primary_signal == 'HOLD':
                return {
                    'signal': 'HOLD',
                    'confidence': 0,
                    'reason': f'Estratégia principal não sinalizou',
                    'primary_result': primary_result,
                    'filters_enabled': self.enable_filters
                }
            
            # 2. Se não há filtros habilitados, usar apenas estratégia principal
            if not self.enable_filters or not self.filter_strategies:
                return {
                    'signal': primary_signal,
                    'confidence': primary_result.get('confidence', 0.8),
                    'reason': f'Estratégia principal: {primary_signal.upper()}',
                    'primary_result': primary_result,
                    'filters_enabled': False
                }
            
            # 3. Consultar filtros de confirmação
            filter_results = {}
            confirmation_score = 0
            total_weight = 0
            
            for filter_name, filter_strategy in self.filter_strategies.items():
                try:
                    filter_result = filter_strategy.analyze(asset, timeframe)
                    filter_signal = filter_result.get('signal', 'HOLD')
                    filter_results[filter_name] = filter_result
                    
                    # Calcular peso do filtro
                    weight = self.filter_weights.get(filter_name, 1.0 / len(self.filter_strategies))
                    total_weight += weight
                    
                    # Calcular contribuição para score de confirmação
                    if filter_signal == primary_signal:
                        # Filtro confirma o sinal principal
                        confirmation_score += weight * 1.0
                    elif filter_signal == 'HOLD':
                        # Filtro neutro (não confirma nem conflita)
                        confirmation_score += weight * 0.0
                    else:
                        # Filtro conflita com sinal principal
                        confirmation_score += weight * -0.5
                        
                    logger.debug(f"Filtro {filter_name}: {filter_signal} (peso: {weight:.2f})")
                    
                except Exception as e:
                    logger.warning(f"Erro ao analisar filtro {filter_name}: {e}")
                    filter_results[filter_name] = {'signal': 'HOLD', 'error': str(e)}
            
            # 4. Normalizar score de confirmação (0.0 a 1.0)
            if total_weight > 0:
                normalized_score = max(0.0, confirmation_score / total_weight)
            else:
                normalized_score = 0.0
            
            # 5. Decidir sinal final baseado no threshold
            final_signal = primary_signal if normalized_score >= self.confirmation_threshold else 'HOLD'
            
            logger.info(f"Análise completa - Asset: {asset}, Principal: {primary_signal}, "
                       f"Score: {normalized_score:.3f}, Threshold: {self.confirmation_threshold}, "
                       f"Final: {final_signal}")
            
            return {
                'signal': final_signal,
                'confidence': normalized_score,
                'reason': f'Principal: {primary_signal}, Confirmação: {normalized_score:.2f}',
                'primary_result': primary_result,
                'filter_results': filter_results,
                'confirmation_score': normalized_score,
                'threshold': self.confirmation_threshold,
                'filters_enabled': True,
                'filters_used': list(self.filter_strategies.keys())
            }
            
        except Exception as e:
            logger.error(f"Erro na análise com filtros: {e}")
            return {
                'signal': 'HOLD',
                'confidence': 0,
                'reason': f'Erro na análise: {str(e)}',
                'filters_enabled': self.enable_filters
            }
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Retorna informações sobre a configuração atual do sistema"""
        if not self.primary_strategy:
            return {'configured': False}
            
        return {
            'configured': True,
            'primary_strategy': self.primary_strategy.__class__.__name__,
            'filters_enabled': self.enable_filters,
            'confirmation_filters': list(self.filter_strategies.keys()),
            'confirmation_threshold': self.confirmation_threshold,
            'filter_weights': self.filter_weights
        }


def create_strategy_with_filters(strategy_name: str, api: IQOptionAPI, session: TradingSession, 
                               filter_config: Optional[Dict[str, Any]] = None):
    """
    Factory function para criar uma estratégia com sistema de filtros.
    
    Args:
        strategy_name: Nome da estratégia principal
        api: Instância da API IQ Option
        session: Sessão de trading
        filter_config: Configuração dos filtros (opcional)
        
    Returns:
        StrategyFilterSystem configurado ou estratégia simples se não há filtros
    """
    # Se não há configuração de filtros, retornar estratégia simples
    if not filter_config or not filter_config.get('confirmation_filters'):
        return get_strategy(strategy_name, api, session)
    
    # Criar sistema com filtros
    filter_system = StrategyFilterSystem(api, session)
    
    config = {
        'strategy': strategy_name,
        'confirmation_filters': filter_config.get('confirmation_filters', []),
        'confirmation_threshold': filter_config.get('confirmation_threshold', 0.6),
        'filter_weights': filter_config.get('filter_weights', {})
    }
    
    if filter_system.configure(config):
        return filter_system
    else:
        # Se falhou ao configurar filtros, usar estratégia simples
        logger.warning(f"Falha ao configurar filtros, usando estratégia simples: {strategy_name}")
        return get_strategy(strategy_name, api, session)
