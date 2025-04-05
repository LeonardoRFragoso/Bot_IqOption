from iqoptionapi.stable_api import IQ_Option
import time
from configobj import ConfigObj
from datetime import datetime
from tabulate import tabulate
import logging
from tqdm import tqdm

# ============================
# CONFIGURAÇÃO DE LOG AJUSTADA
# ============================
logger = logging.getLogger()
logger.setLevel(logging.ERROR)

class GetCandlesFilter(logging.Filter):
    def filter(self, record):
        return "get_candles need reconnect" not in record.getMessage()

logger.addFilter(GetCandlesFilter())
logging.getLogger("iqoptionapi").addFilter(GetCandlesFilter())

# ============================
# FUNÇÕES PRINCIPAIS
# ============================

def obter_pares_abertos(API):
    # Força apenas os pares desejados para análise
    pares_desejados = [
        'EURUSD-OTC',
        'EURGBP-OTC',
        'USDCHF-OTC',
        'GBPUSD-OTC',
        'GBPJPY-OTC'
    ]
    return pares_desejados

def analisar_velas(velas, tipo_estrategia):
    resultados = {'doji': 0, 'win': 0, 'loss': 0, 'gale1': 0, 'gale2': 0}
    for i in range(4, len(velas) - 3):  # Garante que temos pelo menos 3 velas futuras para análise
        minutos = int(datetime.fromtimestamp(velas[i]['from']).strftime('%M'))
        if tipo_estrategia == 'mhi' and (minutos % 5 == 0):
            analisar_mhi(velas, i, resultados)
        elif tipo_estrategia == 'torres' and (minutos % 5 == 4):
            analisar_torres(velas, i, resultados)
        elif tipo_estrategia == 'mhi_m5' and (minutos == 0 or minutos == 30):
            analisar_mhi(velas, i, resultados, timeframe=300)
    return resultados

def analisar_mhi(velas, i, resultados, timeframe=60):
    try:
        if i + 2 >= len(velas):
            return
        vela1 = 'Verde' if velas[i-3]['open'] < velas[i-3]['close'] else 'Vermelha'
        vela2 = 'Verde' if velas[i-2]['open'] < velas[i-2]['close'] else 'Vermelha'
        vela3 = 'Verde' if velas[i-1]['open'] < velas[i-1]['close'] else 'Vermelha'
        direcao = 'Verde' if [vela1, vela2, vela3].count('Verde') > 1 else 'Vermelha'
        entradas = [
            'Verde' if velas[i+j]['open'] < velas[i+j]['close'] else 'Vermelha'
            for j in range(3)
        ]
        resultados = atualizar_resultados(entradas, direcao, resultados)
    except Exception as e:
        print(f"Erro em analisar_mhi: {str(e)}")

def analisar_torres(velas, i, resultados):
    try:
        if i + 2 >= len(velas):
            return
        vela1 = 'Verde' if velas[i-4]['open'] < velas[i-4]['close'] else 'Vermelha'
        direcao = vela1
        entradas = [
            'Verde' if velas[i+j]['open'] < velas[i+j]['close'] else 'Vermelha'
            for j in range(3)
        ]
        resultados = atualizar_resultados(entradas, direcao, resultados)
    except Exception as e:
        print(f"Erro em analisar_torres: {str(e)}")

def atualizar_resultados(entradas, direcao, resultados):
    if entradas[0] == direcao:
        resultados['win'] += 1
    elif entradas[1] == direcao:
        resultados['gale1'] += 1
    elif entradas[2] == direcao:
        resultados['gale2'] += 1
    else:
        resultados['loss'] += 1
    return resultados

def calcular_percentuais(resultados):
    total_entradas = sum(resultados.values()) - resultados['doji']
    if total_entradas == 0:
        return [0, 0, 0]
    win_rate = round(resultados['win'] / total_entradas * 100, 2)
    gale1_rate = round((resultados['win'] + resultados['gale1']) / total_entradas * 100, 2)
    gale2_rate = round((resultados['win'] + resultados['gale1'] + resultados['gale2']) / total_entradas * 100, 2)
    return [win_rate, gale1_rate, gale2_rate]

def obter_resultados(API, pares):
    timeframe = 60
    qnt_velas = 60
    qnt_velas_m5 = 75
    estrategias = ['mhi', 'torres', 'mhi_m5']
    resultados = []

    for estrategia in estrategias:
        for par in pares:
            print(f"\n📊 Estratégia: {estrategia.upper()} | Par: {par}")
            tentativas = 0
            velas = None

            while tentativas < 5 and velas is None:
                try:
                    print("🕒 Solicitando velas...")
                    velas = API.get_candles(par, timeframe if estrategia != 'mhi_m5' else 300,
                                            qnt_velas if estrategia != 'mhi_m5' else qnt_velas_m5,
                                            time.time())

                    if not velas or len(velas) == 0:
                        print(f"⚠️ Nenhuma vela retornada para {par}, pulando para o próximo.")
                        velas = None
                        break

                except Exception as e:
                    tentativas += 1
                    print(f"⚠️ Tentativa {tentativas}/5: Erro ao obter velas de {par} - {str(e)}")
                    try:
                        API = reconectar_api(API)
                        if not API.check_connect():
                            raise Exception("Reconexão falhou")
                        time.sleep(10)
                    except Exception as e:
                        print(f"❌ Reconexão falhou: {str(e)}")
                    velas = None

            if velas:
                resultados_estrategia = analisar_velas(velas, estrategia)
                percentuais = calcular_percentuais(resultados_estrategia)
                resultados.append([estrategia.upper(), par] + percentuais)
                time.sleep(3)

    return resultados

def reconectar_api(API):
    config = ConfigObj('config.txt')
    try:
        API.close()
    except:
        pass
    time.sleep(2)
    API = IQ_Option(config['LOGIN']['email'], config['LOGIN']['senha'])
    for i in range(3):
        try:
            conectado, erro = API.connect()
            if conectado:
                API.change_balance('PRACTICE')
                time.sleep(1)
                return API
            else:
                print(f"Tentativa {i+1}/3: Falha ao reconectar: {erro}")
                time.sleep(3)
        except Exception as e:
            print(f"Erro de conexão: {str(e)}")
            time.sleep(3)
    raise Exception("Falha crítica ao reconectar com a API")

def catag(API):
    config = ConfigObj('config.txt')
    pares = obter_pares_abertos(API)
    resultados = obter_resultados(API, pares)
    if config['MARTINGALE']['usar_martingale'] == 'S':
        linha = 2 + int(config['MARTINGALE']['niveis_martingale'])
    else:
        linha = 2
    resultados_ordenados = sorted(resultados, key=lambda x: x[linha], reverse=True)
    return resultados_ordenados, linha

# ============================
# EXECUÇÃO PRINCIPAL
# ============================
if __name__ == "__main__":
    config = ConfigObj('config.txt')
    max_tentativas = 3
    tentativa = 0

    while tentativa < max_tentativas:
        try:
            API = IQ_Option(config['LOGIN']['email'], config['LOGIN']['senha'])
            conectado, erro = API.connect()
            if conectado:
                print("✅ Conexão com IQ Option realizada com sucesso!")
                API.change_balance('PRACTICE')
                try:
                    catalog, linha = catag(API)
                    headers = ["Estratégia", "Par", "Win%", "Gale1%", "Gale2%"]
                    print(tabulate(catalog, headers=headers, tablefmt="pretty"))
                    break
                except Exception as e:
                    print(f"❌ Erro ao processar catálogo: {str(e)}")
                    tentativa += 1
                    time.sleep(5)
            else:
                print(f"❌ Tentativa {tentativa+1}/{max_tentativas}: Falha ao conectar: {erro}")
                tentativa += 1
                time.sleep(5)
        except Exception as e:
            print(f"❌ Tentativa {tentativa+1}/{max_tentativas}: Erro inesperado: {str(e)}")
            tentativa += 1
            time.sleep(5)
        finally:
            try:
                if 'API' in locals() and API:
                    API.close()
            except:
                pass

    if tentativa >= max_tentativas:
        print("❌ Não foi possível executar o programa após várias tentativas.")