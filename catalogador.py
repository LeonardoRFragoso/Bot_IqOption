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

def obter_pares_abertos(API, tipo_par="Automático (Prioriza OTC)"):
    """
    Obtém os pares disponíveis para negociação, verificando tanto pares OTC quanto normais.
    Dependendo do dia da semana e horário, retorna os pares apropriados.
    
    Args:
        API: Objeto da API IQ Option
        tipo_par: String indicando a preferência de tipo de par
                  "Automático (Prioriza OTC)" - Prioriza OTC, mas usa normais se OTC não estiver disponível
                  "Apenas OTC" - Retorna apenas pares OTC
                  "Apenas Normais" - Retorna apenas pares normais
    """
    try:
        # Lista de pares que queremos monitorar (tanto OTC quanto normais)
        pares_base = [
            'EURUSD',
            'EURGBP',
            'USDCHF',
            'GBPUSD',
            'GBPJPY',
            'USDJPY',
            'AUDUSD',
            'EURJPY',
            'NZDUSD'
        ]
        
        # Cria as versões OTC dos pares
        pares_otc = [f"{par}-OTC" for par in pares_base]
        
        # Obtém todos os pares disponíveis da API
        all_asset = API.get_all_open_time()
        
        # Verifica quais pares estão abertos para negociação binária
        pares_normais_abertos = []
        pares_otc_abertos = []
        
        # Verifica pares normais se necessário
        if tipo_par in ["Automático (Prioriza OTC)", "Apenas Normais"]:
            for par in pares_base:
                try:
                    if par in all_asset['binary'] and all_asset['binary'][par]['open']:
                        pares_normais_abertos.append(par)
                except:
                    pass
        
        # Verifica pares OTC se necessário
        if tipo_par in ["Automático (Prioriza OTC)", "Apenas OTC"]:
            for par in pares_otc:
                try:
                    if par in all_asset['binary'] and all_asset['binary'][par]['open']:
                        pares_otc_abertos.append(par)
                except:
                    pass
        
        # Lógica de seleção baseada na preferência do usuário
        pares_disponiveis = []
        
        if tipo_par == "Automático (Prioriza OTC)":
            # Se tivermos pares OTC disponíveis, usamos eles preferencialmente
            if len(pares_otc_abertos) > 0:
                pares_disponiveis.extend(pares_otc_abertos)
            # Se não houver pares OTC, usamos os pares normais
            elif len(pares_normais_abertos) > 0:
                pares_disponiveis.extend(pares_normais_abertos)
        elif tipo_par == "Apenas OTC":
            pares_disponiveis.extend(pares_otc_abertos)
        elif tipo_par == "Apenas Normais":
            pares_disponiveis.extend(pares_normais_abertos)
        
        # Se não houver nenhum par disponível, retorna uma lista vazia
        if len(pares_disponiveis) == 0:
            print(f"⚠️ Nenhum par {tipo_par.lower()} disponível para negociação no momento.")
            return []
            
        print(f"✅ Pares disponíveis ({tipo_par}): {pares_disponiveis}")
        return pares_disponiveis
        
    except Exception as e:
        print(f"❌ Erro ao obter pares abertos: {str(e)}")
        # Em caso de erro, retorna uma lista vazia
        return []

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
        elif tipo_estrategia == 'bb':
            analisar_bb(velas, i, resultados)
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

def analisar_bb(velas, i, resultados):
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
        print(f"Erro em analisar_bb: {str(e)}")

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
    estrategias = ['mhi', 'torres', 'mhi_m5', 'bb']
    resultados = []

    # Verifica se há pares disponíveis
    if not pares or len(pares) == 0:
        print("❌ Não há pares disponíveis para análise.")
        return []

    for estrategia in estrategias:
        for par in pares:
            print(f"\n📊 Estratégia: {estrategia.upper()} | Par: {par}")
            tentativas = 0
            velas = None

            while tentativas < 3 and velas is None:
                try:
                    print("🕒 Solicitando velas...")
                    
                    # Verifica se o par está disponível antes de solicitar velas
                    all_asset = API.get_all_open_time()
                    if par not in all_asset['binary'] or not all_asset['binary'][par]['open']:
                        print(f"⚠️ Par {par} não está disponível no momento, pulando.")
                        break
                    
                    # Define o timeframe correto para cada estratégia
                    tf = 300 if estrategia in ['mhi_m5', 'bb'] else timeframe
                    qnt = qnt_velas_m5 if estrategia in ['mhi_m5', 'bb'] else qnt_velas
                    
                    velas = API.get_candles(par, tf, qnt, time.time())

                    if not velas or len(velas) == 0:
                        print(f"⚠️ Nenhuma vela retornada para {par}, pulando para o próximo.")
                        velas = None
                        break
                    
                    # Verifica se temos velas suficientes para análise
                    if len(velas) < (qnt * 0.9):  
                        print(f"⚠️ Número insuficiente de velas para {par}: {len(velas)}/{qnt}, pulando.")
                        velas = None
                        break

                except Exception as e:
                    tentativas += 1
                    print(f"⚠️ Tentativa {tentativas}/3: Erro ao obter velas de {par} - {str(e)}")
                    try:
                        API = reconectar_api(API)
                        if not API.check_connect():
                            raise Exception("Reconexão falhou")
                        time.sleep(5)  
                    except Exception as e:
                        print(f"❌ Reconexão falhou: {str(e)}")
                    velas = None

            if velas:
                try:
                    resultados_estrategia = analisar_velas(velas, estrategia)
                    percentuais = calcular_percentuais(resultados_estrategia)
                    resultados.append([estrategia.upper(), par] + percentuais)
                    print(f"✅ Análise concluída para {estrategia.upper()} | {par}")
                except Exception as e:
                    print(f"❌ Erro ao analisar {estrategia.upper()} | {par}: {str(e)}")
                
                time.sleep(1)  

    # Verifica se temos resultados
    if not resultados or len(resultados) == 0:
        print("❌ Nenhum resultado obtido na análise.")
        return []
        
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

def catag(API, tipo_par="Automático (Prioriza OTC)"):
    config = ConfigObj('config.txt')
    
    # Se não foi passado um tipo_par, tenta ler da configuração
    if tipo_par == "Automático (Prioriza OTC)" and 'AJUSTES' in config and 'tipo_par' in config['AJUSTES']:
        tipo_par = config['AJUSTES']['tipo_par']
    
    pares = obter_pares_abertos(API, tipo_par)
    resultados = obter_resultados(API, pares)
    
    if not resultados or len(resultados) == 0:
        print("❌ Nenhum resultado obtido na catalogação.")
        return [], 2
        
    if config['MARTINGALE']['usar'] == 'S':
        linha = 2 + int(config['MARTINGALE']['niveis'])
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
                    catalog, linha = catag(API, config['AJUSTES']['tipo_par'] if 'AJUSTES' in config and 'tipo_par' in config['AJUSTES'] else "Automático (Prioriza OTC)")
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