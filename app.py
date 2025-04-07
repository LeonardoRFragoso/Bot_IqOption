import streamlit as st
import json
import time
import threading
from configobj import ConfigObj
from iqoptionapi.stable_api import IQ_Option
from tabulate import tabulate
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import logging
import os
from catalogador import catag  # Note: a função obter_pares_abertos não é usada diretamente

# ============================
# Definição de GetCandlesFilter
# ============================
class GetCandlesFilter(logging.Filter):
    def filter(self, record):
        return "get_candles need reconnect" not in record.getMessage()

# ============================
# Funções de análise técnica (BB, engolfo, etc)
# ============================
def detecta_pinbar(candle):
    open_price = candle['open']
    close_price = candle['close']
    high_price = candle['max']
    low_price = candle['min']
    corpo = abs(close_price - open_price)
    tamanho_total = high_price - low_price
    if tamanho_total == 0 or corpo / tamanho_total > 0.3:
        return False
    if close_price > open_price:
        sombra_inferior = open_price - low_price
        return sombra_inferior / tamanho_total > 0.6
    else:
        sombra_superior = high_price - open_price
        return sombra_superior / tamanho_total > 0.6

def detecta_engolfo(candle_atual, candle_anterior):
    corpo_atual = abs(candle_atual['close'] - candle_atual['open'])
    corpo_anterior = abs(candle_anterior['close'] - candle_anterior['open'])
    if corpo_atual <= corpo_anterior:
        return False
    if candle_atual['close'] > candle_atual['open']:
        if candle_anterior['close'] < candle_anterior['open']:
            return (candle_atual['open'] <= candle_anterior['close'] and 
                    candle_atual['close'] >= candle_anterior['open'])
    if candle_atual['close'] < candle_atual['open']:
        if candle_atual['close'] < candle_atual['open']:
            return (candle_atual['open'] >= candle_anterior['close'] and 
                    candle_atual['close'] <= candle_anterior['open'])
    return False

def detecta_zona_sr(candles, num=10):
    if len(candles) < num:
        return False
    ultimos_candles = candles[-num:]
    maximos = [c['max'] for c in ultimos_candles]
    minimos = [c['min'] for c in ultimos_candles]
    media_max = sum(maximos) / len(maximos)
    media_min = sum(minimos) / len(minimos)
    ultimo_candle = candles[-1]
    preco_atual = ultimo_candle['close']
    margem = preco_atual * 0.02
    return (abs(preco_atual - media_max) < margem or abs(preco_atual - media_min) < margem)

def detecta_fibo(candles, num=10):
    if len(candles) < num:
        return {}
    ultimos_candles = candles[-num:]
    maxima = max([c['max'] for c in ultimos_candles])
    minima = min([c['min'] for c in ultimos_candles])
    amplitude = maxima - minima
    fibo_levels = {
        '0.0': minima,
        '0.236': minima + 0.236 * amplitude,
        '0.382': minima + 0.382 * amplitude,
        '0.5': minima + 0.5 * amplitude,
        '0.618': minima + 0.618 * amplitude,
        '0.786': minima + 0.786 * amplitude,
        '1.0': maxima
    }
    return fibo_levels

def valida_tendencia_macro(api, ativo, timeframe=300, num_candles=100):
    try:
        timestamp_atual = time.time()
        candles = api.get_candles(ativo, timeframe, num_candles, timestamp_atual)
        if candles is None or len(candles) < 50:
            log_message("Dados insuficientes para análise de tendência macro", "warning")
            return True
        closes = [c['close'] for c in candles]
        ma20 = sum(closes[-20:]) / 20
        ma50 = sum(closes[-50:]) / 50
        preco_atual = closes[-1]
        tendencia_alta = preco_atual > ma20 and ma20 > ma50
        tendencia_baixa = preco_atual < ma20 and ma20 < ma50
        desvio_padrao = (sum([(close - ma20) ** 2 for close in closes[-20:]]) / 20) ** 0.5
        volatilidade_normal = desvio_padrao / ma20 < 0.03
        return (tendencia_alta or tendencia_baixa) and volatilidade_normal
    except Exception as e:
        log_message(f"Erro ao validar tendência macro: {str(e)}", "error")
        return True

def log_auditoria(mensagem, ativo, estrategia):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("auditoria_sinais.csv", "a") as arquivo:
            if arquivo.tell() == 0:
                arquivo.write("Timestamp,Ativo,Estrategia,Mensagem\n")
            arquivo.write(f"{timestamp},{ativo},{estrategia},{mensagem}\n")
    except Exception as e:
        log_message(f"Erro ao registrar auditoria: {str(e)}", "error")

# ============================
# Configuração de logging
# ============================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot_log.txt"), logging.StreamHandler()]
)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.addFilter(GetCandlesFilter())
logging.getLogger("iqoptionapi").addFilter(GetCandlesFilter())

# ============================
# Configuração do Streamlit
# ============================
st.set_page_config(
    page_title="Bot IQ Option Trader",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background: linear-gradient(to bottom, #1E1E2E, #2D2D44); color: #E0E0E0; }
    .main-header { font-size: 2.5rem; background: linear-gradient(90deg, #0078ff, #00bfff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; margin-bottom: 1.5rem; font-weight: 700; }
    .sub-header { font-size: 1.8rem; background: linear-gradient(90deg, #0078ff, #00bfff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-top: 1.5rem; font-weight: 600; }
    .success-message { color: #28a745; font-weight: bold; }
    .error-message { color: #dc3545; font-weight: bold; }
    .info-message { color: #17a2b8; font-weight: bold; }
    .card { background-color: rgba(45, 45, 68, 0.7); border-radius: 10px; padding: 15px; border: 1px solid #3D3D60; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); }
    .log-container { background-color: rgba(30, 30, 46, 0.7); border-radius: 5px; padding: 10px; height: 300px; overflow-y: auto; font-family: monospace; border: 1px solid #3D3D60; }
</style>
""", unsafe_allow_html=True)

# Inicialização de variáveis de estado
if "connected" not in st.session_state:
    st.session_state.connected = False
if "API" not in st.session_state:
    st.session_state.API = None
if "bot_running" not in st.session_state:
    st.session_state.bot_running = False
if "stop_bot" not in st.session_state:
    st.session_state.stop_bot = False
if "operations" not in st.session_state:
    st.session_state.operations = []
if "log_messages" not in st.session_state:
    st.session_state.log_messages = []
if "catalog_results" not in st.session_state:
    st.session_state.catalog_results = None
if "catalog_line" not in st.session_state:
    st.session_state.catalog_line = 0
if "lucro_total" not in st.session_state:
    st.session_state.lucro_total = 0
if "wins" not in st.session_state:
    st.session_state.wins = 0
if "losses" not in st.session_state:
    st.session_state.losses = 0
if "total_ops" not in st.session_state:
    st.session_state.total_ops = 0

_config_cache = None

def load_config():
    global _config_cache
    try:
        if _config_cache is not None:
            return _config_cache
        if os.path.exists('config.txt'):
            config = ConfigObj('config.txt', encoding='utf-8')
            log_message("Configurações carregadas com sucesso")
            _config_cache = config
            return config
        else:
            log_message("Arquivo de configuração não encontrado. Criando novo...", "warning")
            config = ConfigObj()
            config.filename = 'config.txt'
            config['LOGIN'] = {'email': '', 'senha': ''}
            config['AJUSTES'] = {
                'tipo': 'binary', 
                'valor_entrada': '2', 
                'stop_win': '15', 
                'stop_loss': '15',
                'analise_medias': 'N',
                'velas_medias': '20',
                'tipo_par': 'Automático (Prioriza OTC)'
            }
            config['MARTINGALE'] = {'usar': 'N', 'niveis': '2', 'fator': '2.0'}
            config['SOROS'] = {'usar': 'N', 'niveis': '2'}
            config.write()
            _config_cache = config
            return config
    except Exception as e:
        log_message(f"Erro ao carregar configurações: {str(e)}", "error")
        return None

def save_config(config_data):
    global _config_cache
    try:
        config = ConfigObj()
        config.encoding = 'utf-8'
        config['LOGIN'] = {'email': config_data['email'], 'senha': config_data['senha']}
        config['AJUSTES'] = {
            'tipo': config_data['tipo'],
            'valor_entrada': str(config_data['valor_entrada']),
            'stop_win': str(config_data['stop_win']),
            'stop_loss': str(config_data['stop_loss']),
            'analise_medias': 'S' if config_data['analise_medias'] else 'N',
            'velas_medias': str(config_data['velas_medias']),
            'tipo_par': config_data['tipo_par']
        }
        config['MARTINGALE'] = {
            'usar': 'S' if config_data['usar_martingale'] else 'N',
            'niveis': str(config_data['niveis_martingale']),
            'fator': str(config_data['fator_martingale'])
        }
        config['SOROS'] = {
            'usar': 'S' if config_data['usar_soros'] else 'N',
            'niveis': str(config_data['niveis_soros'])
        }
        config.filename = 'config.txt'
        config.write()
        _config_cache = config
        log_message("Configurações salvas com sucesso", "success")
        return True
    except Exception as e:
        log_message(f"Erro ao salvar configurações: {str(e)}", "error")
        return False

def connect_iqoption(email, senha, conta):
    try:
        log_message(f"Iniciando conexão com a IQ Option... Tipo de conta selecionada: {conta}")
        api = IQ_Option(email, senha)
        retry_count = 0
        max_retries = 3
        connected = False
        while not connected and retry_count < max_retries:
            try:
                check, reason = api.connect()
                if check:
                    connected = True
                    log_message("Conectado com sucesso!", "success")
                else:
                    retry_count += 1
                    log_message(f"Tentativa {retry_count}/{max_retries} falhou: {reason}", "warning")
                    time.sleep(2)
            except Exception as e:
                if "getaddrinfo failed" in str(e):
                    log_message("Erro de resolução DNS. Verifique sua conexão e configurações de DNS.", "error")
                retry_count += 1
                log_message(f"Erro na tentativa {retry_count}/{max_retries}: {str(e)}", "warning")
                time.sleep(2)
        if not connected:
            log_message("Todas as tentativas de conexão falharam", "error")
            return None
        try:
            if conta == "Demo":
                log_message("Alterando para conta DEMO...", "info")
                api.change_balance("PRACTICE")
                log_message("Conta DEMO selecionada com sucesso", "info")
            else:
                log_message("Alterando para conta REAL...", "warning")
                api.change_balance("REAL")
                log_message("Conta REAL selecionada com sucesso", "warning")
        except Exception as e:
            log_message(f"Erro ao selecionar tipo de conta: {str(e)}", "error")
            try:
                api.change_balance("PRACTICE")
                log_message("Fallback para conta DEMO realizado", "warning")
            except:
                log_message("Não foi possível selecionar nenhum tipo de conta", "error")
                return None
        try:
            perfil = json.loads(json.dumps(api.get_profile_ansyc()))
            st.session_state.nome = str(perfil['name'])
            st.session_state.cifrao = str(perfil['currency_char'])
            st.session_state.saldo = float(api.get_balance())
            log_message(f"Bem-vindo {st.session_state.nome}! Saldo atual: {st.session_state.cifrao} {st.session_state.saldo}")
            log_message(f"Tipo de conta atual: {api.get_balance_mode()}", "info")
            return api
        except Exception as e:
            log_message(f"Erro ao obter informações do perfil: {str(e)}", "error")
            return None
    except Exception as e:
        log_message(f"Exceção ao conectar: {str(e)}", "error")
        return None

def check_asset_available(api, asset, option_type="binary"):
    try:
        if option_type == "digital":
            asset_list = api.get_digital_underlying()
        else:
            asset_list = api.get_all_open_time()["binary"]
        if option_type == "digital" and asset in asset_list:
            return True
        elif option_type == "binary" and asset in asset_list and asset_list[asset]["open"]:
            return True
        else:
            return False
    except Exception as e:
        log_message(f"Erro ao verificar disponibilidade do ativo: {str(e)}", "error")
        return False

def get_payout(api, asset, option_type="binary"):
    try:
        if option_type == "digital":
            return api.get_digital_payout(asset)
        else:
            return api.get_all_profit()[asset]["turbo"] * 100
    except Exception as e:
        log_message(f"Erro ao obter payout: {str(e)}", "error")
        return 0

def run_catalogador(api):
    try:
        st.session_state.catalogando = True
        with st.spinner("Iniciando catalogação de ativos..."):
            logging.info("Iniciando catalogação de ativos...")
            if _config_cache:
                logging.info("Usando configurações em cache")
                config = _config_cache
            else:
                config = load_config()
            tipo_par = config.get('AJUSTES', {}).get('tipo_par', "Automático (Todos os Pares)")
            logging.info(f"Tipo de par selecionado: {tipo_par}")
            if tipo_par == "Automático (Todos os Pares)":
                logging.info("Buscando todos os pares disponíveis (OTC e normais)...")
                st.info("Buscando todos os pares disponíveis (OTC e normais)...")
            elif tipo_par == "Automático (Prioriza OTC)":
                logging.info("Buscando pares OTC (com fallback para normais)...")
                st.info("Buscando pares OTC (com fallback para normais)...")
            elif tipo_par == "Apenas OTC":
                logging.info("Buscando apenas pares OTC...")
                st.info("Buscando apenas pares OTC...")
            elif tipo_par == "Apenas Normais":
                logging.info("Buscando apenas pares normais...")
                st.info("Buscando apenas pares normais...")
            try:
                catalog, linha = catag(api, tipo_par, config)
                if catalog is None or len(catalog) == 0:
                    st.error("Não foi possível obter resultados da catalogação. Tente novamente mais tarde.")
                    log_message("Falha na catalogação: Nenhum resultado obtido", "error")
                    st.session_state.catalogando = False
                    return
                st.session_state.catalog_results = catalog
                st.session_state.catalog_line = linha
                df = pd.DataFrame(catalog, columns=["Estratégia", "Par", "Win%", "Gale1%", "Gale2%"])
                for col in ["Win%", "Gale1%", "Gale2%"]:
                    df[col] = df[col].apply(lambda x: f"{x:.2f}%")
                st.dataframe(df, use_container_width=True)
                best_strategy = catalog[0][0]
                best_asset = catalog[0][1]
                best_rate = catalog[0][linha]
                st.success(f"Melhor combinação: Estratégia {best_strategy} com o ativo {best_asset} - Taxa de acerto: {best_rate:.2f}%")
                log_message(f"Catalogação concluída com {len(catalog)} estratégias. Melhor: {best_strategy}/{best_asset} com {best_rate:.2f}%", "success")
            except Exception as e:
                st.error(f"Erro durante a catalogação: {str(e)}")
                log_message(f"Erro na catalogação: {str(e)}", "error")
                logging.error(f"Erro durante a catalogação: {str(e)}")
        st.session_state.catalogando = False
    except Exception as e:
        st.error(f"Erro ao executar catalogação: {str(e)}")
        log_message(f"Erro ao executar catalogação: {str(e)}", "error")
        logging.error(f"Erro ao executar catalogação: {str(e)}")
        st.session_state.catalogando = False

def run_trading_bot(api, estrategia, ativo, config_data):
    try:
        if not api or not api.check_connect():
            st.error("API não conectada. Por favor, conecte-se primeiro.")
            log_message("Tentativa de iniciar bot sem conexão com a API", "error")
            return
        if not estrategia:
            st.error("Nenhuma estratégia selecionada.")
            log_message("Tentativa de iniciar bot sem selecionar estratégia", "error")
            return
        if not ativo:
            st.error("Nenhum ativo selecionado.")
            log_message("Tentativa de iniciar bot sem selecionar ativo", "error")
            return
        disponivel = check_asset_available(api, ativo)
        if not disponivel:
            st.error(f"O ativo {ativo} não está disponível no momento.")
            log_message(f"Ativo {ativo} não disponível", "error")
            return
        payout_value = get_payout(api, ativo)
        if payout_value <= 0:
            st.warning(f"Payout para {ativo} não disponível ou muito baixo ({payout_value}%). Continuando mesmo assim...")
            log_message(f"Payout baixo para {ativo}: {payout_value}%", "warning")
        else:
            log_message(f"Payout para {ativo}: {payout_value}%", "info")
        if "running" not in st.session_state:
            st.session_state.running = False
        if "stop_requested" not in st.session_state:
            st.session_state.stop_requested = False
        if "operations" not in st.session_state:
            st.session_state.operations = []
        if "lucro_total" not in st.session_state:
            st.session_state.lucro_total = 0.0
        if "wins" not in st.session_state:
            st.session_state.wins = 0
        if "losses" not in st.session_state:
            st.session_state.losses = 0
        st.session_state.running = True
        st.session_state.stop_requested = False
        valor_entrada = float(config_data.get('AJUSTES', {}).get('valor_entrada', 2))
        stop_win = float(config_data.get('AJUSTES', {}).get('stop_win', 15))
        stop_loss = float(config_data.get('AJUSTES', {}).get('stop_loss', 10))
        usar_martingale = config_data.get('MARTINGALE', {}).get('usar', 'N').upper() == 'S'
        niveis_martingale = int(config_data.get('MARTINGALE', {}).get('niveis', 0)) if usar_martingale else 0
        fator_martingale = float(config_data.get('MARTINGALE', {}).get('fator', 2.0)) if usar_martingale else 0
        usar_soros = config_data.get('SOROS', {}).get('usar', 'N').upper() == 'S'
        niveis_soros = int(config_data.get('SOROS', {}).get('niveis', 0)) if usar_soros else 0
        tipo_operacao = config_data.get('AJUSTES', {}).get('tipo', 'binary')
        log_message(f"Iniciando bot com estratégia {estrategia} no ativo {ativo}", "info")
        log_message(f"Valor de entrada: {valor_entrada}", "info")
        log_message(f"Stop Win: {stop_win} | Stop Loss: {stop_loss}", "info")
        if usar_martingale:
            log_message(f"Martingale ativado: {niveis_martingale} níveis, fator {fator_martingale}", "info")
        if usar_soros:
            log_message(f"Soros ativado: {niveis_soros} níveis", "info")
        log_message(f"Tipo de operação: {tipo_operacao}", "info")
        def horario():
            return datetime.now().strftime('%H:%M:%S')
        def medias(velas):
            try:
                fechamento = [vela['close'] for vela in velas]
                media_curta = sum(fechamento[-5:]) / 5
                media_longa = sum(fechamento[-15:]) / 15
                if media_curta > media_longa:
                    return "call"
                elif media_curta < media_longa:
                    return "put"
                else:
                    return None
            except Exception as e:
                log_message(f"Erro ao calcular médias: {str(e)}", "error")
                return None
        def check_stop():
            if st.session_state.stop_requested:
                log_message("Parada solicitada pelo usuário", "warning")
                return True
            if st.session_state.lucro_total >= stop_win:
                log_message(f"Stop Win atingido: {st.session_state.lucro_total}", "success")
                return True
            if st.session_state.lucro_total <= -stop_loss:
                log_message(f"Stop Loss atingido: {st.session_state.lucro_total}", "error")
                return True
            return False
        def payout(par):
            try:
                if tipo_operacao == "binary":
                    api.subscribe_strike_list(par, 1)
                    while True:
                        d = api.get_digital_current_profit(par, 1)
                        if d != False:
                            api.unsubscribe_strike_list(par, 1)
                            return int(d)
                else:
                    return int(api.get_all_profit()[par]["turbo"] * 100)
            except Exception as e:
                log_message(f"Erro ao obter payout: {str(e)}", "error")
                return 0
        def compra(ativo, valor_entrada, direcao, exp, tipo_op):
            try:
                log_message(f"Realizando operação: {direcao.upper()} em {ativo} com {valor_entrada}", "info")
                if tipo_op == "digital":
                    status, id = api.buy_digital_spot(ativo, valor_entrada, direcao, exp)
                else:
                    status, id = api.buy(valor_entrada, ativo, direcao, exp)
                if status:
                    log_message(f"Ordem enviada com sucesso. ID: {id}", "success")
                    if tipo_op == "digital":
                        while True:
                            status, lucro = api.check_win_digital_v2(id)
                            if status:
                                break
                        if lucro > 0:
                            resultado = "win"
                            st.session_state.wins += 1
                        else:
                            resultado = "loss"
                            st.session_state.losses += 1
                        st.session_state.lucro_total += lucro
                    else:
                        while True:
                            resultado, lucro = api.check_win_v3(id)
                            if resultado != "open":
                                break
                        if resultado == "win":
                            st.session_state.wins += 1
                            st.session_state.lucro_total += lucro
                        elif resultado == "loss":
                            st.session_state.losses += 1
                            st.session_state.lucro_total -= valor_entrada
                        else:
                            log_message(f"Resultado desconhecido: {resultado}", "warning")
                    operacao = {
                        "timestamp": horario(),
                        "ativo": ativo,
                        "direcao": direcao,
                        "valor": valor_entrada,
                        "resultado": resultado,
                        "lucro": lucro if resultado == "win" else -valor_entrada,
                        "lucro_acumulado": st.session_state.lucro_total
                    }
                    st.session_state.operations.append(operacao)
                    log_message(f"Resultado: {resultado.upper()} | Lucro: {lucro if resultado == 'win' else -valor_entrada} | Total: {st.session_state.lucro_total}", "info")
                    return resultado, lucro
                else:
                    log_message(f"Erro ao enviar ordem: {id}", "error")
                    return None, 0
            except Exception as e:
                log_message(f"Erro na operação: {str(e)}", "error")
                return None, 0
        while st.session_state.running and not check_stop():
            try:
                if estrategia == "MHI":
                    minutos = datetime.now().minute
                    segundos = datetime.now().second
                    entrar = (minutos % 5 == 0 and segundos < 30)
                    if entrar:
                        log_message("Analisando entrada para estratégia MHI", "info")
                        velas = api.get_candles(ativo, 60, 3, time.time())
                        cores = []
                        for vela in velas:
                            if vela['open'] < vela['close']:
                                cores.append('Verde')
                            elif vela['open'] > vela['close']:
                                cores.append('Vermelha')
                            else:
                                cores.append('Doji')
                        log_message(f"Velas: {cores}", "info")
                        if cores.count('Verde') > cores.count('Vermelha') and 'Doji' not in cores:
                            direcao = 'put'
                            log_message(f"Sinal identificado: {direcao.upper()}", "info")
                            compra(ativo, valor_entrada, direcao, 1, tipo_operacao)
                        elif cores.count('Verde') < cores.count('Vermelha') and 'Doji' not in cores:
                            direcao = 'call'
                            log_message(f"Sinal identificado: {direcao.upper()}", "info")
                            compra(ativo, valor_entrada, direcao, 1, tipo_operacao)
                        else:
                            log_message("Sem sinal claro. Aguardando próxima oportunidade.", "warning")
                elif estrategia == "Torres Gêmeas":
                    minutos = datetime.now().minute
                    segundos = datetime.now().second
                    entrar = (minutos % 5 == 4 and segundos < 30)
                    if entrar:
                        log_message("Analisando entrada para estratégia Torres Gêmeas", "info")
                        velas = api.get_candles(ativo, 60, 5, time.time())
                        if velas[0]['open'] < velas[0]['close']:
                            direcao = 'call'
                            log_message(f"Sinal identificado: {direcao.upper()}", "info")
                            compra(ativo, valor_entrada, direcao, 1, tipo_operacao)
                        elif velas[0]['open'] > velas[0]['close']:
                            direcao = 'put'
                            log_message(f"Sinal identificado: {direcao.upper()}", "info")
                            compra(ativo, valor_entrada, direcao, 1, tipo_operacao)
                        else:
                            log_message("Sem sinal claro. Aguardando próxima oportunidade.", "warning")
                elif estrategia == "MHI Maioria":
                    minutos = datetime.now().minute
                    segundos = datetime.now().second
                    entrar = (minutos % 5 == 0 and segundos < 30)
                    if entrar:
                        log_message("Analisando entrada para estratégia MHI Maioria", "info")
                        velas = api.get_candles(ativo, 60, 5, time.time())
                        altas = sum(1 for vela in velas if vela['open'] < vela['close'])
                        baixas = sum(1 for vela in velas if vela['open'] > vela['close'])
                        log_message(f"Velas de alta: {altas}, Velas de baixa: {baixas}", "info")
                        if altas > baixas:
                            direcao = 'call'
                            log_message(f"Sinal identificado: {direcao.upper()}", "info")
                            compra(ativo, valor_entrada, direcao, 1, tipo_operacao)
                        elif baixas > altas:
                            direcao = 'put'
                            log_message(f"Sinal identificado: {direcao.upper()}", "info")
                            compra(ativo, valor_entrada, direcao, 1, tipo_operacao)
                        else:
                            log_message("Sem sinal claro. Aguardando próxima oportunidade.", "warning")
                else:
                    log_message(f"Estratégia {estrategia} não implementada", "error")
                    break
                time.sleep(5)
            except Exception as e:
                log_message(f"Erro no loop de trading: {str(e)}", "error")
                time.sleep(5)
        st.session_state.running = False
        log_message("Bot finalizado", "info")
        log_message(f"Resultado final: {st.session_state.wins} wins, {st.session_state.losses} losses, lucro total: {st.session_state.lucro_total}", "info")
    except Exception as e:
        st.session_state.running = False
        log_message(f"Erro fatal no bot: {str(e)}", "error")
        st.error(f"Erro ao executar o bot: {str(e)}")

def log_message(message, message_type="info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    if message_type == "success":
        formatted_message = f"<span style='color: #28a745;'>[{timestamp}] {message}</span>"
    elif message_type == "error":
        formatted_message = f"<span style='color: #dc3545;'>[{timestamp}] {message}</span>"
    elif message_type == "warning":
        formatted_message = f"<span style='color: #ffc107;'>[{timestamp}] {message}</span>"
    elif message_type == "operation":
        formatted_message = f"<span style='color: #9370DB;'>[{timestamp}] {message}</span>"
    else:
        formatted_message = f"<span style='color: #E0E0E0;'>[{timestamp}] {message}</span>"
    st.session_state.log_messages.append(formatted_message)
    logging.info(message)

# ============================
# Sidebar - Configurações e Login
# ============================
with st.sidebar:
    st.markdown("<h3 class='sub-header'>Configurações</h3>", unsafe_allow_html=True)
    if _config_cache is not None:
        config = _config_cache
        log_message("Usando configurações em cache para a interface", "info")
    else:
        config = load_config()
        _config_cache = config
    with st.expander("Credenciais IQ Option", expanded=True):
        email = st.text_input("Email", value=config['LOGIN']['email'] if config and 'LOGIN' in config else "", placeholder="Seu email na IQ Option")
        senha = st.text_input("Senha", value=config['LOGIN']['senha'] if config and 'LOGIN' in config else "", type="password", placeholder="Sua senha")
        conta = st.selectbox("Tipo de Conta", ["Demo", "Real"], index=0)
    with st.expander("Configurações de Operação", expanded=True):
        tipo = st.selectbox("Tipo de Operação", ["binary", "digital", "automatico"],
                            index=0 if not config or 'AJUSTES' not in config else ["binary", "digital", "automatico"].index(config['AJUSTES']['tipo']))
        col1, col2 = st.columns(2)
        with col1:
            valor_entrada_config = 2.0
            if config and 'AJUSTES' in config and 'valor_entrada' in config['AJUSTES']:
                try:
                    valor_entrada_config = max(2.0, float(config['AJUSTES']['valor_entrada']))
                except (ValueError, TypeError):
                    valor_entrada_config = 2.0
            valor_entrada = st.number_input("Valor Entrada", min_value=2.0, value=valor_entrada_config, step=1.0)
        with col2:
            velas_medias_config = 20
            if config and 'AJUSTES' in config and 'velas_medias' in config['AJUSTES']:
                try:
                    velas_medias_config = max(3, int(config['AJUSTES']['velas_medias']))
                except (ValueError, TypeError):
                    velas_medias_config = 20
            velas_medias = st.number_input("Velas p/ Médias", min_value=3, value=velas_medias_config, step=1)
        col1, col2 = st.columns(2)
        with col1:
            stop_win_config = 15.0
            if config and 'AJUSTES' in config and 'stop_win' in config['AJUSTES']:
                try:
                    stop_win_config = max(1.0, float(config['AJUSTES']['stop_win']))
                except (ValueError, TypeError):
                    stop_win_config = 15.0
            stop_win = st.number_input("Stop Win", min_value=1.0, value=stop_win_config, step=1.0)
        with col2:
            stop_loss_config = 15.0
            if config and 'AJUSTES' in config and 'stop_loss' in config['AJUSTES']:
                try:
                    stop_loss_config = max(1.0, float(config['AJUSTES']['stop_loss']))
                except (ValueError, TypeError):
                    stop_loss_config = 15.0
            stop_loss = st.number_input("Stop Loss", min_value=1.0, value=stop_loss_config, step=1.0)
        analise_medias = st.checkbox("Usar Análise de Médias", value=True if config and 'AJUSTES' in config and config['AJUSTES']['analise_medias'] == 'S' else False)
        tipo_par = st.selectbox("Tipo de Par", ["Automático (Todos os Pares)", "Automático (Prioriza OTC)", "Apenas OTC", "Apenas Normais"],
                                  index=0 if not config or 'AJUSTES' not in config or 'tipo_par' not in config['AJUSTES'] else ["Automático (Todos os Pares)", "Automático (Prioriza OTC)", "Apenas OTC", "Apenas Normais"].index(
                                      config['AJUSTES']['tipo_par'] if config['AJUSTES']['tipo_par'] in ["Automático (Todos os Pares)", "Automático (Prioriza OTC)", "Apenas OTC", "Apenas Normais"] else "Automático (Todos os Pares)"))
    with st.expander("Configurações de Martingale", expanded=False):
        mg_nivel_config = 2
        mg_fator_config = 2.0
        if config and 'MARTINGALE' in config:
            if 'niveis' in config['MARTINGALE']:
                try:
                    mg_nivel_config = max(1, int(config['MARTINGALE']['niveis']))
                except (ValueError, TypeError):
                    mg_nivel_config = 2
            if 'fator' in config['MARTINGALE']:
                try:
                    mg_fator_config = max(1.0, float(config['MARTINGALE']['fator']))
                except (ValueError, TypeError):
                    mg_fator_config = 2.0
        usar_martingale = st.checkbox("Usar Martingale", value=True if config and 'MARTINGALE' in config and config['MARTINGALE']['usar'] == 'S' else False)
        if usar_martingale:
            col1, col2 = st.columns(2)
            with col1:
                niveis_martingale = st.number_input("Níveis", min_value=1, max_value=5, value=mg_nivel_config, step=1)
            with col2:
                fator_martingale = st.number_input("Fator", min_value=1.0, max_value=5.0, value=mg_fator_config, step=0.1)
        else:
            niveis_martingale = 1
            fator_martingale = 1.0
    with st.expander("Configurações de Soros", expanded=False):
        soros_nivel_config = 2
        if config and 'SOROS' in config and 'niveis' in config['SOROS']:
            try:
                soros_nivel_config = max(1, int(config['SOROS']['niveis']))
            except (ValueError, TypeError):
                soros_nivel_config = 2
        usar_soros = st.checkbox("Usar Soros", value=True if config and 'SOROS' in config and config['SOROS']['usar'] == 'S' else False)
        if usar_soros:
            niveis_soros = st.number_input("Níveis de Soros", min_value=1, max_value=5, value=soros_nivel_config, step=1)
        else:
            niveis_soros = 1
    if st.button("Salvar Configurações", use_container_width=True):
        config_data = {
            'email': email,
            'senha': senha,
            'tipo': tipo,
            'valor_entrada': valor_entrada,
            'stop_win': stop_win,
            'stop_loss': stop_loss,
            'analise_medias': analise_medias,
            'velas_medias': velas_medias,
            'tipo_par': tipo_par,
            'usar_martingale': usar_martingale,
            'niveis_martingale': niveis_martingale,
            'fator_martingale': fator_martingale,
            'usar_soros': usar_soros,
            'niveis_soros': niveis_soros
        }
        if save_config(config_data):
            st.success("Configurações salvas com sucesso!")
        else:
            st.error("Erro ao salvar configurações!")

# Seção 1: Conectar na IQ Option
st.markdown("<h2 class='sub-header'>1. Conectar na IQ Option</h2>", unsafe_allow_html=True)
with st.container():
    st.markdown("""
    <div class="card">
        <p>Conecte-se à sua conta IQ Option para iniciar as operações. Certifique-se de que suas credenciais estejam corretas.</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Conectar à IQ Option", use_container_width=True, key="btn_connect"):
        if not email or not senha:
            st.error("Por favor, preencha seu email e senha nas configurações!")
            log_message("Tentativa de conexão sem credenciais", "error")
        else:
            with st.spinner("Conectando à IQ Option..."):
                api = connect_iqoption(email, senha, conta)
                if api:
                    st.session_state.API = api
                    st.session_state.connected = True
                    st.success(f"Conectado com sucesso! Bem-vindo, {st.session_state.nome}!")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Saldo", f"{st.session_state.cifrao} {st.session_state.saldo:.2f}")
                    with col2:
                        st.metric("Tipo de Conta", conta)
                    with col3:
                        st.metric("Status", "Conectado", delta="Online")
                else:
                    st.error("Falha na conexão. Verifique suas credenciais e tente novamente.")

# Seção 2: Catalogar Ativos
if st.session_state.connected:
    st.markdown("<h2 class='sub-header'>2. Catalogar Ativos</h2>", unsafe_allow_html=True)
    with st.container():
        st.markdown("""
        <div class="card">
            <p>Execute o catalogador para identificar os melhores ativos e estratégias com base no histórico recente.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Executar Catalogador", use_container_width=True, key="btn_catalog"):
            with st.spinner("Catalogando ativos... Isso pode demorar alguns minutos."):
                catalog_results, line = run_catalogador(st.session_state.API)
                if catalog_results:
                    st.session_state.catalog_results = catalog_results
                    st.session_state.catalog_line = line
                    df = pd.DataFrame(catalog_results, columns=["Estratégia", "Par", "Win%", "Gale1%", "Gale2%"])
                    for col in ["Win%", "Gale1%", "Gale2%"]:
                        df[col] = df[col].apply(lambda x: f"{x:.2f}%")
                    st.dataframe(df, use_container_width=True)
                    best_strategy = catalog_results[0][0]
                    best_asset = catalog_results[0][1]
                    best_rate = catalog_results[0][line]
                    st.success(f"Melhor combinação: Estratégia {best_strategy} com o ativo {best_asset} - Taxa de acerto: {best_rate:.2f}%")
                    log_message(f"Catalogação concluída com {len(catalog_results)} estratégias. Melhor: {best_strategy}/{best_asset} com {best_rate:.2f}%", "success")
                else:
                    st.error("Falha na catalogação. Verifique o log para mais detalhes.")

# Seção 3: Escolher Estratégia e Ativo
if st.session_state.connected:
    st.markdown("<h2 class='sub-header'>3. Escolher Estratégia e Ativo</h2>", unsafe_allow_html=True)
    with st.container():
        st.markdown("""
        <div class="card">
            <p>Selecione a estratégia e o ativo para iniciar as operações. Você pode escolher manualmente ou usar os resultados do catalogador.</p>
        </div>
        """, unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            estrategia_options = ["MHI", "Torres Gêmeas", "MHI M5", "BB"]
            estrategia = st.selectbox("Selecione a Estratégia", estrategia_options, index=0)
        with col2:
            if "catalog_results" in st.session_state and st.session_state.catalog_results:
                asset_options = [item[1] for item in st.session_state.catalog_results]
                ativo = st.selectbox("Selecione o Ativo", asset_options, index=0)
            else:
                ativo = st.text_input("Digite o Ativo (ex: EURUSD, EURUSD-OTC)", value="EURUSD-OTC").upper()
        if ativo and st.button("Verificar Disponibilidade do Ativo", key="check_asset"):
            with st.spinner(f"Verificando disponibilidade de {ativo}..."):
                if check_asset_available(st.session_state.API, ativo):
                    payout = get_payout(st.session_state.API, ativo)
                    st.success(f"Ativo {ativo} está disponível! Payout atual: {payout:.2f}%")
                    log_message(f"Ativo {ativo} disponível com payout de {payout:.2f}%", "success")
                else:
                    st.error(f"Ativo {ativo} não está disponível para operações.")
                    log_message(f"Ativo {ativo} indisponível", "error")

# Seção 4: Iniciar Bot e Dashboard
if st.session_state.connected:
    st.markdown("<h2 class='sub-header'>4. Iniciar Bot e Dashboard</h2>", unsafe_allow_html=True)
    with st.container():
        st.markdown("""
        <div class="card">
            <p>Inicie o bot para começar as operações automatizadas. O dashboard mostrará os resultados em tempo real.</p>
        </div>
        """, unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if not st.session_state.bot_running:
                if st.button("Iniciar Bot", use_container_width=True, key="btn_start_bot"):
                    if not ativo:
                        st.error("Selecione um ativo antes de iniciar o bot!")
                    else:
                        if check_asset_available(st.session_state.API, ativo):
                            config_data = {
                                'tipo': tipo,
                                'valor_entrada': valor_entrada,
                                'stop_win': stop_win,
                                'stop_loss': stop_loss,
                                'analise_medias': analise_medias,
                                'velas_medias': velas_medias,
                                'tipo_par': tipo_par,
                                'usar_martingale': usar_martingale,
                                'niveis_martingale': niveis_martingale,
                                'fator_martingale': fator_martingale,
                                'usar_soros': usar_soros,
                                'niveis_soros': niveis_soros
                            }
                            bot_thread = threading.Thread(
                                target=run_trading_bot,
                                args=(st.session_state.API, estrategia, ativo, config_data),
                                daemon=True
                            )
                            bot_thread.start()
                            st.success(f"Bot iniciado com estratégia {estrategia} no ativo {ativo}!")
                        else:
                            st.error(f"Ativo {ativo} não está disponível para operações!")
        with col2:
            if st.session_state.bot_running:
                if st.button("Parar Bot", use_container_width=True, key="btn_stop_bot"):
                    st.session_state.stop_bot = True
                    st.warning("Solicitação para parar o bot enviada. Aguarde a conclusão da operação atual...")
    if st.session_state.bot_running or len(st.session_state.operations) > 0:
        st.markdown("<h3 class='sub-header'>Dashboard de Resultados</h3>", unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Lucro/Prejuízo", f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {st.session_state.lucro_total:.2f}", delta=f"{st.session_state.lucro_total:.2f}")
        with col2:
            taxa_acerto = (st.session_state.wins / st.session_state.total_ops * 100) if st.session_state.total_ops > 0 else 0
            st.metric("Taxa de Acerto", f"{taxa_acerto:.2f}%", delta=f"{st.session_state.wins} ganhos / {st.session_state.losses} perdas")
        with col3:
            st.metric("Stop Win", f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {stop_win}", delta=f"{(st.session_state.lucro_total/stop_win)*100:.1f}%" if stop_win > 0 else None)
        with col4:
            st.metric("Stop Loss", f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {stop_loss}", delta=f"{(st.session_state.lucro_total/(-stop_loss))*100:.1f}%" if stop_loss > 0 else None)
        if len(st.session_state.operations) > 0:
            df_ops = pd.DataFrame(st.session_state.operations)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(range(1, len(df_ops) + 1)),
                y=df_ops['lucro_acumulado'],
                mode='lines+markers',
                name='Lucro Acumulado',
                line=dict(color='#00bfff', width=3),
                marker=dict(
                    size=8,
                    color=df_ops['lucro'].apply(lambda x: '#28a745' if x > 0 else '#dc3545' if x < 0 else '#ffc107'),
                    line=dict(width=2, color='#E0E0E0')
                )
            ))
            fig.add_shape(
                type="line",
                x0=0,
                y0=0,
                x1=len(df_ops) + 1,
                y1=0,
                line=dict(color="#3D3D60", width=1, dash="dash"),
            )
            fig.update_layout(
                title="Evolução do Lucro",
                xaxis_title="Operação",
                yaxis_title="Lucro Acumulado",
                height=300,
                margin=dict(l=10, r=10, t=40, b=10),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#E0E0E0'),
                xaxis=dict(gridcolor='#3D3D60'),
                yaxis=dict(gridcolor='#3D3D60')
            )
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("<p style='margin-top: 20px; font-weight: bold;'>Histórico de Operações:</p>", unsafe_allow_html=True)
            df_display = df_ops.copy()
            df_display['resultado'] = df_display['resultado'].apply(lambda x: "✅ WIN" if x == "win" else "❌ LOSS")
            df_display['lucro'] = df_display.apply(lambda x: f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {x['lucro']:.2f}", axis=1)
            df_display['lucro_acumulado'] = df_display.apply(lambda x: f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {x['lucro_acumulado']:.2f}", axis=1)
            df_display = df_display.rename(columns={
                'timestamp': 'Horário',
                'ativo': 'Ativo',
                'direcao': 'Direção',
                'valor': 'Valor',
                'resultado': 'Resultado',
                'lucro': 'Lucro',
                'lucro_acumulado': 'Acumulado'
            })
            st.dataframe(df_display, use_container_width=True)
        log_html = ""
        for msg in st.session_state.log_messages:
            log_html += f"{msg}<br>"
        st.markdown(f"""
        <div class="log-container">
            {log_html}
        </div>
        """, unsafe_allow_html=True)

st.markdown("""
<div style="text-align: center; margin-top: 30px; opacity: 0.7;">
    <p>Bot Trader IQ Option v1.0 | 2025</p>
</div>
""", unsafe_allow_html=True)
