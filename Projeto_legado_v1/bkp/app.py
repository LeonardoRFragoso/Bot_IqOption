import streamlit as st
import json
import time
import threading
from configobj import ConfigObj
from iqoptionapi.stable_api import IQ_Option
from tabulate import tabulate
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
import warnings
import logging
from catalogador import catag, obter_pares_abertos, obter_resultados

# Suprimir avisos específicos do Streamlit sobre ScriptRunContext
logging.getLogger('streamlit.runtime.scriptrunner.script_runner').setLevel(logging.CRITICAL)
logging.getLogger('streamlit').setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message=".*Thread.*")

# Configurar um logger personalizado para o bot
bot_logger = logging.getLogger('bot_iqoption')
bot_logger.setLevel(logging.INFO)
bot_logger.propagate = False  # Impedir propagação para evitar duplicação

# Remover handlers existentes para evitar duplicação
if bot_logger.handlers:
    bot_logger.handlers.clear()

# Handler para console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
bot_logger.addHandler(console_handler)

# Handler para arquivo
try:
    file_handler = logging.FileHandler('bot_log.txt')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    bot_logger.addHandler(file_handler)
except:
    pass  # Se não conseguir criar o arquivo de log, apenas continue

# Configuração da página
st.set_page_config(
    page_title="Bot IQ Option Trader",
    page_icon="",
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
        font-size: 2.8rem;
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
        margin-top: 2rem;
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
    
    /* Containers */
    .dashboard-container {
        background-color: rgba(30, 30, 46, 0.7);
        border-radius: 10px;
        padding: 20px;
        border: 1px solid #3D3D60;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
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
    
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 15px rgba(0, 0, 0, 0.2);
    }
    
    /* Sidebar */
    .css-1d391kg, .css-1lcbmhc {
        background-color: rgba(25, 25, 35, 0.9);
    }
    
    /* Botões */
    .stButton>button {
        background: linear-gradient(90deg, #0078ff, #00bfff);
        color: white;
        border: none;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        transition: all 0.3s;
    }
    
    .stButton>button:hover {
        background: linear-gradient(90deg, #00bfff, #0078ff);
        box-shadow: 0 0 10px rgba(0, 191, 255, 0.5);
        transform: translateY(-2px);
    }
    
    /* Inputs */
    .stTextInput>div>div>input, .stNumberInput>div>div>input {
        background-color: rgba(45, 45, 68, 0.7);
        border: 1px solid #3D3D60;
        color: #E0E0E0;
        border-radius: 5px;
    }
    
    /* Selectbox */
    .stSelectbox>div>div {
        background-color: rgba(45, 45, 68, 0.7);
        border: 1px solid #3D3D60;
        color: #E0E0E0;
        border-radius: 5px;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: rgba(45, 45, 68, 0.7);
        border: 1px solid #3D3D60;
        border-radius: 5px;
        color: #E0E0E0;
    }
    
    /* Métricas */
    .stMetric {
        background-color: rgba(45, 45, 68, 0.7);
        border: 1px solid #3D3D60;
        border-radius: 10px;
        padding: 10px;
        transition: all 0.3s ease;
    }
    
    .stMetric:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.2);
    }
    
    /* Tabelas */
    .dataframe {
        background-color: rgba(45, 45, 68, 0.7);
        border: 1px solid #3D3D60;
        border-radius: 5px;
        color: #E0E0E0;
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 10px;
        background-color: #1E1E2E;
    }
    
    ::-webkit-scrollbar-thumb {
        background-color: #3D3D60;
        border-radius: 5px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background-color: #4D4D80;
    }
    
    /* Divisor */
    hr {
        border-color: #3D3D60;
        margin: 20px 0;
    }
    
    /* Animação de loading */
    .stSpinner>div {
        border-top-color: #00bfff !important;
    }
    
    /* Animação de pulsação */
    @keyframes pulse {
        0% {
            box-shadow: 0 0 0 0 rgba(0, 191, 255, 0.7);
        }
        70% {
            box-shadow: 0 0 0 10px rgba(0, 191, 255, 0);
        }
        100% {
            box-shadow: 0 0 0 0 rgba(0, 191, 255, 0);
        }
    }
    
    .pulse {
        animation: pulse 2s infinite;
    }
    
    /* Estilo para o log */
    .log-container {
        height: 300px;
        overflow-y: auto;
        background-color: rgba(25, 25, 35, 0.9);
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #3D3D60;
        font-family: 'Consolas', monospace;
        font-size: 0.9rem;
        line-height: 1.5;
    }
    
    /* Estilo para tabelas de estatísticas */
    .stats-table {
        width: 100%;
        border-collapse: collapse;
    }
    
    .stats-table tr {
        border-bottom: 1px solid rgba(61, 61, 96, 0.5);
    }
    
    .stats-table tr:last-child {
        border-bottom: none;
    }
    
    .stats-table td {
        padding: 8px 4px;
    }
    
    .stats-table td:first-child {
        font-weight: bold;
        color: #CCCCCC;
    }
    
    .stats-table td:last-child {
        text-align: right;
        color: #E0E0E0;
    }
    
    /* Estilo para cards de estatísticas */
    .stats-card {
        background-color: rgba(45, 45, 68, 0.7);
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #3D3D60;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .stats-card h4 {
        text-align: center;
        margin-bottom: 10px;
        color: #00bfff;
        font-size: 1.2rem;
    }
</style>
""", unsafe_allow_html=True)

# Título principal
st.markdown("<h1 class='main-header'>Bot Trader IQ Option</h1>", unsafe_allow_html=True)

# Variável global para controle do bot
BOT_RUNNING = False

# Variáveis para comunicação entre threads
if "bot_messages" not in st.session_state:
    st.session_state.bot_messages = []
if "bot_lucro_total" not in st.session_state:
    st.session_state.bot_lucro_total = 0.0
if "bot_wins" not in st.session_state:
    st.session_state.bot_wins = 0
if "bot_losses" not in st.session_state:
    st.session_state.bot_losses = 0
if "bot_empates" not in st.session_state:
    st.session_state.bot_empates = 0
if "bot_total_ops" not in st.session_state:
    st.session_state.bot_total_ops = 0
if "bot_historico" not in st.session_state:
    st.session_state.bot_historico = []
if "log" not in st.session_state:
    st.session_state.log = []

# Função auxiliar para acessar session_state com segurança
def safe_session_state_update(key, value):
    try:
        if key not in st.session_state:
            st.session_state[key] = value
        else:
            st.session_state[key] = value
    except Exception as e:
        bot_logger.error(f"Erro ao atualizar session_state[{key}]: {str(e)}")

# Função auxiliar para incrementar session_state com segurança
def safe_session_state_increment(key):
    try:
        if key not in st.session_state:
            st.session_state[key] = 1
        else:
            st.session_state[key] += 1
    except Exception as e:
        bot_logger.error(f"Erro ao incrementar session_state[{key}]: {str(e)}")

# Função auxiliar para adicionar ao histórico com segurança
def safe_add_to_historico(item):
    try:
        if "bot_historico" not in st.session_state:
            st.session_state.bot_historico = []
        st.session_state.bot_historico.append(item)
    except Exception as e:
        bot_logger.error(f"Erro ao adicionar ao histórico: {str(e)}")

# -----------------------------------------------------------------------------
# Função para registrar mensagens no log do dashboard
def log_message(msg, show_in_ui=True):
    timestamp = datetime.now().strftime('%H:%M:%S')
    if "log" not in st.session_state:
        st.session_state.log = []
    st.session_state.log.append(f"{timestamp} - {msg}")
    
    # Usar o logger personalizado para evitar avisos de ScriptRunContext
    # Evita duplicação de logs ao usar apenas o logger personalizado
    bot_logger.info(msg)
    
    # Para comunicação entre threads - Apenas atualiza contadores, não duplica logs
    if "bot_messages" in st.session_state:
        # Não adiciona a mensagem novamente, apenas atualiza os contadores
        # st.session_state.bot_messages.append(f"{timestamp} - {msg}")
        
        # Atualiza contadores baseados na mensagem
        if "WIN" in msg:
            # Verificar se as variáveis existem antes de incrementar
            if "bot_wins" not in st.session_state:
                st.session_state.bot_wins = 1
            else:
                st.session_state.bot_wins += 1
                
            if "bot_total_ops" not in st.session_state:
                st.session_state.bot_total_ops = 1
            else:
                st.session_state.bot_total_ops += 1
                
        elif "LOSS" in msg:
            # Verificar se as variáveis existem antes de incrementar
            if "bot_losses" not in st.session_state:
                st.session_state.bot_losses = 1
            else:
                st.session_state.bot_losses += 1
                
            if "bot_total_ops" not in st.session_state:
                st.session_state.bot_total_ops = 1
            else:
                st.session_state.bot_total_ops += 1
                
        elif "EMPATE" in msg:
            # Verificar se as variáveis existem antes de incrementar
            if "bot_empates" not in st.session_state:
                st.session_state.bot_empates = 1
            else:
                st.session_state.bot_empates += 1
                
            if "bot_total_ops" not in st.session_state:
                st.session_state.bot_total_ops = 1
            else:
                st.session_state.bot_total_ops += 1
        
        # Atualiza lucro total
        if "Lucro Total:" in msg:
            try:
                if "bot_lucro_total" not in st.session_state:
                    st.session_state.bot_lucro_total = 0.0
                st.session_state.bot_lucro_total = float(msg.split("Lucro Total:")[1].strip())
            except:
                pass

    if show_in_ui:
        # Atualiza o log no dashboard
        log_container = st.empty()
        log_text = ""
        for log in st.session_state.log:
            if "WIN" in log:
                log_text += f"<span style='color: #28a745;'>{log}</span><br>"
            elif "LOSS" in log:
                log_text += f"<span style='color: #dc3545;'>{log}</span><br>"
            elif "EMPATE" in log:
                log_text += f"<span style='color: #ffc107;'>{log}</span><br>"
            elif "STOP" in log:
                log_text += f"<span style='color: #17a2b8; font-weight: bold;'>{log}</span><br>"
            elif "Entrada" in log:
                log_text += f"<span style='color: #9370DB;'>{log}</span><br>"
            else:
                log_text += f"<span style='color: #E0E0E0;'>{log}</span><br>"
        
        log_container.markdown(f"""
        <div class="log-container">
            {log_text}
        </div>
        """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Função para validar configurações
def validar_configuracoes():
    """Valida as configurações antes de iniciar o bot"""
    mensagens = []
    
    # Validar credenciais
    if not st.session_state.get("email") or not st.session_state.get("senha"):
        mensagens.append("Email e senha são obrigatórios")
    
    # Validar valores numéricos
    try:
        valor_entrada = float(st.session_state.get("valor_entrada", 0))
        if valor_entrada <= 0:
            mensagens.append("Valor de entrada deve ser maior que zero")
    except:
        mensagens.append("Valor de entrada inválido")
    
    try:
        stop_win = float(st.session_state.get("stop_win", 0))
        if stop_win <= 0:
            mensagens.append("Stop Win deve ser maior que zero")
    except:
        mensagens.append("Stop Win inválido")
    
    try:
        stop_loss = float(st.session_state.get("stop_loss", 0))
        if stop_loss <= 0:
            mensagens.append("Stop Loss deve ser maior que zero")
    except:
        mensagens.append("Stop Loss inválido")
    
    # Validar estratégia e ativo
    estrategia = st.session_state.get("estrategia_choice")
    if not estrategia:
        mensagens.append("Selecione uma estratégia")
    
    ativo = st.session_state.get("ativo_input")
    if not ativo:
        mensagens.append("Selecione ou digite um ativo")
    
    return mensagens

# Função para carregar configurações com verificação
def carregar_configuracoes_seguras():
    """Carrega configurações com verificação de existência de chaves"""
    try:
        config = ConfigObj('config.txt', encoding='utf-8')
        
        # Verificar e criar seções se não existirem
        if 'LOGIN' not in config:
            config['LOGIN'] = {}
        if 'AJUSTES' not in config:
            config['AJUSTES'] = {}
        if 'MARTINGALE' not in config:
            config['MARTINGALE'] = {}
        if 'SOROS' not in config:
            config['SOROS'] = {}
        
        # Definir valores padrão para chaves ausentes
        # LOGIN
        if 'email' not in config['LOGIN']:
            config['LOGIN']['email'] = ""
        if 'senha' not in config['LOGIN']:
            config['LOGIN']['senha'] = ""
        
        # AJUSTES
        if 'tipo' not in config['AJUSTES']:
            config['AJUSTES']['tipo'] = "automatico"
        if 'valor_entrada' not in config['AJUSTES']:
            config['AJUSTES']['valor_entrada'] = "2.0"
        if 'stop_win' not in config['AJUSTES']:
            config['AJUSTES']['stop_win'] = "20.0"
        if 'stop_loss' not in config['AJUSTES']:
            config['AJUSTES']['stop_loss'] = "10.0"
        if 'estrategia' not in config['AJUSTES']:
            config['AJUSTES']['estrategia'] = "MHI"
        if 'ativo' not in config['AJUSTES']:
            config['AJUSTES']['ativo'] = ""
        if 'analise_medias' not in config['AJUSTES']:
            config['AJUSTES']['analise_medias'] = "N"
        if 'velas_medias' not in config['AJUSTES']:
            config['AJUSTES']['velas_medias'] = "20"
        
        # MARTINGALE
        if 'usar' not in config['MARTINGALE']:
            config['MARTINGALE']['usar'] = "N"
        if 'niveis' not in config['MARTINGALE']:
            config['MARTINGALE']['niveis'] = "1"
        if 'fator' not in config['MARTINGALE']:
            config['MARTINGALE']['fator'] = "2.0"
        
        # SOROS
        if 'usar' not in config['SOROS']:
            config['SOROS']['usar'] = "N"
        if 'niveis' not in config['SOROS']:
            config['SOROS']['niveis'] = "1"
        
        # Salvar configurações atualizadas
        config.write()
        
        return config
    except Exception as e:
        st.error(f"Erro ao carregar configurações: {str(e)}")
        # Criar configuração padrão em caso de erro
        config = ConfigObj()
        config['LOGIN'] = {'email': "", 'senha': ""}
        config['AJUSTES'] = {
            'tipo': "automatico", 
            'valor_entrada': "2.0", 
            'stop_win': "20.0", 
            'stop_loss': "10.0",
            'estrategia': "MHI",
            'ativo': "",
            'analise_medias': "N",
            'velas_medias': "20"
        }
        config['MARTINGALE'] = {'usar': "N", 'niveis': "1", 'fator': "2.0"}
        config['SOROS'] = {'usar': "N", 'niveis': "1"}
        
        try:
            config.filename = 'config.txt'
            config.write()
        except:
            pass
        
        return config

# -----------------------------------------------------------------------------
# Função para tentar reconectar à API com várias tentativas
def reconectar_api(api, max_tentativas=3, intervalo=5):
    """Tenta reconectar à API com várias tentativas"""
    for tentativa in range(1, max_tentativas + 1):
        try:
            log_message(f"Tentativa de reconexão {tentativa}/{max_tentativas}...")
            check, reason = api.connect()
            if check:
                log_message("Reconexão bem-sucedida!")
                return True
            else:
                log_message(f"Falha na reconexão: {reason}")
                time.sleep(intervalo)
        except Exception as e:
            log_message(f"Erro durante a reconexão: {str(e)}")
            time.sleep(intervalo)
    
    log_message("Todas as tentativas de reconexão falharam")
    return False

# Função para verificar se o ativo está disponível com tratamento de erros
def verificar_ativo_disponivel(api, ativo, tipo="binary"):
    """Verifica se o ativo está disponível com tratamento de erros"""
    max_tentativas = 3
    
    for tentativa in range(1, max_tentativas + 1):
        try:
            ativo_aberto = api.get_all_open_time()
            
            # Verificar se o ativo existe no dicionário
            if tipo not in ativo_aberto:
                log_message(f"Tipo de operação '{tipo}' não disponível")
                return False
                
            if ativo not in ativo_aberto[tipo]:
                log_message(f"Ativo '{ativo}' não encontrado para o tipo '{tipo}'")
                return False
                
            # Verificar se o ativo está aberto
            if not ativo_aberto[tipo][ativo]['open']:
                log_message(f"Ativo '{ativo}' está fechado no momento")
                return False
                
            return True
            
        except Exception as e:
            log_message(f"Erro ao verificar disponibilidade do ativo (tentativa {tentativa}/{max_tentativas}): {str(e)}")
            
            if tentativa < max_tentativas:
                time.sleep(2)
            else:
                log_message("Falha ao verificar disponibilidade do ativo após várias tentativas")
                return False
    
    return False

# Função para parada segura do bot
def parar_bot_seguro():
    """Para o bot de forma segura, garantindo que recursos sejam liberados"""
    global BOT_RUNNING
    
    log_message("Iniciando parada segura do bot...")
    
    # Sinalizar que o bot deve parar
    BOT_RUNNING = False
    
    # Adicionar aqui qualquer limpeza adicional necessária
    log_message("Bot parado com segurança")

# -----------------------------------------------------------------------------
# Sidebar – Configuração e Login
st.sidebar.markdown("<h2 style='text-align: center; background: linear-gradient(90deg, #0078ff, #00bfff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 600; margin-bottom: 20px;'> Configuração e Login</h2>", unsafe_allow_html=True)

# Adiciona logo na sidebar
st.sidebar.markdown("""
<div style="text-align: center; margin-bottom: 20px;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/IQ_Option_logo.svg/1200px-IQ_Option_logo.svg.png" width="150">
</div>
""", unsafe_allow_html=True)

with st.sidebar.expander("Credenciais IQ Option", expanded=True):
    email = st.text_input("Email", value="", key="email", placeholder="Seu email na IQ Option")
    senha = st.text_input("Senha", type="password", key="senha", placeholder="Sua senha")
    conta = st.selectbox("Conta", ["Demo", "Real"], key="conta")

with st.sidebar.expander("Configurações de Operação", expanded=True):
    tipo = st.selectbox("Tipo de Operação", ["automatico", "digital", "binary"], key="tipo", 
                        help="Escolha o tipo de operação a ser realizada")
    
    col1, col2 = st.columns(2)
    with col1:
        valor_entrada = st.number_input("Valor Entrada", value=2.0, step=0.5, format="%.2f", key="valor_entrada")
        stop_loss = st.number_input("Stop Loss", value=10.0, step=1.0, format="%.2f", key="stop_loss")
    with col2:
        stop_win = st.number_input("Stop Win", value=20.0, step=1.0, format="%.2f", key="stop_win")
        analise_medias = st.selectbox("Análise Médias", ["N", "S"], key="analise_medias", 
                                    help="Usar análise de médias móveis para confirmar tendência")

    usar_martingale = st.checkbox("Usar Martingale", value=False, key="usar_martingale")
    if usar_martingale:
        col1, col2 = st.columns(2)
        with col1:
            niveis_martingale = st.number_input("Níveis", value=1, step=1, key="niveis_martingale", min_value=1)
        with col2:
            fator_martingale = st.number_input("Fator", value=2.0, key="fator_martingale", min_value=1.0, format="%.1f")
    else:
        niveis_martingale = 0
        fator_martingale = 0.0

with st.sidebar.expander("Configurações de Soros", expanded=False):
    usar_soros = st.checkbox("Usar Soros", value=False, key="usar_soros")
    if usar_soros:
        niveis_soros = st.number_input("Níveis de Soros", value=1, step=1, key="niveis_soros", min_value=1)
    else:
        niveis_soros = 0

with st.sidebar.expander("Configurações de Análise", expanded=False):
    velas_medias = st.number_input("Número de Velas para Médias", value=20, step=1, key="velas_medias", min_value=3)

# Adiciona informações na parte inferior da sidebar
st.sidebar.markdown("""
<div style="position: fixed; bottom: 20px; left: 20px; right: 20px; text-align: center; font-size: 0.8rem; color: #888;">
    <hr style="margin: 10px 0; border-color: #3D3D60;">
    <p>Bot Trader IQ Option v1.0</p>
    <p> 2025 - Todos os direitos reservados</p>
</div>
""", unsafe_allow_html=True)

if st.sidebar.button("Salvar Configurações", use_container_width=True, key="salvar_config"):
    # Obtém a estratégia e ativo selecionados (se disponíveis)
    estrategia = st.session_state.get("estrategia_choice", "MHI")
    ativo = st.session_state.get("ativo_input", "")
    
    # Sanitiza os valores para evitar problemas de codificação
    estrategia = estrategia.replace('ê', 'e').replace('ã', 'a')
    
    try:
        # Lê a configuração existente ou cria uma nova
        try:
            config = ConfigObj('config.txt', encoding='utf-8')
        except:
            config = ConfigObj()
            
        # Atualiza as configurações
        config["LOGIN"] = {"email": email, "senha": senha}
        config["AJUSTES"] = {"tipo": tipo,
                            "valor_entrada": str(valor_entrada),
                            "stop_win": str(stop_win),
                            "stop_loss": str(stop_loss),
                            "analise_medias": analise_medias,
                            "velas_medias": str(velas_medias),
                            "estrategia": estrategia,
                            "ativo": ativo}
        config["MARTINGALE"] = {"usar": "S" if usar_martingale else "N",
                                "niveis": str(niveis_martingale),
                                "fator": str(fator_martingale)}
        config["SOROS"] = {"usar": "S" if usar_soros else "N",
                        "niveis": str(niveis_soros)}
        
        # Salva o arquivo
        config.filename = "config.txt"
        config.write()
        
        st.sidebar.success("")
        log_message("Configuração salva em config.txt")
    except Exception as e:
        st.sidebar.error(f" Erro ao salvar configuração: {str(e)}")
        log_message(f"Erro ao salvar configuração: {str(e)}")
        
        # Tenta uma abordagem alternativa se a primeira falhar
        try:
            with open('config.txt', 'w') as f:
                f.write("[LOGIN]\n")
                f.write(f"email = {email}\n")
                f.write(f"senha = {senha}\n\n")
                
                f.write("[AJUSTES]\n")
                f.write(f"tipo = {tipo}\n")
                f.write(f"valor_entrada = {valor_entrada}\n")
                f.write(f"stop_win = {stop_win}\n")
                f.write(f"stop_loss = {stop_loss}\n")
                f.write(f"analise_medias = {analise_medias}\n")
                f.write(f"velas_medias = {velas_medias}\n")
                f.write(f"estrategia = {estrategia}\n")
                f.write(f"ativo = {ativo}\n\n")
                
                f.write("[MARTINGALE]\n")
                f.write(f"usar = {'S' if usar_martingale else 'N'}\n")
                f.write(f"niveis = {niveis_martingale}\n")
                f.write(f"fator = {fator_martingale}\n\n")
                
                f.write("[SOROS]\n")
                f.write(f"usar = {'S' if usar_soros else 'N'}\n")
                f.write(f"niveis = {niveis_soros}\n")
            
            st.sidebar.success("")
        except Exception as e2:
            st.sidebar.error(f" Falha no método alternativo: {str(e2)}")

# -----------------------------------------------------------------------------
# Seção: Conectar na IQ Option
st.markdown("<h2 class='sub-header'> 1 - Conectar na IQ Option</h2>", unsafe_allow_html=True)

with st.container():
    st.markdown("""
    <div class="card">
        <div style="display: flex; align-items: center; margin-bottom: 15px;">
            <div style="background: linear-gradient(135deg, #0078ff, #00bfff); width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px;">
                <span style="color: white; font-size: 20px;">🔑</span>
            </div>
            <div>
                <h3 style="margin: 0; color: #E0E0E0;">Conexão com a Plataforma</h3>
                <p style="margin: 0; color: #AAAAAA; font-size: 0.9rem;">Clique no botão abaixo para se conectar à sua conta IQ Option usando as credenciais fornecidas.</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Conectar à IQ Option", use_container_width=True, key="conectar"):
        try:
            with st.spinner("Conectando à IQ Option..."):
                st.session_state.API = IQ_Option(email, senha)
                check, reason = st.session_state.API.connect()
                if check:
                    st.success("")
                    log_message("Conectado com sucesso.")
                    if conta == "Demo":
                        st.session_state.API.change_balance("PRACTICE")
                        log_message("Conta demo selecionada.")
                    else:
                        st.session_state.API.change_balance("REAL")
                        log_message("Conta real selecionada.")
                    perfil = json.loads(json.dumps(st.session_state.API.get_profile_ansyc()))
                    st.session_state.cifrao = str(perfil['currency_char'])
                    st.info(f"Saldo atual: {st.session_state.cifrao} {st.session_state.API.get_balance()}")
                    log_message(f"Saldo atual: {st.session_state.cifrao} {st.session_state.API.get_balance()}")
                else:
                    st.error(f" Erro ao conectar: {reason}")
                    log_message(f"Erro ao conectar: {reason}")
        except Exception as e:
            st.error(f" Exceção na conexão: {str(e)}")
            log_message("Exceção na conexão: " + str(e))

# -----------------------------------------------------------------------------
# Seção: Catalogador e Seleção de Estratégia
if "API" in st.session_state:
    st.markdown("<h2 class='sub-header'> 2 - Executar Catalogador e Selecionar Estratégia</h2>", unsafe_allow_html=True)
    
    with st.container():
        st.markdown("""
        <div class="card">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <div style="background: linear-gradient(135deg, #00cc66, #00ff99); width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px;">
                    <span style="color: white; font-size: 20px;">📈</span>
                </div>
                <div>
                    <h3 style="margin: 0; color: #E0E0E0;">Análise de Ativos</h3>
                    <p style="margin: 0; color: #AAAAAA; font-size: 0.9rem;">Execute o catalogador para analisar os ativos disponíveis e selecione a estratégia desejada para operar.</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("Executar Catalogador", use_container_width=True, key="executar_catalogador"):
                try:
                    with st.spinner("Executando catalogador..."):
                        lista_catalog, linha = catag(st.session_state.API)
                        if lista_catalog:
                            st.session_state.lista_catalog = lista_catalog
                            st.session_state.linha_catalog = linha
                            log_message("Catalogador executado com sucesso.")
                            st.success("")
                        else:
                            st.error("")
                            log_message("Erro ao executar catalogador.")
                except Exception as e:
                    st.error(f" Exceção no catalogador: {str(e)}")
                    log_message("Exceção no catalogador: " + str(e))
        
        with col2:
            estrategia_choice = st.selectbox(
                "Selecione a Estratégia",
                ["MHI", "Torres Gêmeas", "MHI M5"],
                key="estrategia_choice",
                help="Escolha a estratégia de operação"
            )
        
        # Exibição dos resultados do catalogador
        if "lista_catalog" in st.session_state:
            with st.expander("", expanded=True):
                # Define os cabeçalhos fixos para a tabela
                headers = ["", "", "", "", ""]
                st.markdown(f"```\n{tabulate(st.session_state.lista_catalog, headers=headers, tablefmt='pretty')}\n```")
                
                # Extrair ativos da lista de catalogação
                ativos = [item[1] for item in st.session_state.lista_catalog]  # Índice 1 contém o nome do par
                default_ativo = ativos[0] if ativos else ""
                
                st.markdown("<p style='margin-top:15px;'><b></b></p>", unsafe_allow_html=True)
                st.markdown("<p style='margin-top: 10px; font-weight: bold;'>Selecione ou digite o ativo:</p>", unsafe_allow_html=True)
                ativo_input = st.selectbox("Selecione o Ativo", ativos, index=0, key="ativo_select") if ativos else st.text_input("Digite o Ativo", value=default_ativo, key="ativo_input")
                
                # Botão para salvar a estratégia e ativo selecionados
                if st.button("Salvar Estratégia e Ativo", use_container_width=True, key="salvar_estrategia"):
                    # Atualiza o arquivo de configuração
                    try:
                        # Lê a configuração existente ou cria uma nova
                        try:
                            config = ConfigObj('config.txt', encoding='utf-8')
                        except:
                            config = ConfigObj()
                            
                        # Atualiza as configurações
                        config["AJUSTES"] = {"estrategia": estrategia_choice,
                            "ativo": ativo_input}
                        
                        # Salva o arquivo
                        config.filename = 'config.txt'
                        config.write()
                        
                        st.success("")
                        log_message(f"" + estrategia_choice + "" + ativo_input + "")
                    except Exception as e:
                        st.error(f" Erro ao salvar configuração: {str(e)}")
                        log_message(f"Erro ao salvar configuração: {str(e)}")
                        
                        # Tenta uma abordagem alternativa se a primeira falhar
                        try:
                            with open('config.txt', 'w') as f:
                                f.write(f"[AJUSTES]\nestrategia = {estrategia_choice}\nativo = {ativo_input}\n")
                            st.success("")
                        except Exception as e2:
                            st.error(f" Falha no método alternativo: {str(e2)}")
        else:
            ativo_input = st.text_input("", value="")

# -----------------------------------------------------------------------------
# Função que roda o bot em thread separada, recebendo a API como parâmetro
def run_bot(api):
    global BOT_RUNNING
    
    # Obtém as configurações
    config = carregar_configuracoes_seguras()
    
    # Parâmetros
    valor_entrada = float(config['AJUSTES']['valor_entrada'])
    stop_win = float(config['AJUSTES']['stop_win'])
    stop_loss = float(config['AJUSTES']['stop_loss'])
    tipo = config['AJUSTES']['tipo']
    estrategia = config['AJUSTES'].get('estrategia', 'MHI')  # Valor padrão caso não exista
    ativo = config['AJUSTES'].get('ativo', '')  # Valor padrão caso não exista
    
    # Martingale
    usar_martingale = config['MARTINGALE']['usar'] == 'S'
    niveis_martingale = int(config['MARTINGALE']['niveis'])
    fator_martingale = float(config['MARTINGALE']['fator'])
    
    # Soros
    usar_soros = config['SOROS']['usar'] == 'S'
    niveis_soros = int(config['SOROS']['niveis'])
    
    # Análise de médias
    analise_medias = config['AJUSTES'].get('analise_medias', 'N')
    velas_medias = int(config['AJUSTES'].get('velas_medias', '20'))
    
    # Variáveis de controle
    lucro_atual = 0.0
    valor_atual = valor_entrada
    nivel_atual_martingale = 0
    nivel_atual_soros = 0
    valor_soros = 0
    lucro_op_atual = 0
    
    # Obter informações do perfil
    try:
        perfil = json.loads(json.dumps(api.get_profile_ansyc()))
        cifrao = str(perfil['currency_char'])
        nome = str(perfil['name'])
        safe_session_state_update('cifrao', cifrao)
        log_message(f"Bem-vindo, {nome}! Saldo atual: {cifrao}{api.get_balance()}")
    except Exception as e:
        cifrao = "$"
        log_message(f"Erro ao obter informações do perfil: {str(e)}")
    
    log_message(f"Bot iniciado - Estratégia: {estrategia}, Ativo: {ativo}, Valor: {valor_entrada}")
    
    # Função para verificar o horário da corretora
    def horario():
        return datetime.fromtimestamp(api.get_server_timestamp())
    
    # Função para calcular médias
    def medias(velas):
        soma = 0
        for i in velas:
            soma += i['close']
        media = soma / len(velas)
        
        if media > velas[-1]['close']:
            tendencia = 'put'
        else:
            tendencia = 'call'
        
        return tendencia
    
    # Função para verificar o payout
    def payout(par):
        profit = api.get_all_profit()
        all_asset = api.get_all_open_time()
        
        try:
            if all_asset['binary'][par]['open']:
                if profit[par]['binary'] > 0:
                    binary = round(profit[par]['binary'], 2) * 100
            else:
                binary = 0
        except:
            binary = 0
        
        try:
            if all_asset['turbo'][par]['open']:
                if profit[par]['turbo'] > 0:
                    turbo = round(profit[par]['turbo'], 2) * 100
            else:
                turbo = 0
        except:
            turbo = 0
        
        try:
            if all_asset['digital'][par]['open']:
                digital = api.get_digital_payout(par)
            else:
                digital = 0
        except:
            digital = 0
        
        return binary, turbo, digital
    
    # Função para realizar compra
    def compra(ativo, valor_entrada, direcao, exp, tipo):
        nonlocal lucro_atual, nivel_atual_soros, valor_soros, lucro_op_atual, valor_atual, nivel_atual_martingale
        
        # Lógica de Soros
        if usar_soros:
            if nivel_atual_soros == 0:
                entrada = valor_entrada
            elif nivel_atual_soros >= 1 and valor_soros > 0 and nivel_atual_soros <= niveis_soros:
                entrada = valor_entrada + valor_soros
            elif nivel_atual_soros > niveis_soros:
                lucro_op_atual = 0
                valor_soros = 0
                entrada = valor_entrada
                nivel_atual_soros = 0
        else:
            entrada = valor_entrada
        
        # Loop para martingale
        for i in range(nivel_atual_martingale + 1):
            # Aplica Martingale antes da nova entrada (exceto na primeira)
            if i > 0:
                entrada = round(entrada * fator_martingale, 2)
                log_message(f" MARTINGALE {i}: Aumentando valor para {entrada:.2f}")
            
            # Executar a compra na API
            try:
                log_message(f" ENTRADA REALIZADA: {ativo}, Direção: {direcao.upper()}, Valor: {entrada:.2f}, Expiração: {exp} min")
                
                if tipo.lower() == 'digital':
                    check, id = api.buy_digital_spot_v2(ativo, entrada, direcao.lower(), exp)
                else:
                    check, id = api.buy(entrada, ativo, direcao.lower(), exp)
                
                if check:
                    log_message(f" Ordem aberta com sucesso{' para gale ' + str(i) if i > 0 else ''}")
                    
                    # Aguardar resultado
                    tempo_espera = 0
                    max_tempo_espera = exp * 60 + 5  # Tempo de expiração em segundos + 5 segundos de margem
                    
                    while tempo_espera < max_tempo_espera:
                        time.sleep(1)
                        tempo_espera += 1
                        
                        try:
                            if tipo.lower() == 'digital':
                                status, resultado_valor = api.check_win_digital_v2(id)
                            else:
                                if hasattr(api, 'check_win_v3'):
                                    resultado_valor = api.check_win_v3(id)
                                    status = True
                                else:
                                    status, resultado_valor = api.check_win_v2(id)
                            
                            if status:
                                # Registra o timestamp da operação
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                resultado_valor = round(resultado_valor, 2)
                                
                                try:
                                    if resultado_valor > 0:
                                        # WIN
                                        lucro_atual += resultado_valor
                                        valor_soros += resultado_valor
                                        lucro_op_atual += resultado_valor
                                        
                                        # Atualiza session_state
                                        safe_session_state_increment('bot_wins')
                                        if "bot_lucro_total" not in st.session_state:
                                            st.session_state.bot_lucro_total = resultado_valor
                                        else:
                                            st.session_state.bot_lucro_total += resultado_valor
                                            
                                        log_message(f" RESULTADO: WIN +{resultado_valor:.2f}{' no gale ' + str(i) if i > 0 else ''} | Lucro Total: {lucro_atual:.2f}")
                                        
                                        # Registra a operação no histórico
                                        safe_add_to_historico({
                                            'timestamp': timestamp,
                                            'resultado': 'WIN',
                                            'valor': entrada,
                                            'lucro': resultado_valor,
                                            'lucro_acumulado': lucro_atual,
                                            'estrategia': estrategia,
                                            'ativo': ativo,
                                            'direcao': direcao,
                                            'martingale': i
                                        })
                                        
                                        # Reset martingale após WIN
                                        nivel_atual_martingale = 0
                                        
                                        # Aplicar Soros se configurado
                                        if usar_soros:
                                            if lucro_op_atual > 0:
                                                nivel_atual_soros += 1
                                                lucro_op_atual = 0
                                                log_message(f" SOROS: Próximo nível {nivel_atual_soros} com {valor_soros:.2f}")
                                            else:
                                                valor_soros = 0
                                                nivel_atual_soros = 0
                                                lucro_op_atual = 0
                                        
                                        return True, resultado_valor
                                        
                                    elif resultado_valor == 0:
                                        # EMPATE
                                        # Atualiza session_state
                                        safe_session_state_increment('bot_empates')
                                        log_message(f" RESULTADO: EMPATE{' no gale ' + str(i) if i > 0 else ''} | Lucro Total: {lucro_atual:.2f}")
                                        
                                        # Registra a operação no histórico
                                        safe_add_to_historico({
                                            'timestamp': timestamp,
                                            'resultado': 'EMPATE',
                                            'valor': entrada,
                                            'lucro': 0,
                                            'lucro_acumulado': lucro_atual,
                                            'estrategia': estrategia,
                                            'ativo': ativo,
                                            'direcao': direcao,
                                            'martingale': i
                                        })
                                        
                                        return True, 0
                                        
                                    else:
                                        # LOSS
                                        lucro_atual += resultado_valor  # Resultado negativo
                                        
                                        # Atualiza session_state
                                        safe_session_state_increment('bot_losses')
                                        if "bot_lucro_total" not in st.session_state:
                                            st.session_state.bot_lucro_total = resultado_valor
                                        else:
                                            st.session_state.bot_lucro_total += resultado_valor
                                            
                                        log_message(f" RESULTADO: LOSS {resultado_valor:.2f}{' no gale ' + str(i) if i > 0 else ''} | Lucro Total: {lucro_atual:.2f}")
                                        
                                        # Registra a operação no histórico
                                        safe_add_to_historico({
                                            'timestamp': timestamp,
                                            'resultado': 'LOSS',
                                            'valor': entrada,
                                            'lucro': resultado_valor,
                                            'lucro_acumulado': lucro_atual,
                                            'estrategia': estrategia,
                                            'ativo': ativo,
                                            'direcao': direcao,
                                            'martingale': i
                                        })
                                        
                                        # Se tiver mais níveis de martingale, continua para o próximo
                                        if usar_martingale and i < niveis_martingale:
                                            break  # Sai do loop de espera para ir para o próximo martingale
                                        else:
                                            # Reset martingale se atingiu o nível máximo
                                            nivel_atual_martingale = 0
                                            # Reset soros em caso de loss
                                            valor_soros = 0
                                            nivel_atual_soros = 0
                                            lucro_op_atual = 0
                                            return False, resultado_valor
                                    
                                    # Incrementa contador de operações totais
                                    safe_session_state_increment('bot_total_ops')
                                    break  # Sai do loop de espera após obter o resultado
                                    
                                except Exception as e:
                                    log_message(f" Erro ao processar resultado: {str(e)}")
                                    if tempo_espera >= max_tempo_espera - 1:
                                        break
                        except Exception as e:
                            log_message(f" Erro ao verificar resultado: {str(e)}")
                            if tempo_espera >= max_tempo_espera - 1:
                                break
                else:
                    log_message(f" Erro na abertura da ordem: {id}")
                    return False, 0
            
            except Exception as e:
                log_message(f" Erro ao realizar entrada: {str(e)}")
                return False, 0
        
        # Se chegou aqui após todas as tentativas de martingale, é LOSS
        if usar_martingale and nivel_atual_martingale < niveis_martingale:
            nivel_atual_martingale += 1
            log_message(f" MARTINGALE: Próxima entrada será nível {nivel_atual_martingale}")
        else:
            nivel_atual_martingale = 0
        
        return False, 0
    
    # Função para verificar stop win/loss
    def check_stop():
        try:
            if lucro_atual <= float('-'+str(abs(stop_loss))):
                log_message(f"STOP LOSS BATIDO {cifrao}{lucro_atual:.2f}")
                parar_bot_seguro()
                return False
            
            if lucro_atual >= float(abs(stop_win)):
                log_message(f"STOP WIN BATIDO {cifrao}{lucro_atual:.2f}")
                parar_bot_seguro()
                return False
            
            return True
        except Exception as e:
            log_message(f"Erro ao verificar stop: {str(e)}")
            # Em caso de erro, retorna True para não interromper o bot por falha no check
            return True
    
    # Loop principal do bot
    while BOT_RUNNING:
        try:
            # Verificar stop win/loss
            if not check_stop():
                BOT_RUNNING = False
                break
            
            # Verificar se o mercado está aberto
            try:
                check_open = api.check_connect()
                if not check_open:
                    log_message("Reconectando à IQ Option...")
                    if not reconectar_api(api):
                        log_message("Falha na reconexão. Parando o bot.")
                        BOT_RUNNING = False
                        break
                    time.sleep(5)
                    continue
            except Exception as e:
                log_message(f"Erro de conexão - {str(e)}")
                time.sleep(5)
                continue
            
            # Verificar se o ativo está disponível
            try:
                if ativo:
                    if not verificar_ativo_disponivel(api, ativo, tipo):
                        log_message(f"Ativo '{ativo}' não está disponível no momento")
                        time.sleep(30)
                        continue
                else:
                    log_message("Nenhum ativo selecionado")
                    time.sleep(5)
                    continue
            except Exception as e:
                log_message(f"Erro ao verificar disponibilidade do ativo - {str(e)}")
                time.sleep(5)
                continue
            
            # Definir tipo de operação automaticamente se necessário
            if tipo == 'automatico':
                binary, turbo, digital = payout(ativo)
                log_message(f"Payouts - Binary: {binary}%, Turbo: {turbo}%, Digital: {digital}%")
                
                if digital > turbo:
                    log_message(f"Suas entradas serão realizadas nas digitais")
                    tipo = 'digital'
                elif turbo > digital:
                    log_message(f"Suas entradas serão realizadas nas binárias")
                    tipo = 'binary'
                else:
                    log_message(f"Par fechado, escolha outro")
                    time.sleep(30)
                    continue
            
            # Lógica específica para cada estratégia
            if estrategia == "MHI":
                # Verificar o horário para entrada
                now = horario()
                minutos = float(now.strftime('%M.%S')[1:])
                
                # Exibir horário atual
                log_message(f"Horário atual: {now.strftime('%H:%M:%S')} - Minutos: {minutos}", show_in_ui=False)
                
                # Verificar se é momento de entrada (M1)
                entrar = True if (minutos >= 4.59 and minutos <= 5.00) or minutos >= 9.59 else False
                
                if not entrar:
                    # Aguardar próximo ciclo
                    time.sleep(0.2)
                    continue
                
                log_message("Iniciando análise da estratégia MHI")
                
                # Obter velas para análise
                timeframe = 60  # M1
                qnt_velas = 3
                
                # Análise de tendência com médias (opcional)
                tendencia = None
                if analise_medias == 'S':
                    velas_tendencia = api.get_candles(ativo, timeframe, int(velas_medias), time.time())
                    tendencia = medias(velas_tendencia)
                    log_message(f"Tendência baseada em médias: {tendencia.upper()}")
                
                # Obter velas para análise do padrão
                velas = api.get_candles(ativo, timeframe, qnt_velas, time.time())
                
                # Classificar as velas
                vela1 = 'Verde' if velas[-3]['open'] < velas[-3]['close'] else 'Vermelha' if velas[-3]['open'] > velas[-3]['close'] else 'Doji'
                vela2 = 'Verde' if velas[-2]['open'] < velas[-2]['close'] else 'Vermelha' if velas[-2]['open'] > velas[-2]['close'] else 'Doji'
                vela3 = 'Verde' if velas[-1]['open'] < velas[-1]['close'] else 'Vermelha' if velas[-1]['open'] > velas[-1]['close'] else 'Doji'
                
                cores = [vela1, vela2, vela3]
                log_message(f"Velas: {vela1}, {vela2}, {vela3}")
                
                # Definir direção com base no padrão MHI
                direcao = None
                if cores.count('Verde') > cores.count('Vermelha') and cores.count('Doji') == 0:
                    direcao = 'put'
                elif cores.count('Verde') < cores.count('Vermelha') and cores.count('Doji') == 0:
                    direcao = 'call'
                
                # Verificar se a direção está de acordo com a tendência
                if analise_medias == 'S' and direcao and tendencia and direcao != tendencia:
                    log_message(f"Entrada abortada - Contra tendência ({direcao.upper()} vs {tendencia.upper()})")
                    direcao = None
                
                # Executar entrada se houver direção definida
                if direcao:
                    log_message(f"Padrão MHI identificado - Entrada: {direcao.upper()}")
                    compra(ativo, valor_atual, direcao, 1, tipo)  # Expiração de 1 minuto
                else:
                    if cores.count('Doji') > 0:
                        log_message("Entrada abortada - Foi encontrado um doji na análise")
                    else:
                        log_message("Entrada abortada - Padrão não identificado")
                
                # Aguardar próximo ciclo
                time.sleep(60)  # Aguarda 1 minuto antes da próxima análise
                
            elif estrategia == "Torres Gêmeas":
                # Verificar o horário para entrada
                now = horario()
                minutos = float(now.strftime('%M.%S')[1:])
                
                # Verificar se é momento de entrada
                entrar = True if (minutos >= 3.59 and minutos <= 4.00) or minutos >= 9.59 else False
                
                if not entrar:
                    # Aguardar próximo ciclo
                    time.sleep(0.2)
                    continue
                
                log_message("Iniciando análise da estratégia Torres Gêmeas")
                
                # Obter velas para análise
                timeframe = 60  # M1
                qnt_velas = 4
                
                # Análise de tendência com médias (opcional)
                tendencia = None
                if analise_medias == 'S':
                    velas_tendencia = api.get_candles(ativo, timeframe, int(velas_medias), time.time())
                    tendencia = medias(velas_tendencia)
                    log_message(f"Tendência baseada em médias: {tendencia.upper()}")
                
                # Obter velas para análise do padrão
                velas = api.get_candles(ativo, timeframe, qnt_velas, time.time())
                
                # Classificar a vela de referência (4ª vela)
                vela4 = 'Verde' if velas[-4]['open'] < velas[-4]['close'] else 'Vermelha' if velas[-4]['open'] > velas[-4]['close'] else 'Doji'
                
                log_message(f"Vela de referência: {vela4}")
                
                # Definir direção com base no padrão Torres Gêmeas
                direcao = None
                if vela4 == 'Verde' and vela4 != 'Doji':
                    direcao = 'call'
                elif vela4 == 'Vermelha' and vela4 != 'Doji':
                    direcao = 'put'
                
                # Verificar se a direção está de acordo com a tendência
                if analise_medias == 'S' and direcao and tendencia and direcao != tendencia:
                    log_message(f"Entrada abortada - Contra tendência ({direcao.upper()} vs {tendencia.upper()})")
                    direcao = None
                
                # Executar entrada se houver direção definida
                if direcao:
                    log_message(f"Padrão Torres Gêmeas identificado - Entrada: {direcao.upper()}")
                    compra(ativo, valor_atual, direcao, 1, tipo)  # Expiração de 1 minuto
                else:
                    if vela4 == 'Doji':
                        log_message("Entrada abortada - Foi encontrado um doji na análise")
                    else:
                        log_message("Entrada abortada - Padrão não identificado")
                
                # Aguardar próximo ciclo
                time.sleep(60)  # Aguarda 1 minuto antes da próxima análise
                
            elif estrategia == "MHI M5":
                # Verificar o horário para entrada
                now = horario()
                minutos = float(now.strftime('%M.%S'))
                
                # Verificar se é momento de entrada (M5)
                entrar = True if (minutos >= 29.59 and minutos <= 30.00) or minutos == 59.59 else False
                
                if not entrar:
                    # Aguardar próximo ciclo
                    time.sleep(0.2)
                    continue
                
                log_message("Iniciando análise da estratégia MHI M5")
                
                # Obter velas para análise
                timeframe = 300  # M5
                qnt_velas = 3
                
                # Análise de tendência com médias (opcional)
                tendencia = None
                if analise_medias == 'S':
                    velas_tendencia = api.get_candles(ativo, timeframe, int(velas_medias), time.time())
                    tendencia = medias(velas_tendencia)
                    log_message(f"Tendência baseada em médias: {tendencia.upper()}")
                
                # Obter velas para análise do padrão
                velas = api.get_candles(ativo, timeframe, qnt_velas, time.time())
                
                # Classificar as velas
                vela1 = 'Verde' if velas[-3]['open'] < velas[-3]['close'] else 'Vermelha' if velas[-3]['open'] > velas[-3]['close'] else 'Doji'
                vela2 = 'Verde' if velas[-2]['open'] < velas[-2]['close'] else 'Vermelha' if velas[-2]['open'] > velas[-2]['close'] else 'Doji'
                vela3 = 'Verde' if velas[-1]['open'] < velas[-1]['close'] else 'Vermelha' if velas[-1]['open'] > velas[-1]['close'] else 'Doji'
                
                cores = [vela1, vela2, vela3]
                log_message(f"Velas: {vela1}, {vela2}, {vela3}")
                
                # Definir direção com base no padrão MHI
                direcao = None
                if cores.count('Verde') > cores.count('Vermelha') and cores.count('Doji') == 0:
                    direcao = 'put'
                elif cores.count('Verde') < cores.count('Vermelha') and cores.count('Doji') == 0:
                    direcao = 'call'
                
                # Verificar se a direção está de acordo com a tendência
                if analise_medias == 'S' and direcao and tendencia and direcao != tendencia:
                    log_message(f"Entrada abortada - Contra tendência ({direcao.upper()} vs {tendencia.upper()})")
                    direcao = None
                
                # Executar entrada se houver direção definida
                if direcao:
                    log_message(f"Padrão MHI M5 identificado - Entrada: {direcao.upper()}")
                    compra(ativo, valor_atual, direcao, 5, tipo)  # Expiração de 5 minutos
                else:
                    if cores.count('Doji') > 0:
                        log_message("Entrada abortada - Foi encontrado um doji na análise")
                    else:
                        log_message("Entrada abortada - Padrão não identificado")
                
                # Aguardar próximo ciclo
                time.sleep(60)  # Aguarda 1 minuto antes da próxima análise
                
            else:
                log_message(f"Estratégia '{estrategia}' não implementada")
                time.sleep(30)
            
        except Exception as e:
            log_message(f"Erro na execução do bot: {str(e)}")
            time.sleep(5)

# -----------------------------------------------------------------------------
# Seção: Iniciar Bot e Dashboard de Resultados
if "API" in st.session_state:
    st.markdown("<h2 class='sub-header'> 3 - Iniciar Bot e Acompanhar Resultados</h2>", unsafe_allow_html=True)
    
    with st.container():
        st.markdown("""
        <div class="card">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <div style="background: linear-gradient(135deg, #ff6b6b, #ff8e8e); width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px;">
                    <span style="color: white; font-size: 20px;">▶️</span>
                </div>
                <div>
                    <h3 style="margin: 0; color: #E0E0E0;">Operação Automatizada</h3>
                    <p style="margin: 0; color: #AAAAAA; font-size: 0.9rem;">Inicie o bot para começar a operar automaticamente com base nas configurações e estratégia selecionadas.</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Iniciar Operações Automatizadas", use_container_width=True, key="iniciar_bot"):
            # Efeito de animação ao iniciar o bot
            with st.spinner("Iniciando operações..."):
                st.markdown("""
                <div style="display: flex; justify-content: center; margin: 20px 0;">
                    <div style="background: linear-gradient(135deg, #0078ff, #00bfff); width: 80px; height: 80px; border-radius: 50%; display: flex; align-items: center; justify-content: center;" class="pulse">
                        <span style="color: white; font-size: 40px;">🤖</span>
                    </div>
                </div>
                <p style="text-align: center; color: #00bfff; font-weight: bold; margin-bottom: 20px;">Bot iniciado com sucesso!</p>
                """, unsafe_allow_html=True)
                time.sleep(2)  # Pequena pausa para efeito visual
            
            # Verificar configurações antes de iniciar o bot
            erros = validar_configuracoes()
            if erros:
                st.error("Configurações inválidas:")
                for erro in erros:
                    st.error(erro)
            else:
                BOT_RUNNING = True
                # Captura a API em uma variável local para uso na thread
                api_instance = st.session_state.API

                # Configuração para suprimir avisos na thread
                def run_bot_with_warnings_suppressed(api):
                    # Solução mais robusta para suprimir avisos
                    import sys
                    import os
                    import logging
                    import warnings
                    
                    # Desativar completamente todos os warnings do Python
                    warnings.simplefilter("ignore")
                    os.environ["PYTHONWARNINGS"] = "ignore"
                    
                    # Desativar todos os logs do Streamlit
                    for logger_name in logging.Logger.manager.loggerDict:
                        if 'streamlit' in logger_name:
                            logging.getLogger(logger_name).setLevel(logging.CRITICAL)
                            logging.getLogger(logger_name).propagate = False
                            logging.getLogger(logger_name).disabled = True
                    
                    # Redirecionar stderr para um arquivo nulo
                    class NullWriter:
                        def write(self, text):
                            pass
                        def flush(self):
                            pass
                    
                    # Salvar stderr original
                    original_stderr = sys.stderr
                    
                    try:
                        # Redirecionar stderr para evitar mensagens de aviso
                        sys.stderr = NullWriter()
                        
                        # Chamar a função real do bot
                        run_bot(api)
                    finally:
                        # Restaurar stderr original
                        sys.stderr = original_stderr

                # Inicia a thread do bot com supressão de avisos
                bot_thread = threading.Thread(target=run_bot_with_warnings_suppressed, args=(api_instance,), daemon=True)
                bot_thread.start()

    st.markdown("<h3 class='sub-header'> Dashboard de Resultados</h3>", unsafe_allow_html=True)
    
    with st.container():
        st.markdown("""
        <div class="dashboard-container">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <div style="background: linear-gradient(135deg, #9370DB, #8A2BE2); width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px;">
                    <span style="color: white; font-size: 20px;">📊</span>
                </div>
                <div>
                    <h3 style="margin: 0; color: #E0E0E0;">Acompanhamento em Tempo Real</h3>
                    <p style="margin: 0; color: #AAAAAA; font-size: 0.9rem;">Monitore o desempenho das operações e resultados do bot em tempo real.</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Layout do dashboard - Métricas principais
        col1, col2, col3 = st.columns(3)
        with col1:
            lucro_total_container = st.empty()
        with col2:
            operacoes_container = st.empty()
        with col3:
            taxa_acerto_container = st.empty()
        
        # Métricas adicionais
        col4, col5 = st.columns(2)
        with col4:
            stop_win_container = st.empty()
        with col5:
            stop_loss_container = st.empty()
        
        # Gráficos e estatísticas
        st.markdown("<p style='margin-top: 20px; font-weight: bold;'>Estatísticas Detalhadas:</p>", unsafe_allow_html=True)
        stats_container = st.empty()
        
        # Container para o log
        st.markdown("<p style='margin-top: 20px; font-weight: bold;'>Log de Operações:</p>", unsafe_allow_html=True)
        log_container = st.empty()
        
        # Loop de atualização do dashboard
        while BOT_RUNNING:
            # Atualiza métricas
            lucro_total = st.session_state.bot_lucro_total
            
            taxa_acerto = 0
            if st.session_state.bot_total_ops > 0:
                taxa_acerto = (st.session_state.bot_wins / st.session_state.bot_total_ops) * 100
                
            # Atualiza os containers com as métricas
            lucro_total_container.metric(
                label="", 
                value=f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {lucro_total:.2f}",
                delta=None
            )
            
            operacoes_container.metric(
                label="", 
                value=f"{st.session_state.bot_total_ops}",
                delta=f"" + str(st.session_state.bot_wins) + "" + str(st.session_state.bot_losses) + "" + str(st.session_state.bot_empates) + ""
            )
            
            taxa_acerto_container.metric(
                label="", 
                value=f"{taxa_acerto:.1f}%",
                delta=None
            )
            
            stop_win_container.metric(
                label="", 
                value=f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {stop_win}",
                delta=f"{(lucro_total/stop_win)*100:.1f}%" if stop_win > 0 else None
            )
            
            stop_loss_container.metric(
                label="", 
                value=f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {stop_loss}",
                delta=f"{(lucro_total/stop_loss)*100:.1f}%" if stop_loss > 0 else None
            )
            
            # Atualiza estatísticas detalhadas
            if st.session_state.bot_total_ops > 0:
                # Cria dados para o gráfico de pizza
                stats_cols = stats_container.columns([1, 1])
                
                with stats_cols[0]:
                    # Estatísticas em formato de tabela
                    stats_data = [
                        ["Total de Operações", st.session_state.bot_total_ops],
                        ["Vitórias", st.session_state.bot_wins],
                        ["Derrotas", st.session_state.bot_losses],
                        ["Empates", st.session_state.bot_empates],
                        ["Taxa de Acerto", f"{taxa_acerto:.1f}%"],
                        ["Lucro Médio por Operação", f"{lucro_total/st.session_state.bot_total_ops:.2f}"]
                    ]
                    
                    st.markdown(f"""
                    <div class="stats-card">
                        <h4>Resumo de Operações</h4>
                        <table class="stats-table">
                            {"".join([f"<tr><td>{row[0]}</td><td>{row[1]}</td></tr>" for row in stats_data])}
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Gráfico de pizza para resultados
                    if st.session_state.bot_total_ops > 0:
                        labels = ['', '', '']
                        values = [st.session_state.bot_wins, st.session_state.bot_losses, st.session_state.bot_empates]
                        colors = ['#28a745', '#dc3545', '#ffc107']
                        
                        fig = go.Figure(data=[go.Pie(
                            labels=labels,
                            values=values,
                            hole=.4,
                            marker=dict(colors=colors)
                        )])
                        
                        fig.update_layout(
                            title_text="Distribuição de Resultados",
                            showlegend=True,
                            legend=dict(orientation="h", y=-0.1),
                            height=300,
                            margin=dict(l=10, r=10, t=40, b=10),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(color='#E0E0E0')
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                
                with stats_cols[1]:
                    # Informações da estratégia atual
                    st.markdown(f"""
                    <div class="stats-card">
                        <h4>Configuração Atual</h4>
                        <table class="stats-table">
                            <tr><td>Estratégia:</td><td>{estrategia_choice}</td></tr>
                            <tr><td>Ativo:</td><td>{ativo_input}</td></tr>
                            <tr><td>Valor de Entrada:</td><td>{valor_entrada}</td></tr>
                            <tr><td>Tipo:</td><td>{tipo}</td></tr>
                            <tr><td>Martingale:</td><td>{"Sim" if usar_martingale else "Não"}</td></tr>
                            <tr><td>Soros:</td><td>{"Sim" if usar_soros else "Não"}</td></tr>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Gráfico de linha para lucro acumulado
                    if len(st.session_state.bot_historico) > 0:
                        # Criar DataFrame para o gráfico
                        df_historico = pd.DataFrame(st.session_state.bot_historico)
                        
                        # Gráfico de linha para lucro acumulado
                        fig = go.Figure()
                        
                        fig.add_trace(go.Scatter(
                            x=list(range(1, len(df_historico) + 1)),
                            y=df_historico['lucro_acumulado'],
                            mode='lines+markers',
                            name='Lucro Acumulado',
                            line=dict(color='#00bfff', width=3),
                            marker=dict(
                                size=8,
                                color=df_historico['lucro'].apply(lambda x: '#28a745' if x > 0 else '#dc3545' if x < 0 else '#ffc107'),
                                line=dict(width=2, color='#E0E0E0')
                            )
                        ))
                        
                        # Linha de referência em zero
                        fig.add_shape(
                            type="line",
                            x0=0,
                            y0=0,
                            x1=len(df_historico) + 1,
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
            
            # Atualiza o log com formatação de cores
            log_text = ""
            for log in st.session_state.bot_messages:
                if "WIN" in log:
                    log_text += f"<span style='color: #28a745;'>{log}</span><br>"
                elif "LOSS" in log:
                    log_text += f"<span style='color: #dc3545;'>{log}</span><br>"
                elif "EMPATE" in log:
                    log_text += f"<span style='color: #ffc107;'>{log}</span><br>"
                elif "STOP" in log:
                    log_text += f"<span style='color: #17a2b8; font-weight: bold;'>{log}</span><br>"
                elif "Entrada" in log:
                    log_text += f"<span style='color: #9370DB;'>{log}</span><br>"
                else:
                    log_text += f"<span style='color: #E0E0E0;'>{log}</span><br>"
            
            log_container.markdown(f"""
            <div class="log-container">
                {log_text}
            </div>
            """, unsafe_allow_html=True)
            
            time.sleep(1)

# Exibição dos resultados do catalogador
if "lista_catalog" in st.session_state:
    st.markdown("<p style='margin-top: 20px; font-weight: bold;'>Resultado do Catalogador:</p>", unsafe_allow_html=True)
    
    # Cria uma tabela para exibir os resultados
    st.dataframe(st.session_state.linha, label="Resultados do Catalogador", label_visibility="collapsed")
    
    # Permite selecionar um dos ativos do catalogador ou digitar manualmente
    st.markdown("<p style='margin-top:15px;'><b></b></p>", unsafe_allow_html=True)
    st.markdown("<p style='margin-top: 10px; font-weight: bold;'>Selecione ou digite o ativo:</p>", unsafe_allow_html=True)
    ativo_input = st.selectbox("Selecione o Ativo", [item[1] for item in st.session_state.lista_catalog], index=0, key="ativo_select") if st.session_state.lista_catalog else st.text_input("Digite o Ativo", value="", key="ativo_input")
