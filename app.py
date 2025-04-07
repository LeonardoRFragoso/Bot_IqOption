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
from catalogador import catag, obter_pares_abertos

# Implementação das funções auxiliares para a estratégia BB
def detecta_pinbar(candle):
    """
    Detecta padrão Pinbar em um candle.
    Um Pinbar tem um corpo pequeno e uma sombra longa em uma direção.
    """
    open_price = candle['open']
    close_price = candle['close']
    high_price = candle['max']
    low_price = candle['min']
    
    corpo = abs(close_price - open_price)
    tamanho_total = high_price - low_price
    
    # Evitar divisão por zero
    if tamanho_total == 0:
        return False
    
    # Corpo deve ser pequeno (menos de 30% do tamanho total)
    if corpo / tamanho_total > 0.3:
        return False
    
    # Verificar se tem uma sombra longa
    if close_price > open_price:  # Candle de alta
        sombra_inferior = open_price - low_price
        return sombra_inferior / tamanho_total > 0.6
    else:  # Candle de baixa
        sombra_superior = high_price - open_price
        return sombra_superior / tamanho_total > 0.6

def detecta_engolfo(candle_atual, candle_anterior):
    """
    Detecta padrão de Engolfo entre dois candles consecutivos.
    Um Engolfo ocorre quando o corpo do candle atual "engole" completamente o corpo do candle anterior.
    """
    # Corpo do candle atual
    corpo_atual = abs(candle_atual['close'] - candle_atual['open'])
    # Corpo do candle anterior
    corpo_anterior = abs(candle_anterior['close'] - candle_anterior['open'])
    
    # Verificar se o corpo atual é maior que o anterior
    if corpo_atual <= corpo_anterior:
        return False
    
    # Verificar se há engolfo de alta
    if candle_atual['close'] > candle_atual['open']:  # Candle atual de alta
        if candle_anterior['close'] < candle_anterior['open']:  # Candle anterior de baixa
            return (candle_atual['open'] <= candle_anterior['close'] and 
                   candle_atual['close'] >= candle_anterior['open'])
    
    # Verificar se há engolfo de baixa
    if candle_atual['close'] < candle_atual['open']:  # Candle atual de baixa
        if candle_anterior['close'] > candle_anterior['open']:  # Candle anterior de alta
            return (candle_atual['open'] >= candle_anterior['close'] and 
                   candle_atual['close'] <= candle_anterior['open'])
    
    return False

def detecta_zona_sr(candles, num=10):
    """
    Detecta zonas de suporte e resistência baseadas nos últimos candles.
    Retorna True se o último candle estiver próximo a uma zona S/R.
    """
    if len(candles) < num:
        return False
    
    # Pegar os últimos N candles para análise
    ultimos_candles = candles[-num:]
    
    # Encontrar máximos e mínimos locais
    maximos = [c['max'] for c in ultimos_candles]
    minimos = [c['min'] for c in ultimos_candles]
    
    # Calcular médias para identificar zonas
    media_max = sum(maximos) / len(maximos)
    media_min = sum(minimos) / len(minimos)
    
    # Último candle
    ultimo_candle = candles[-1]
    preco_atual = ultimo_candle['close']
    
    # Definir margem de proximidade (2% do preço)
    margem = preco_atual * 0.02
    
    # Verificar se o preço atual está próximo a uma zona S/R
    return (abs(preco_atual - media_max) < margem or 
            abs(preco_atual - media_min) < margem)

def detecta_fibo(candles, num=10):
    """
    Calcula os níveis de Fibonacci com base nos últimos candles.
    Retorna um dicionário com os níveis calculados.
    """
    if len(candles) < num:
        return {}
    
    # Pegar os últimos N candles para análise
    ultimos_candles = candles[-num:]
    
    # Encontrar máximo e mínimo no período
    maxima = max([c['max'] for c in ultimos_candles])
    minima = min([c['min'] for c in ultimos_candles])
    
    # Calcular a amplitude do movimento
    amplitude = maxima - minima
    
    # Calcular níveis de Fibonacci
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
    """
    Valida a tendência macro do ativo usando médias móveis de longo prazo.
    Retorna True se a tendência for considerada estável.
    """
    try:
        # Obter candles para análise de tendência
        timestamp_atual = time.time()
        candles = api.get_candles(ativo, timeframe, num_candles, timestamp_atual)
        
        if candles is None or len(candles) < 50:
            log_message("Dados insuficientes para análise de tendência macro", "warning")
            return True  # Por padrão, permitimos a operação
        
        # Calcular médias móveis
        closes = [candle['close'] for candle in candles]
        
        # Média móvel de 20 períodos
        ma20 = sum(closes[-20:]) / 20
        # Média móvel de 50 períodos
        ma50 = sum(closes[-50:]) / 50
        
        # Verificar se o preço atual está acima das médias (tendência de alta)
        preco_atual = closes[-1]
        tendencia_alta = preco_atual > ma20 and ma20 > ma50
        
        # Verificar se o preço atual está abaixo das médias (tendência de baixa)
        tendencia_baixa = preco_atual < ma20 and ma20 < ma50
        
        # Verificar a volatilidade (desvio padrão dos últimos 20 períodos)
        desvio_padrao = (sum([(close - ma20) ** 2 for close in closes[-20:]]) / 20) ** 0.5
        volatilidade_normal = desvio_padrao / ma20 < 0.03  # 3% é considerado normal
        
        # Retorna True se temos uma tendência clara e volatilidade normal
        return (tendencia_alta or tendencia_baixa) and volatilidade_normal
        
    except Exception as e:
        log_message(f"Erro ao validar tendência macro: {str(e)}", "error")
        return True  # Em caso de erro, permitimos a operação

def log_auditoria(mensagem, ativo, estrategia):
    """
    Registra informações de auditoria em um arquivo CSV.
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("auditoria_sinais.csv", "a") as arquivo:
            # Se o arquivo estiver vazio, adicionar cabeçalho
            if arquivo.tell() == 0:
                arquivo.write("Timestamp,Ativo,Estrategia,Mensagem\n")
            arquivo.write(f"{timestamp},{ativo},{estrategia},{mensagem}\n")
    except Exception as e:
        log_message(f"Erro ao registrar auditoria: {str(e)}", "error")

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_log.txt"),
        logging.StreamHandler()
    ]
)

# Configuração da página
st.set_page_config(
    page_title="Bot IQ Option Trader",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS personalizado
st.markdown("""
<style>
    /* Tema escuro personalizado */
    .stApp {
        background: linear-gradient(to bottom, #1E1E2E, #2D2D44);
        color: #E0E0E0;
    }
    
    /* Cabeçalhos */
    .main-header {
        font-size: 2.5rem;
        background: linear-gradient(90deg, #0078ff, #00bfff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 1.5rem;
        font-weight: 700;
    }
    
    .sub-header {
        font-size: 1.8rem;
        background: linear-gradient(90deg, #0078ff, #00bfff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-top: 1.5rem;
        font-weight: 600;
    }
    
    /* Mensagens */
    .success-message {
        color: #28a745;
        font-weight: bold;
    }
    
    .error-message {
        color: #dc3545;
        font-weight: bold;
    }
    
    .info-message {
        color: #17a2b8;
        font-weight: bold;
    }
    
    /* Cards */
    .card {
        background-color: rgba(45, 45, 68, 0.7);
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #3D3D60;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    /* Log container */
    .log-container {
        background-color: rgba(30, 30, 46, 0.7);
        border-radius: 5px;
        padding: 10px;
        height: 300px;
        overflow-y: auto;
        font-family: monospace;
        border: 1px solid #3D3D60;
    }
</style>
""", unsafe_allow_html=True)

# Inicialização de variáveis de estado da sessão
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

# Título principal
st.markdown("<h1 class='main-header'>Bot Trader IQ Option</h1>", unsafe_allow_html=True)

# Função para adicionar mensagens ao log
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

# Função para carregar configurações com tratamento de erros
def load_config():
    try:
        if os.path.exists('config.txt'):
            config = ConfigObj('config.txt', encoding='utf-8')
            log_message("Configurações carregadas com sucesso")
            return config
        else:
            log_message("Arquivo de configuração não encontrado. Criando novo...", "warning")
            config = ConfigObj()
            config.filename = 'config.txt'
            
            # Estrutura padrão de configuração
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
            return config
    except Exception as e:
        log_message(f"Erro ao carregar configurações: {str(e)}", "error")
        return None

# Função para salvar configurações
def save_config(config_data):
    try:
        config = ConfigObj()
        
        # Atualiza as configurações
        config['LOGIN'] = {
            'email': config_data['email'],
            'senha': config_data['senha']
        }
        
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
        
        # Salva o arquivo
        config.filename = 'config.txt'
        config.write()
        
        log_message("Configurações salvas com sucesso", "success")
        return True
    except Exception as e:
        log_message(f"Erro ao salvar configurações: {str(e)}", "error")
        return False

# Função para conectar à IQ Option
def connect_iqoption(email, senha, conta):
    try:
        log_message(f"Iniciando conexão com a IQ Option... Tipo de conta selecionada: {conta}")
        api = IQ_Option(email, senha)
        
        # Tenta conectar com retry
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
                    time.sleep(2)  # Aguarda 2 segundos antes de tentar novamente
            except Exception as e:
                retry_count += 1
                log_message(f"Erro na tentativa {retry_count}/{max_retries}: {str(e)}", "warning")
                time.sleep(2)
        
        if not connected:
            log_message("Todas as tentativas de conexão falharam", "error")
            return None
        
        # Seleciona a conta (demo ou real)
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
            # Tenta novamente com um fallback para PRACTICE
            try:
                api.change_balance("PRACTICE")
                log_message("Fallback para conta DEMO realizado", "warning")
            except:
                log_message("Não foi possível selecionar nenhum tipo de conta", "error")
                return None
        
        # Obtém informações do perfil
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

# Função para verificar se o ativo está disponível
def check_asset_available(api, asset, option_type="binary"):
    try:
        if option_type == "digital":
            asset_list = api.get_digital_underlying()
        else:  # binary
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

# Função para obter payout
def get_payout(api, asset, option_type="binary"):
    try:
        if option_type == "digital":
            return api.get_digital_payout(asset)
        else:
            return api.get_all_profit()[asset]["binary"] * 100
    except Exception as e:
        log_message(f"Erro ao obter payout: {str(e)}", "error")
        return 0

# Função para executar o catalogador
def run_catalogador(api):
    try:
        log_message("Iniciando catalogação de ativos...", "info")
        
        # Carrega as configurações
        config = load_config()
        tipo_par = "Automático (Prioriza OTC)"
        if config and 'AJUSTES' in config and 'tipo_par' in config['AJUSTES']:
            tipo_par = config['AJUSTES']['tipo_par']
        
        # Executa o catalogador
        resultados, linha = catag(api, tipo_par)
        
        if not resultados or len(resultados) == 0:
            log_message("Nenhum resultado obtido na catalogação. Verifique se há pares disponíveis.", "error")
            return None, 0
            
        st.session_state.catalog_results = resultados
        st.session_state.catalog_line = linha
        
        log_message(f"Catalogação concluída. Encontrados {len(resultados)} resultados.", "success")
        return resultados, linha
    except Exception as e:
        log_message(f"Erro ao executar catalogação: {str(e)}", "error")
        return None, 0

# Função para executar o bot de trading
def run_trading_bot(api, estrategia, ativo, config_data):
    try:
        # Inicializa variáveis
        st.session_state.bot_running = True
        st.session_state.stop_bot = False
        st.session_state.lucro_total = 0
        st.session_state.wins = 0
        st.session_state.losses = 0
        st.session_state.total_ops = 0
        
        # Carrega configurações
        tipo = config_data['tipo']
        valor_entrada = float(config_data['valor_entrada'])
        stop_win = float(config_data['stop_win'])
        stop_loss = float(config_data['stop_loss'])
        analise_medias = config_data['analise_medias']
        velas_medias = int(config_data['velas_medias'])
        tipo_par = config_data['tipo_par']
        
        # Configurações de Martingale
        usar_martingale = config_data['usar_martingale']
        if usar_martingale:
            martingale = int(config_data['niveis_martingale'])
            fator_mg = float(config_data['fator_martingale'])
        else:
            # Garante que os valores sejam zero quando não estiver usando martingale
            martingale = 0
            fator_mg = 0
        
        # Configurações de Soros
        usar_soros = config_data['usar_soros']
        if usar_soros:
            soros = True
            niveis_soros = int(config_data['niveis_soros'])
            nivel_soros = 0
        else:
            # Garante que os valores sejam zero quando não estiver usando soros
            soros = False
            niveis_soros = 0
            nivel_soros = 0
        
        valor_soros = 0
        lucro_op_atual = 0
        
        # Função para obter horário atual
        def horario():
            return datetime.now().strftime('%H:%M:%S')
        
        # Função para calcular médias móveis
        def medias(velas):
            soma = 0
            for vela in velas:
                soma += vela['close']
            media = soma / len(velas)
            
            if velas[-1]['close'] > media:
                return 'call'
            else:
                return 'put'
        
        # Função para verificar stop win/loss
        def check_stop():
            if st.session_state.lucro_total >= stop_win:
                log_message(f"STOP WIN ATINGIDO! Lucro: {st.session_state.cifrao} {st.session_state.lucro_total:.2f}", "success")
                return False
            
            if st.session_state.lucro_total <= -stop_loss:
                log_message(f"STOP LOSS ATINGIDO! Prejuízo: {st.session_state.cifrao} {st.session_state.lucro_total:.2f}", "error")
                return False
            
            if st.session_state.stop_bot:
                log_message("Bot parado manualmente pelo usuário", "warning")
                return False
            
            return True
        
        # Função para obter payout
        def payout(par):
            try:
                if tipo == 'digital':
                    api.subscribe_strike_list(par, 1)
                    time.sleep(0.5)
                    data = api.get_digital_current_profit(par, 1)
                    api.unsubscribe_strike_list(par, 1)
                    return data
                else:
                    return api.get_all_profit()[par]['binary'] * 100
            except Exception as e:
                log_message(f"Erro ao obter payout: {str(e)}", "error")
                return 0
        
        # Função para realizar compra
        def compra(ativo, valor_entrada, direcao, exp, tipo_op):
            try:
                log_message(f"Iniciando operação: {ativo} / {direcao.upper()} / {valor_entrada} / {exp} min", "operation")
                
                # Verifica o tipo de operação
                if tipo_op == 'automatico':
                    payout_digital = api.get_digital_payout(ativo)
                    payout_binario = api.get_all_profit()[ativo]['binary'] * 100
                    
                    if payout_digital > payout_binario:
                        tipo_op = 'digital'
                    else:
                        tipo_op = 'binary'
                
                # Realiza a compra
                if tipo_op == 'binary':
                    status, id = api.buy(valor_entrada, ativo, direcao, exp)
                else:
                    status, id = api.buy_digital_spot(ativo, valor_entrada, direcao, exp)
                
                if status:
                    log_message(f"Ordem executada com sucesso! ID: {id}", "success")
                    
                    # Aguarda o resultado
                    if tipo_op == 'binary':
                        resultado, lucro = api.check_win_v3(id)
                    else:
                        while True:
                            status, lucro = api.check_win_digital_v2(id)
                            if status:
                                resultado = "win" if lucro > 0 else "loss"
                                break
                            time.sleep(0.5)
                    
                    # Atualiza estatísticas
                    st.session_state.lucro_total += lucro
                    st.session_state.total_ops += 1
                    
                    # Registra operação
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    operation = {
                        "timestamp": timestamp,
                        "ativo": ativo,
                        "direcao": direcao,
                        "valor": valor_entrada,
                        "resultado": resultado,
                        "lucro": lucro,
                        "lucro_acumulado": st.session_state.lucro_total
                    }
                    st.session_state.operations.append(operation)
                    
                    # Exibe resultado
                    if resultado == "win":
                        st.session_state.wins += 1
                        log_message(f"WIN! Lucro: {st.session_state.cifrao} {lucro:.2f}", "success")
                        return True, lucro
                    else:
                        st.session_state.losses += 1
                        log_message(f"LOSS! Prejuízo: {st.session_state.cifrao} {lucro:.2f}", "error")
                        return False, lucro
                else:
                    log_message(f"Erro ao executar ordem: {id}", "error")
                    return False, 0
            except Exception as e:
                log_message(f"Exceção na compra: {str(e)}", "error")
                return False, 0
        
        # Loop principal do bot
        log_message(f"Iniciando bot com estratégia {estrategia} no ativo {ativo}", "info")
        log_message(f"Stop Win: {st.session_state.cifrao} {stop_win} | Stop Loss: {st.session_state.cifrao} {stop_loss}", "info")
        
        # Executa a estratégia selecionada
        while check_stop():
            try:
                # Estratégia MHI
                if estrategia == "MHI":
                    # Verifica se está próximo do horário de entrada (minutos múltiplos de 5)
                    minuto_atual = int(datetime.now().strftime('%M'))
                    segundo_atual = int(datetime.now().strftime('%S'))
                    
                    # Aguarda o momento ideal para entrar (segundos finais do minuto anterior)
                    if minuto_atual % 5 == 4 and segundo_atual >= 55:
                        log_message("Preparando entrada para MHI...", "info")
                        
                        # Obtém as velas
                        timeframe = 60  # 1 minuto
                        qnt_velas = 3
                        
                        if analise_medias:
                            velas_data = api.get_candles(ativo, timeframe, velas_medias, time.time())
                            tendencia = medias(velas_data)
                            log_message(f"Análise de tendência: {tendencia.upper()}", "info")
                        
                        velas_data = api.get_candles(ativo, timeframe, qnt_velas, time.time())
                        
                        # Analisa as velas
                        vela1 = 'Verde' if velas_data[0]['open'] < velas_data[0]['close'] else 'Vermelha'
                        vela2 = 'Verde' if velas_data[1]['open'] < velas_data[1]['close'] else 'Vermelha'
                        vela3 = 'Verde' if velas_data[2]['open'] < velas_data[2]['close'] else 'Vermelha'
                        
                        cores = [vela1, vela2, vela3]
                        log_message(f"Velas analisadas: {vela1}, {vela2}, {vela3}", "info")
                        
                        # Define a direção
                        direcao = None
                        if cores.count('Verde') > cores.count('Vermelha') and 'Doji' not in cores:
                            direcao = 'put'
                        elif cores.count('Verde') < cores.count('Vermelha') and 'Doji' not in cores:
                            direcao = 'call'
                        
                        # Verifica se a direção está de acordo com a tendência
                        if analise_medias and direcao and direcao != tendencia:
                            log_message("Entrada abortada - Contra tendência", "warning")
                            direcao = None
                        
                        # Executa a operação
                        if direcao:
                            log_message(f"Sinal identificado: {direcao.upper()}", "info")
                            
                            # Executa a entrada
                            win, lucro = compra(ativo, valor_entrada, direcao, 1, tipo)
                            
                            # Gerencia martingale se necessário
                            if not win and martingale > 0:
                                valor_mg = valor_entrada
                                
                                for i in range(martingale):
                                    log_message(f"Iniciando martingale nível {i+1}", "warning")
                                    valor_mg = valor_mg * fator_mg
                                    
                                    win_mg, lucro_mg = compra(ativo, valor_mg, direcao, 1, tipo)
                                    
                                    if win_mg:
                                        log_message(f"Martingale {i+1} recuperou operação!", "success")
                                        break
                                    
                                    if i == martingale - 1:
                                        log_message("Todos os níveis de martingale perdidos", "error")
                            
                            # Aguarda para próxima operação
                            time.sleep(60)
                        else:
                            log_message("Sem sinal válido para entrada", "warning")
                            time.sleep(5)
                    else:
                        # Aguarda o momento certo
                        time.sleep(1)
                
                # Estratégia Torres Gêmeas
                elif estrategia == "Torres Gêmeas":
                    # Verifica se está próximo do horário de entrada (minutos terminados em 4 ou 9)
                    minuto_atual = int(datetime.now().strftime('%M'))
                    segundo_atual = int(datetime.now().strftime('%S'))
                    
                    # Aguarda o momento ideal para entrar
                    if (minuto_atual % 5 == 4) and segundo_atual >= 55:
                        log_message("Preparando entrada para Torres Gêmeas...", "info")
                        
                        # Obtém as velas
                        timeframe = 60  # 1 minuto
                        
                        if analise_medias:
                            velas_data = api.get_candles(ativo, timeframe, velas_medias, time.time())
                            tendencia = medias(velas_data)
                            log_message(f"Análise de tendência: {tendencia.upper()}", "info")
                        
                        velas_data = api.get_candles(ativo, timeframe, 5, time.time())
                        
                        # Analisa a vela de referência (primeira vela)
                        vela_ref = 'Verde' if velas_data[0]['open'] < velas_data[0]['close'] else 'Vermelha'
                        log_message(f"Vela de referência: {vela_ref}", "info")
                        
                        # Define a direção (contrária à vela de referência)
                        direcao = 'put' if vela_ref == 'Verde' else 'call'
                        
                        # Verifica se a direção está de acordo com a tendência
                        if analise_medias and direcao != tendencia:
                            log_message("Entrada abortada - Contra tendência", "warning")
                        else:
                            log_message(f"Sinal identificado: {direcao.upper()}", "info")
                            
                            # Executa a entrada
                            win, lucro = compra(ativo, valor_entrada, direcao, 1, tipo)
                            
                            # Gerencia martingale se necessário
                            if not win and martingale > 0:
                                valor_mg = valor_entrada
                                
                                for i in range(martingale):
                                    log_message(f"Iniciando martingale nível {i+1}", "warning")
                                    valor_mg = valor_mg * fator_mg
                                    
                                    win_mg, lucro_mg = compra(ativo, valor_mg, direcao, 1, tipo)
                                    
                                    if win_mg:
                                        log_message(f"Martingale {i+1} recuperou operação!", "success")
                                        break
                                    
                                    if i == martingale - 1:
                                        log_message("Todos os níveis de martingale perdidos", "error")
                        
                        # Aguarda para próxima operação
                        time.sleep(60)
                    else:
                        # Aguarda o momento certo
                        time.sleep(1)
                
                # Estratégia MHI M5
                elif estrategia == "MHI M5":
                    # Verifica se está próximo do horário de entrada (minutos 0 ou 30)
                    minuto_atual = int(datetime.now().strftime('%M'))
                    segundo_atual = int(datetime.now().strftime('%S'))
                    
                    # Aguarda o momento ideal para entrar
                    if (minuto_atual == 29 or minuto_atual == 59) and segundo_atual >= 55:
                        log_message("Preparando entrada para MHI M5...", "info")
                        
                        # Obtém as velas
                        timeframe = 300  # 5 minutos
                        qnt_velas = 3
                        
                        if analise_medias:
                            velas_data = api.get_candles(ativo, timeframe, velas_medias, time.time())
                            tendencia = medias(velas_data)
                            log_message(f"Análise de tendência: {tendencia.upper()}", "info")
                        
                        velas_data = api.get_candles(ativo, timeframe, qnt_velas, time.time())
                        
                        # Analisa as velas
                        vela1 = 'Verde' if velas_data[0]['open'] < velas_data[0]['close'] else 'Vermelha'
                        vela2 = 'Verde' if velas_data[1]['open'] < velas_data[1]['close'] else 'Vermelha'
                        vela3 = 'Verde' if velas_data[2]['open'] < velas_data[2]['close'] else 'Vermelha'
                        
                        cores = [vela1, vela2, vela3]
                        log_message(f"Velas analisadas: {vela1}, {vela2}, {vela3}", "info")
                        
                        # Define a direção
                        direcao = None
                        if cores.count('Verde') > cores.count('Vermelha') and 'Doji' not in cores:
                            direcao = 'put'
                        elif cores.count('Verde') < cores.count('Vermelha') and 'Doji' not in cores:
                            direcao = 'call'
                        
                        # Verifica se a direção está de acordo com a tendência
                        if analise_medias and direcao and direcao != tendencia:
                            log_message("Entrada abortada - Contra tendência", "warning")
                            direcao = None
                        
                        # Executa a operação
                        if direcao:
                            log_message(f"Sinal identificado: {direcao.upper()}", "info")
                            
                            # Executa a entrada
                            win, lucro = compra(ativo, valor_entrada, direcao, 5, tipo)
                            
                            # Gerencia martingale se necessário
                            if not win and martingale > 0:
                                valor_mg = valor_entrada
                                
                                for i in range(martingale):
                                    log_message(f"Iniciando martingale nível {i+1}", "warning")
                                    valor_mg = valor_mg * fator_mg
                                    
                                    win_mg, lucro_mg = compra(ativo, valor_mg, direcao, 5, tipo)
                                    
                                    if win_mg:
                                        log_message(f"Martingale {i+1} recuperou operação!", "success")
                                        break
                                    
                                    if i == martingale - 1:
                                        log_message("Todos os níveis de martingale perdidos", "error")
                            
                            # Aguarda para próxima operação
                            time.sleep(300)
                        else:
                            log_message("Sem sinal válido para entrada", "warning")
                            time.sleep(5)
                    else:
                        # Aguarda o momento certo
                        time.sleep(1)
                
                # Estratégia BB
                elif estrategia == "BB":
                    # Verifica se está no momento correto para análise (minuto divisível por 5 e segundos entre 0 e 4)
                    agora = datetime.fromtimestamp(api.get_server_timestamp())
                    minuto = agora.minute
                    segundo = agora.second
                    
                    # Para M5, disparamos a análise quando o minuto é divisível por 5 e os segundos estão entre 0 e 4
                    if (minuto % 5 == 0) and (segundo < 5):
                        log_message("Iniciando análise da estratégia BB (M5)", "info")
                        
                        # Valida tendência macro antes de operar
                        if not valida_tendencia_macro(api, ativo):
                            log_message("Tendência macro não confirmada, operação abortada.", "warning")
                            time.sleep(5)
                            continue

                        # Obtém os candles para análise
                        timeframe = 300            # M5: 300 segundos
                        quantidade_candles = 60
                        timestamp_atual = time.time()
                        candles = api.get_candles(ativo, timeframe, quantidade_candles, timestamp_atual)
                        
                        if candles is None or len(candles) < 50:
                            log_message("Número insuficiente de candles para análise BB", "error")
                            time.sleep(5)
                            continue

                        # Cálculo da média BB50
                        closes = [candle['close'] for candle in candles]
                        media_50 = sum(closes[-50:]) / 50

                        # Seleciona a última candle e a penúltima para análise
                        ultima_candle = candles[-1]
                        penultima_candle = candles[-2]

                        open_last = ultima_candle['open']
                        close_last = ultima_candle['close']
                        high_last = ultima_candle['max']
                        low_last = ultima_candle['min']
                        corpo_last = abs(close_last - open_last)
                        tamanho_last = high_last - low_last if (high_last - low_last) != 0 else 1
                        candle_forca = (corpo_last / tamanho_last) > 0.6

                        # Logs detalhados para auditoria
                        log_message(f"Fechamento: {close_last}, Média BB50: {media_50}", "info")
                        log_message(f"Candle atual: open={open_last}, close={close_last}, high={high_last}, low={low_last}", "info")
                        log_message(f"Candle de força? {'Sim' if candle_forca else 'Não'}", "info")

                        # Detecta padrões de reversão
                        sinal_pinbar = detecta_pinbar(ultima_candle)
                        sinal_engolfo = detecta_engolfo(ultima_candle, penultima_candle)
                        zona_sr = detecta_zona_sr(candles)
                        fibo_levels = detecta_fibo(candles, num=10)

                        direcao = None
                        sinal_info = ""
                        
                        # Lógica: se candle de força e fechamento em relação à média BB50
                        if candle_forca:
                            if close_last < media_50:
                                direcao = "call"
                                sinal_info = "Reversão para alta detectada: candle de força com fechamento abaixo da média BB50."
                            elif close_last > media_50:
                                direcao = "put"
                                sinal_info = "Reversão para baixa detectada: candle de força com fechamento acima da média BB50."

                        if sinal_pinbar:
                            sinal_info += " Padrão Pinbar identificado."
                            log_message("Padrão Pinbar identificado", "info")
                        if sinal_engolfo:
                            sinal_info += " Padrão Engolfo identificado."
                            log_message("Padrão Engolfo identificado", "info")
                        if zona_sr:
                            sinal_info += " Zona de suporte/resistência validada."
                            log_message("Zona de suporte/resistência validada", "info")

                        # Exibe níveis de Fibonacci
                        log_message(f"Níveis Fibonacci calculados: {fibo_levels}", "info")
                        
                        if direcao is not None:
                            log_message(f"Sinal: {sinal_info}", "operation")
                            log_auditoria(sinal_info, ativo, "BB")
                            
                            # Para M5, passamos expiração de 5 minutos
                            win, lucro = compra(ativo, valor_entrada, direcao, 5, tipo_op)
                            
                            # Gerencia martingale se necessário
                            if not win and martingale > 0:
                                valor_mg = valor_entrada
                                
                                for i in range(martingale):
                                    log_message(f"Iniciando martingale nível {i+1}", "warning")
                                    valor_mg = valor_mg * fator_mg
                                    
                                    win_mg, lucro_mg = compra(ativo, valor_mg, direcao, 5, tipo_op)
                                    
                                    if win_mg:
                                        log_message(f"Martingale {i+1} recuperou operação!", "success")
                                        break
                                    
                                    if i == martingale - 1:
                                        log_message("Todos os níveis de martingale perdidos", "error")
                        else:
                            log_message("Nenhum sinal acionado no momento.", "warning")

                        # Aguarda para próxima análise
                        time.sleep(5)
                    else:
                        # Aguarda o momento certo
                        time.sleep(0.5)
            
            except Exception as e:
                log_message(f"Erro na execução do bot: {str(e)}", "error")
                time.sleep(5)
        
        # Finaliza o bot
        st.session_state.bot_running = False
        log_message("Bot finalizado", "info")
        
    except Exception as e:
        st.session_state.bot_running = False
        log_message(f"Exceção geral no bot: {str(e)}", "error")

# Sidebar - Configurações e Login
with st.sidebar:
    st.markdown("<h3 class='sub-header'>Configurações</h3>", unsafe_allow_html=True)
    
    # Carrega configurações existentes
    config = load_config()
    
    # Seção de Login
    with st.expander("Credenciais IQ Option", expanded=True):
        email = st.text_input(
            "Email", 
            value=config['LOGIN']['email'] if config and 'LOGIN' in config else "", 
            placeholder="Seu email na IQ Option"
        )
        senha = st.text_input(
            "Senha", 
            value=config['LOGIN']['senha'] if config and 'LOGIN' in config else "", 
            type="password", 
            placeholder="Sua senha"
        )
        conta = st.selectbox(
            "Tipo de Conta", 
            ["Demo", "Real"], 
            index=0
        )
    
    # Seção de Configurações de Operação
    with st.expander("Configurações de Operação", expanded=True):
        tipo = st.selectbox(
            "Tipo de Operação", 
            ["binary", "digital", "automatico"], 
            index=0 if not config or 'AJUSTES' not in config else 
                  ["binary", "digital", "automatico"].index(config['AJUSTES']['tipo'])
        )
        
        col1, col2 = st.columns(2)
        with col1:
            # Validação do valor de entrada
            valor_entrada_config = 2.0  # Valor padrão
            if config and 'AJUSTES' in config and 'valor_entrada' in config['AJUSTES']:
                try:
                    valor_entrada_config = max(2.0, float(config['AJUSTES']['valor_entrada']))
                except (ValueError, TypeError):
                    valor_entrada_config = 2.0  # Em caso de erro, usa o valor padrão
                    
            valor_entrada = st.number_input(
                "Valor Entrada", 
                min_value=2.0, 
                value=valor_entrada_config,
                step=1.0
            )
        with col2:
            # Validação do número de velas para médias
            velas_medias_config = 20  # Valor padrão
            if config and 'AJUSTES' in config and 'velas_medias' in config['AJUSTES']:
                try:
                    velas_medias_config = max(3, int(config['AJUSTES']['velas_medias']))
                except (ValueError, TypeError):
                    velas_medias_config = 20  # Em caso de erro, usa o valor padrão
                    
            velas_medias = st.number_input(
                "Velas p/ Médias", 
                min_value=3, 
                value=velas_medias_config,
                step=1
            )
        
        col1, col2 = st.columns(2)
        with col1:
            # Validação do stop win
            stop_win_config = 15.0  # Valor padrão
            if config and 'AJUSTES' in config and 'stop_win' in config['AJUSTES']:
                try:
                    stop_win_config = max(1.0, float(config['AJUSTES']['stop_win']))
                except (ValueError, TypeError):
                    stop_win_config = 15.0  # Em caso de erro, usa o valor padrão
                    
            stop_win = st.number_input(
                "Stop Win", 
                min_value=1.0, 
                value=stop_win_config,
                step=1.0
            )
        with col2:
            # Validação do stop loss
            stop_loss_config = 15.0  # Valor padrão
            if config and 'AJUSTES' in config and 'stop_loss' in config['AJUSTES']:
                try:
                    stop_loss_config = max(1.0, float(config['AJUSTES']['stop_loss']))
                except (ValueError, TypeError):
                    stop_loss_config = 15.0  # Em caso de erro, usa o valor padrão
                    
            stop_loss = st.number_input(
                "Stop Loss", 
                min_value=1.0, 
                value=stop_loss_config,
                step=1.0
            )
        
        analise_medias = st.checkbox(
            "Usar Análise de Médias", 
            value=True if config and 'AJUSTES' in config and config['AJUSTES']['analise_medias'] == 'S' else False
        )
        
        tipo_par = st.selectbox(
            "Tipo de Par", 
            [
                "Automático (Prioriza OTC)", 
                "Apenas OTC", 
                "Apenas Normais"
            ], 
            index=0 if not config or 'AJUSTES' not in config or 'tipo_par' not in config['AJUSTES'] else 
                  [
                      "Automático (Prioriza OTC)", 
                      "Apenas OTC", 
                      "Apenas Normais"
                  ].index(config['AJUSTES']['tipo_par'])
        )
    
    # Seção de Martingale
    with st.expander("Configurações de Martingale", expanded=False):
        # Verifica se os valores na configuração são válidos
        mg_nivel_config = 2  # Valor padrão
        mg_fator_config = 2.0  # Valor padrão
        
        if config and 'MARTINGALE' in config:
            if 'niveis' in config['MARTINGALE']:
                try:
                    mg_nivel_config = max(1, int(config['MARTINGALE']['niveis']))
                except (ValueError, TypeError):
                    mg_nivel_config = 2  # Em caso de erro, usa o valor padrão
                    
            if 'fator' in config['MARTINGALE']:
                try:
                    mg_fator_config = max(1.0, float(config['MARTINGALE']['fator']))
                except (ValueError, TypeError):
                    mg_fator_config = 2.0  # Em caso de erro, usa o valor padrão
        
        usar_martingale = st.checkbox(
            "Usar Martingale", 
            value=True if config and 'MARTINGALE' in config and config['MARTINGALE']['usar'] == 'S' else False
        )
        
        if usar_martingale:
            col1, col2 = st.columns(2)
            with col1:
                niveis_martingale = st.number_input(
                    "Níveis", 
                    min_value=1, 
                    max_value=5, 
                    value=mg_nivel_config,
                    step=1
                )
            with col2:
                fator_martingale = st.number_input(
                    "Fator", 
                    min_value=1.0, 
                    max_value=5.0, 
                    value=mg_fator_config,
                    step=0.1
                )
        else:
            niveis_martingale = 1  # Valor padrão quando não está usando Martingale
            fator_martingale = 1.0  # Valor padrão quando não está usando Martingale
    
    # Seção de Soros
    with st.expander("Configurações de Soros", expanded=False):
        # Verifica se o valor de 'niveis' na configuração é válido (>= 1)
        soros_nivel_config = 2  # Valor padrão
        if config and 'SOROS' in config and 'niveis' in config['SOROS']:
            try:
                soros_nivel_config = max(1, int(config['SOROS']['niveis']))
            except (ValueError, TypeError):
                soros_nivel_config = 2  # Em caso de erro, usa o valor padrão
        
        usar_soros = st.checkbox(
            "Usar Soros", 
            value=True if config and 'SOROS' in config and config['SOROS']['usar'] == 'S' else False
        )
        
        if usar_soros:
            niveis_soros = st.number_input(
                "Níveis de Soros", 
                min_value=1, 
                max_value=5, 
                value=soros_nivel_config,
                step=1
            )
        else:
            niveis_soros = 1  # Valor padrão quando não está usando Soros
    
    # Botão para salvar configurações
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
                    
                    # Exibe informações da conta
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
                    
                    # Cria um DataFrame para exibir os resultados
                    df = pd.DataFrame(
                        catalog_results, 
                        columns=["Estratégia", "Ativo", "Win%", "Gale1%", "Gale2%"]
                    )
                    
                    # Formata as colunas de percentual
                    for col in ["Win%", "Gale1%", "Gale2%"]:
                        df[col] = df[col].apply(lambda x: f"{x:.2f}%")
                    
                    # Exibe o DataFrame
                    st.dataframe(df, use_container_width=True)
                    
                    # Destaca o melhor resultado
                    best_strategy = catalog_results[0][0]
                    best_asset = catalog_results[0][1]
                    best_rate = catalog_results[0][line]
                    
                    st.success(f"Melhor combinação: Estratégia {best_strategy} com o ativo {best_asset} - Taxa de acerto: {best_rate:.2f}%")
                    log_message(f"Catalogação concluída. Melhor resultado: {best_strategy}/{best_asset} com {best_rate:.2f}%", "success")
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
            estrategia = st.selectbox(
                "Selecione a Estratégia", 
                estrategia_options,
                index=0
            )
        
        with col2:
            # Se tiver resultados do catalogador, oferece como opções
            if "catalog_results" in st.session_state and st.session_state.catalog_results:
                asset_options = [item[1] for item in st.session_state.catalog_results]
                default_asset = asset_options[0] if asset_options else ""
                
                ativo = st.selectbox(
                    "Selecione o Ativo", 
                    asset_options,
                    index=0
                )
            else:
                # Caso contrário, permite entrada manual
                ativo = st.text_input("Digite o Ativo (ex: EURUSD, EURUSD-OTC)", value="EURUSD-OTC").upper()
        
        # Verifica disponibilidade do ativo
        if ativo and st.button("Verificar Disponibilidade do Ativo", key="check_asset"):
            with st.spinner(f"Verificando disponibilidade de {ativo}..."):
                if check_asset_available(st.session_state.API, ativo, tipo):
                    payout = get_payout(st.session_state.API, ativo, tipo)
                    st.success(f"Ativo {ativo} está disponível! Payout atual: {payout:.2f}%")
                    log_message(f"Ativo {ativo} disponível com payout de {payout:.2f}%", "success")
                else:
                    st.error(f"Ativo {ativo} não está disponível para operações de tipo {tipo}.")
                    log_message(f"Ativo {ativo} indisponível para o tipo {tipo}", "error")

# Seção 4: Iniciar Bot e Dashboard
if st.session_state.connected:
    st.markdown("<h2 class='sub-header'>4. Iniciar Bot e Dashboard</h2>", unsafe_allow_html=True)
    
    with st.container():
        st.markdown("""
        <div class="card">
            <p>Inicie o bot para começar as operações automatizadas. O dashboard mostrará os resultados em tempo real.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Botões para iniciar e parar o bot
        col1, col2 = st.columns(2)
        
        with col1:
            if not st.session_state.bot_running:
                if st.button("Iniciar Bot", use_container_width=True, key="btn_start_bot"):
                    if not ativo:
                        st.error("Selecione um ativo antes de iniciar o bot!")
                    else:
                        # Verifica se o ativo está disponível
                        if check_asset_available(st.session_state.API, ativo, tipo):
                            # Prepara os dados de configuração
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
                            
                            # Inicia o bot em uma thread separada
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
    
    # Dashboard de resultados
    if st.session_state.bot_running or len(st.session_state.operations) > 0:
        st.markdown("<h3 class='sub-header'>Dashboard de Resultados</h3>", unsafe_allow_html=True)
        
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Lucro/Prejuízo", 
                f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {st.session_state.lucro_total:.2f}",
                delta=f"{st.session_state.lucro_total:.2f}"
            )
        
        with col2:
            taxa_acerto = (st.session_state.wins / st.session_state.total_ops * 100) if st.session_state.total_ops > 0 else 0
            st.metric(
                "Taxa de Acerto", 
                f"{taxa_acerto:.2f}%",
                delta=f"{st.session_state.wins} ganhos / {st.session_state.losses} perdas"
            )
        
        with col3:
            st.metric(
                "Stop Win", 
                f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {stop_win}",
                delta=f"{(st.session_state.lucro_total/stop_win)*100:.1f}%" if stop_win > 0 else None
            )
        
        with col4:
            st.metric(
                "Stop Loss", 
                f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {stop_loss}",
                delta=f"{(st.session_state.lucro_total/(-stop_loss))*100:.1f}%" if stop_loss > 0 else None
            )
        
        # Gráfico de resultados
        if len(st.session_state.operations) > 0:
            # Cria DataFrame para o gráfico
            df_ops = pd.DataFrame(st.session_state.operations)
            
            # Gráfico de linha para lucro acumulado
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
            
            # Linha de referência em zero
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
            
            # Tabela de operações
            st.markdown("<p style='margin-top: 20px; font-weight: bold;'>Histórico de Operações:</p>", unsafe_allow_html=True)
            
            # Formata o DataFrame para exibição
            df_display = df_ops.copy()
            df_display['resultado'] = df_display['resultado'].apply(
                lambda x: "✅ WIN" if x == "win" else "❌ LOSS"
            )
            df_display['lucro'] = df_display.apply(
                lambda x: f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {x['lucro']:.2f}", axis=1
            )
            df_display['lucro_acumulado'] = df_display.apply(
                lambda x: f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {x['lucro_acumulado']:.2f}", axis=1
            )
            
            # Renomeia as colunas
            df_display = df_display.rename(columns={
                'timestamp': 'Horário',
                'ativo': 'Ativo',
                'direcao': 'Direção',
                'valor': 'Valor',
                'resultado': 'Resultado',
                'lucro': 'Lucro',
                'lucro_acumulado': 'Acumulado'
            })
            
            # Exibe a tabela
            st.dataframe(df_display, use_container_width=True)
    
    # Log de operações
    st.markdown("<p style='margin-top: 20px; font-weight: bold;'>Log de Operações:</p>", unsafe_allow_html=True)
    
    # Container para o log
    log_html = ""
    for msg in st.session_state.log_messages:
        log_html += f"{msg}<br>"
    
    st.markdown(f"""
    <div class="log-container">
        {log_html}
    </div>
    """, unsafe_allow_html=True)

# Rodapé
st.markdown("""
<div style="text-align: center; margin-top: 30px; opacity: 0.7;">
    <p>Bot Trader IQ Option v1.0 | 2025</p>
</div>
""", unsafe_allow_html=True)
