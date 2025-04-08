# utils.py
from iqoptionapi.stable_api import IQ_Option
import time
from configobj import ConfigObj

def safe_get_candles(api, par, timeframe, count, end_time):
    config = ConfigObj('config.txt')
    email = config['LOGIN']['email']
    senha = config['LOGIN']['senha']
    attempts = 0
    max_attempts = 5
    candles = None

    while attempts < max_attempts and not candles:
        try:
            candles = api.get_candles(par, timeframe, count, end_time)
            if candles:
                return candles, api
        except Exception as e:
            print(f"⚠️ Erro get_candles: {e}")
            if "get_candles need reconnect" in str(e):
                try:
                    new_api = IQ_Option(email, senha)
                    if new_api.connect()[0]:
                        new_api.change_balance('PRACTICE')
                        api = new_api
                        print("🔄 Reconectado com sucesso.")
                except Exception as e2:
                    print(f"Erro crítico de reconexão: {e2}")
        attempts += 1
        time.sleep(2)
    return candles, api
