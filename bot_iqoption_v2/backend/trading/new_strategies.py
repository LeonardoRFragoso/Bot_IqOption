"""
New Strategies Integration
Integração das novas estratégias: RSI, Moving Average e Bollinger Bands
"""

from .rsi_strategy import RSIStrategy
from .moving_average_strategy import MovingAverageStrategy
from .bollinger_strategy import BollingerBandsStrategy
from .iq_api import IQOptionAPI
from .models import TradingSession
from typing import Optional

# Strategy factory for new strategies
NEW_STRATEGIES = {
    'rsi': RSIStrategy,
    'moving_average': MovingAverageStrategy,
    'bollinger_bands': BollingerBandsStrategy,
}


def get_new_strategy(strategy_name: str, api: IQOptionAPI, session: TradingSession) -> Optional[object]:
    """Get new strategy instance by name"""
    strategy_class = NEW_STRATEGIES.get(strategy_name.lower())
    if strategy_class:
        return strategy_class(api, session)
    return None


def get_all_available_strategies():
    """Get list of all available strategies (existing + new)"""
    from .strategies import STRATEGIES
    
    all_strategies = {}
    all_strategies.update(STRATEGIES)  # Existing strategies
    all_strategies.update(NEW_STRATEGIES)  # New strategies
    
    return all_strategies


def get_strategy_info():
    """Get information about all strategies"""
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
        }
    }


# Wrapper function to get any strategy (existing or new)
def get_any_strategy(strategy_name: str, api: IQOptionAPI, session: TradingSession) -> Optional[object]:
    """Get any strategy instance by name (existing or new)"""
    from .strategies import get_strategy
    
    # Try existing strategies first
    strategy = get_strategy(strategy_name, api, session)
    if strategy:
        return strategy
    
    # Try new strategies
    return get_new_strategy(strategy_name, api, session)
