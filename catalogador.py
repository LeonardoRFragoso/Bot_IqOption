from iqoptionapi.stable_api import IQ_Option
import time
from configobj import ConfigObj
from datetime import datetime
from tabulate import tabulate

def safe_get_candles(API, par, timeframe, count, end_time):
    """
    Tenta obter candles utilizando API.get_candles com até 5 tentativas.
    Se a mensagem de erro indicar "get_candles need reconnect", recria a instância
    da API utilizando as credenciais do arquivo de configuração e reconecta.
    Retorna uma tupla (candles, API_atualizada).
    """
    max_attempts = 5
    attempts = 0
    candles = None
    config = ConfigObj('config.txt')
    email = config['LOGIN']['email']
    senha = config['LOGIN']['senha']
    
    while attempts < max_attempts and not candles:
        try:
            candles = API.get_candles(par, timeframe, count, end_time)
            if candles:
                return candles, API
        except Exception as e:
            err_msg = str(e)
            print(f"⚠️ Erro get_candles para {par} (tentativa {attempts+1}/{max_attempts}): {err_msg}")
            if "get_candles need reconnect" in err_msg:
                try:
                    new_api = IQ_Option(email, senha)
                    conectado, motivo = new_api.connect()
                    if conectado:
                        # Ajuste o tipo de conta conforme necessário (aqui, 'PRACTICE')
                        new_api.change_balance('PRACTICE')
                        API = new_api  # atualiza a instância da API usada
                        print(f"🔄 Reconectado com sucesso para {par}.")
                    else:
                        print(f"❌ Falha na reconexão: {motivo}")
                except Exception as e2:
                    print(f"❌ Erro durante reconexão: {e2}")
        attempts += 1
        time.sleep(3)
    return candles, API

def obter_pares_abertos(API):
    todos_os_ativos = API.get_all_open_time()
    pares = []
    for par in todos_os_ativos['digital']:
        if todos_os_ativos['digital'][par]['open']:
            pares.append(par)
    for par in todos_os_ativos['turbo']:
        if todos_os_ativos['turbo'][par]['open'] and par not in pares:
            pares.append(par)
    return pares

def analisar_velas(velas, tipo_estrategia):
    resultados = {'doji': 0, 'win': 0, 'loss': 0, 'gale1': 0, 'gale2': 0}
    for i in range(2, len(velas)):
        # Conforme versão original: remove o primeiro dígito dos minutos
        minutos = float(datetime.fromtimestamp(velas[i]['from']).strftime('%M')[1:])
        if tipo_estrategia == 'mhi' and (minutos == 5 or minutos == 0):
            analisar_mhi(velas, i, resultados)
        elif tipo_estrategia == 'torres' and (minutos == 4 or minutos == 9):
            analisar_torres(velas, i, resultados)
        elif tipo_estrategia == 'mhi_m5' and (minutos == 30 or minutos == 0):
            analisar_mhi(velas, i, resultados, timeframe=300)
    return resultados

def analisar_mhi(velas, i, resultados, timeframe=60):
    try:
        vela1 = 'Verde' if velas[i-3]['open'] < velas[i-3]['close'] else 'Vermelha'
        vela2 = 'Verde' if velas[i-2]['open'] < velas[i-2]['close'] else 'Vermelha'
        vela3 = 'Verde' if velas[i-1]['open'] < velas[i-1]['close'] else 'Vermelha'
        # Define a direção: se mais de uma vela for "Verde", direção é Verde; caso contrário, Vermelha.
        direcao = 'Verde' if [vela1, vela2, vela3].count('Verde') > 1 else 'Vermelha'
        entradas = [
            'Verde' if velas[i+j]['open'] < velas[i+j]['close'] else 'Vermelha'
            for j in range(3)
        ]
        resultados = atualizar_resultados(entradas, direcao, resultados)
    except Exception as e:
        print(f"Erro em analisar_mhi: {e}")

def analisar_torres(velas, i, resultados):
    try:
        vela1 = 'Verde' if velas[i-4]['open'] < velas[i-4]['close'] else 'Vermelha'
        direcao = vela1
        entradas = [
            'Verde' if velas[i+j]['open'] < velas[i+j]['close'] else 'Vermelha'
            for j in range(3)
        ]
        resultados = atualizar_resultados(entradas, direcao, resultados)
    except Exception as e:
        print(f"Erro em analisar_torres: {e}")

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
    qnt_velas = 120
    qnt_velas_m5 = 146
    estrategias = ['mhi', 'torres', 'mhi_m5']
    resultados = []
    
    # Para cada estratégia e cada par aberto, tenta obter os candles de forma robusta.
    for estrategia in estrategias:
        for par in pares:
            tentativas = 0
            velas = None
            # Utilize safe_get_candles e atualize a instância da API, se necessário.
            while tentativas < 5 and not velas:
                if estrategia != 'mhi_m5':
                    velas, API = safe_get_candles(API, par, timeframe, qnt_velas, time.time())
                else:
                    velas, API = safe_get_candles(API, par, timeframe, qnt_velas_m5, time.time())
                if not velas:
                    print(f"⚠️ Tentativa {tentativas+1}: falha ao obter velas de {par}. Reconectando em 2 segundos...")
                    try:
                        API.connect()
                        API.change_balance('PRACTICE')
                    except Exception as recon_err:
                        print(f"Erro na reconexão: {recon_err}")
                    time.sleep(2)
                    tentativas += 1

            if velas:
                resultados_estrategia = analisar_velas(velas, estrategia)
                percentuais = calcular_percentuais(resultados_estrategia)
                resultados.append([estrategia.upper(), par] + percentuais)
                time.sleep(1)
            else:
                print(f"❌ Não foi possível obter os dados do ativo {par} após múltiplas tentativas.")
    return resultados

def catag(API):
    config = ConfigObj('config.txt')
    pares = obter_pares_abertos(API)
    resultados = obter_resultados(API, pares)
    
    # Define a linha de referência para ordenação de acordo com as configurações
    if config['MARTINGALE']['usar_martingale'] == 'S':
        linha = 2 + int(config['MARTINGALE']['niveis_martingale'])
    else:
        linha = 2
        
    resultados_ordenados = sorted(resultados, key=lambda x: x[linha], reverse=True)
    return resultados_ordenados, linha

if __name__ == "__main__":
    config = ConfigObj('config.txt')
    API = IQ_Option(config['LOGIN']['email'], config['LOGIN']['senha'])
    conectado, erro = API.connect()
    if conectado:
        print("✅ Conexão com IQ Option realizada com sucesso!")
    else:
        print(f"❌ Falha ao conectar: {erro}")
        exit()
    API.change_balance('PRACTICE')  # Use 'REAL' se necessário
    catalog, linha = catag(API)
    headers = ["Estratégia", "Par", "Win%", "Gale1%", "Gale2%"]
    print(tabulate(catalog, headers=headers, tablefmt="pretty"))
