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
    page_icon="💹",
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

# -----------------------------------------------------------------------------
# Função para registrar mensagens no log do dashboard
def log_message(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    if "log" not in st.session_state:
        st.session_state.log = []
    st.session_state.log.append(f"{timestamp} - {msg}")
    
    # Usar o logger personalizado para evitar avisos de ScriptRunContext
    bot_logger.info(msg)
    
    # Para comunicação entre threads
    if "bot_messages" in st.session_state:
        st.session_state.bot_messages.append(f"{timestamp} - {msg}")
        
        # Atualiza contadores baseados na mensagem
        if "RESULTADO: WIN" in msg:
            st.session_state.bot_wins += 1
            st.session_state.bot_total_ops += 1
        elif "RESULTADO: LOSS" in msg:
            st.session_state.bot_losses += 1
            st.session_state.bot_total_ops += 1
        elif "RESULTADO: EMPATE" in msg:
            st.session_state.bot_empates += 1
            st.session_state.bot_total_ops += 1
        
        # Atualiza lucro total
        if "Lucro Total:" in msg:
            try:
                st.session_state.bot_lucro_total = float(msg.split("Lucro Total:")[1].strip())
            except:
                pass

# Inicializa variáveis de estado (exceto o controle do bot)
if "log" not in st.session_state:
    st.session_state.log = []

# -----------------------------------------------------------------------------
# Sidebar – Configuração e Login
st.sidebar.markdown("<h2 style='text-align: center; background: linear-gradient(90deg, #0078ff, #00bfff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 600; margin-bottom: 20px;'>⚙️ Configuração e Login</h2>", unsafe_allow_html=True)

# Adiciona logo na sidebar
st.sidebar.markdown("""
<div style="text-align: center; margin-bottom: 20px;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/IQ_Option_logo.svg/1200px-IQ_Option_logo.svg.png" width="150">
</div>
""", unsafe_allow_html=True)

with st.sidebar.expander("📧 Credenciais", expanded=True):
    email = st.text_input("Email", value="", key="email", placeholder="Seu email na IQ Option")
    senha = st.text_input("Senha", type="password", key="senha", placeholder="Sua senha")
    conta = st.selectbox("Conta", ["Demo", "Real"], key="conta")

with st.sidebar.expander("💰 Configurações de Operação", expanded=True):
    tipo = st.selectbox("Tipo de Operação", ["automatico", "digital", "binary"], key="tipo", 
                        help="Escolha o tipo de operação a ser realizada")
    
    col1, col2 = st.columns(2)
    with col1:
        valor_entrada = st.number_input("Valor de Entrada", value=1.0, key="valor_entrada", 
                                      min_value=1.0, format="%.2f")
    with col2:
        stop_win = st.number_input("Stop Win", value=10.0, key="stop_win", 
                                 min_value=0.0, format="%.2f")
    
    col3, col4 = st.columns(2)
    with col3:
        stop_loss = st.number_input("Stop Loss", value=5.0, key="stop_loss", 
                                  min_value=0.0, format="%.2f")

with st.sidebar.expander("🔄 Configurações de Martingale", expanded=False):
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

with st.sidebar.expander("📈 Configurações de Soros", expanded=False):
    usar_soros = st.checkbox("Usar Soros", value=False, key="usar_soros")
    if usar_soros:
        niveis_soros = st.number_input("Níveis de Soros", value=1, step=1, key="niveis_soros", min_value=1)
    else:
        niveis_soros = 0

with st.sidebar.expander("📊 Configurações de Análise", expanded=False):
    analise_medias = st.selectbox("Análise de Médias", ["S", "N"], key="analise_medias")
    velas_medias = st.number_input("Número de Velas para Médias", value=3, step=1, key="velas_medias", min_value=1)

# Adiciona informações na parte inferior da sidebar
st.sidebar.markdown("""
<div style="position: fixed; bottom: 20px; left: 20px; right: 20px; text-align: center; font-size: 0.8rem; color: #888;">
    <hr style="margin: 10px 0; border-color: #3D3D60;">
    <p>Bot Trader IQ Option v1.0</p>
    <p> 2025 - Todos os direitos reservados</p>
</div>
""", unsafe_allow_html=True)

if st.sidebar.button("💾 Salvar Configuração", use_container_width=True):
    # Obtém a estratégia e ativo selecionados (se disponíveis)
    estrategia = st.session_state.get("estrategia_choice", "MHI")
    ativo = st.session_state.get("ativo_input", "")
    
    # Sanitiza os valores para evitar problemas de codificação
    estrategia = estrategia.replace('ê', 'e').replace('ã', 'a')
    
    try:
        # Lê a configuração existente ou cria uma nova
        try:
            config = ConfigObj('config.txt')
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
        
        st.sidebar.success("✅ Configuração salva em config.txt")
        log_message("Configuração salva em config.txt")
    except Exception as e:
        st.sidebar.error(f"❌ Erro ao salvar configuração: {str(e)}")
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
            
            st.sidebar.success("✅ Configuração salva usando método alternativo!")
        except Exception as e2:
            st.sidebar.error(f"❌ Falha no método alternativo: {str(e2)}")

# -----------------------------------------------------------------------------
# Seção: Conectar na IQ Option
st.markdown("<h2 class='sub-header'>🔌 1 - Conectar na IQ Option</h2>", unsafe_allow_html=True)

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
    
    if st.button("🔑 Conectar", use_container_width=True):
        try:
            with st.spinner("Conectando à IQ Option..."):
                st.session_state.API = IQ_Option(email, senha)
                check, reason = st.session_state.API.connect()
                if check:
                    st.success("✅ Conectado com sucesso!")
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
    st.markdown("<h2 class='sub-header'>📊 2 - Executar Catalogador e Selecionar Estratégia</h2>", unsafe_allow_html=True)
    
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
            if st.button("📈 Executar Catalogador", use_container_width=True):
                try:
                    with st.spinner("Executando catalogador..."):
                        lista_catalog, linha = catag(st.session_state.API)
                        if lista_catalog:
                            st.session_state.lista_catalog = lista_catalog
                            st.session_state.linha_catalog = linha
                            log_message("Catalogador executado com sucesso.")
                            st.success("✅ Catalogador executado com sucesso!")
                        else:
                            st.error("❌ Erro ao executar catalogador.")
                            log_message("Erro ao executar catalogador.")
                except Exception as e:
                    st.error(f" Exceção no catalogador: {str(e)}")
                    log_message("Exceção no catalogador: " + str(e))
        
        with col2:
            estrategia_choice = st.selectbox(
                "Selecione a Estratégia",
                ["MHI", "Torres Gemeas", "MHI M5"],
                key="estrategia_choice",
                help="Escolha a estratégia que deseja utilizar para operar"
            )
        
        # Exibição dos resultados do catalogador
        if "lista_catalog" in st.session_state:
            with st.expander("📋 Resultados do Catalogador", expanded=True):
                # Define os cabeçalhos fixos para a tabela
                headers = ["Estratégia", "Par", "Win%", "Gale1%", "Gale2%"]
                st.markdown(f"```\n{tabulate(st.session_state.lista_catalog, headers=headers, tablefmt='pretty')}\n```")
                
                # Extrair ativos da lista de catalogação
                ativos = [item[1] for item in st.session_state.lista_catalog]  # Índice 1 contém o nome do par
                default_ativo = ativos[0] if ativos else ""
                
                st.markdown("<p style='margin-top:15px;'><b>Selecione o ativo para operar:</b></p>", unsafe_allow_html=True)
                ativo_input = st.selectbox("Ativo", ativos, index=0) if ativos else st.text_input("Digite o ativo que deseja operar:", value=default_ativo)
                
                # Botão para salvar a estratégia e ativo selecionados
                if st.button("💾 Salvar Estratégia e Ativo", use_container_width=True):
                    # Atualiza o arquivo de configuração
                    try:
                        # Lê a configuração existente primeiro
                        try:
                            config = ConfigObj('config.txt')
                        except:
                            # Se o arquivo não existir ou estiver corrompido, cria um novo
                            config = ConfigObj()
                            
                        # Garante que a seção AJUSTES existe
                        if 'AJUSTES' not in config:
                            config['AJUSTES'] = {}
                        
                        # Sanitiza os valores para evitar problemas de codificação
                        estrategia_sanitizada = estrategia_choice.replace('ê', 'e').replace('ã', 'a')
                        
                        # Atualiza as configurações
                        config['AJUSTES']['estrategia'] = estrategia_sanitizada
                        config['AJUSTES']['ativo'] = ativo_input
                        
                        # Salva o arquivo
                        config.filename = 'config.txt'
                        config.write()
                        
                        st.success(f"✅ Estratégia '{estrategia_choice}' e ativo '{ativo_input}' salvos com sucesso!")
                        log_message(f"Estratégia '{estrategia_choice}' e ativo '{ativo_input}' salvos na configuração.")
                    except Exception as e:
                        st.error(f"❌ Erro ao salvar configuração: {str(e)}")
                        log_message(f"Erro ao salvar configuração: {str(e)}")
                        
                        # Tenta uma abordagem alternativa se a primeira falhar
                        try:
                            with open('config.txt', 'w') as f:
                                f.write(f"[AJUSTES]\nestrategia = {estrategia_choice.replace('ê', 'e').replace('ã', 'a')}\nativo = {ativo_input}\n")
                            st.success("✅ Configuração salva usando método alternativo!")
                        except Exception as e2:
                            st.error(f"❌ Falha no método alternativo: {str(e2)}")
        else:
            ativo_input = st.text_input("Digite o ativo que deseja operar:", value="")

# -----------------------------------------------------------------------------
# Função que roda o bot em thread separada, recebendo a API como parâmetro
def run_bot(api):
    global BOT_RUNNING
    
    # Obtém as configurações
    config = ConfigObj('config.txt')
    
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
    
    # Variáveis de controle
    lucro_atual = 0.0
    valor_atual = valor_entrada
    nivel_atual_martingale = 0
    nivel_atual_soros = 0
    
    # Tempo entre operações (em segundos)
    tempo_entre_operacoes = 60  # 1 minuto entre operações
    
    log_message(f"Bot iniciado - Estratégia: {estrategia}, Ativo: {ativo}, Valor: {valor_entrada}")
    
    # Loop principal do bot
    while BOT_RUNNING:
        try:
            # Verificar stop win/loss
            if lucro_atual >= stop_win:
                log_message(f"STOP WIN ATINGIDO: {lucro_atual:.2f}")
                BOT_RUNNING = False
                break
            
            if lucro_atual <= -stop_loss:
                log_message(f"STOP LOSS ATINGIDO: {lucro_atual:.2f}")
                BOT_RUNNING = False
                break
            
            # Lógica de operação baseada na estratégia
            log_message(f"Analisando entrada para {ativo} com estratégia {estrategia}")
            
            # Verificar se o mercado está aberto
            try:
                check_open = api.check_connect()
                if not check_open:
                    log_message("❌ ENTRADA NÃO REALIZADA: Conexão com a IQ Option perdida. Tentando reconectar...")
                    api.connect()
                    time.sleep(5)
                    continue
            except Exception as e:
                log_message(f"❌ ENTRADA NÃO REALIZADA: Erro de conexão - {str(e)}")
                time.sleep(5)
                continue
            
            # Verificar se o ativo está disponível
            try:
                if ativo:
                    ativo_aberto = api.get_all_open_time()
                    if ativo not in ativo_aberto['binary'] or not ativo_aberto['binary'][ativo]['open']:
                        log_message(f"❌ ENTRADA NÃO REALIZADA: Ativo {ativo} não está disponível no momento")
                        
                        # Contar tempo para próxima verificação
                        for i in range(tempo_entre_operacoes, 0, -1):
                            if not BOT_RUNNING:
                                break
                            log_message(f"⏱️ Próxima verificação em {i} segundos...")
                            time.sleep(1)
                        continue
                else:
                    log_message("❌ ENTRADA NÃO REALIZADA: Nenhum ativo selecionado")
                    time.sleep(5)
                    continue
            except Exception as e:
                log_message(f"❌ ENTRADA NÃO REALIZADA: Erro ao verificar disponibilidade do ativo - {str(e)}")
                time.sleep(5)
                continue
            
            # Verificar condições da estratégia
            condicoes_atendidas = False
            motivo_nao_entrada = "Condições da estratégia não atendidas"
            
            # Implementar verificação de acordo com a estratégia selecionada
            if estrategia == "MHI":
                # Lógica para MHI
                try:
                    # Obter velas para análise
                    velas = api.get_candles(ativo, 60, 5, time.time())
                    
                    # Verificar padrão MHI (exemplo simplificado)
                    if len(velas) >= 3:
                        # Verificar se as últimas 3 velas seguem um padrão específico
                        ultimas_cores = [1 if vela['close'] > vela['open'] else 0 for vela in velas[-3:]]
                        
                        # Exemplo: entrar se tiver alternância de cores nas últimas 3 velas
                        if ultimas_cores == [1, 0, 1] or ultimas_cores == [0, 1, 0]:
                            condicoes_atendidas = True
                            direcao = "CALL" if ultimas_cores[-1] == 0 else "PUT"
                        else:
                            motivo_nao_entrada = f"Padrão MHI não identificado. Padrão atual: {ultimas_cores}"
                    else:
                        motivo_nao_entrada = "Dados insuficientes para análise MHI"
                except Exception as e:
                    motivo_nao_entrada = f"Erro na análise MHI: {str(e)}"
            
            elif estrategia == "Torres Gemeas":
                # Lógica para Torres Gemeas (exemplo)
                try:
                    # Obter velas para análise
                    velas = api.get_candles(ativo, 60, 10, time.time())
                    
                    # Verificar padrão Torres Gemeas (exemplo simplificado)
                    if len(velas) >= 5:
                        # Exemplo: verificar se há duas velas consecutivas na mesma direção
                        ultimas_cores = [1 if vela['close'] > vela['open'] else 0 for vela in velas[-5:]]
                        
                        if ultimas_cores[-2] == ultimas_cores[-1]:
                            condicoes_atendidas = True
                            direcao = "PUT" if ultimas_cores[-1] == 1 else "CALL"  # Inversão após duas velas iguais
                        else:
                            motivo_nao_entrada = f"Padrão Torres Gemeas não identificado. Últimas cores: {ultimas_cores[-5:]}"
                    else:
                        motivo_nao_entrada = "Dados insuficientes para análise Torres Gemeas"
                except Exception as e:
                    motivo_nao_entrada = f"Erro na análise Torres Gemeas: {str(e)}"
            
            elif estrategia == "MHI M5":
                # Lógica para MHI M5 (exemplo)
                try:
                    # Obter velas para análise
                    velas = api.get_candles(ativo, 300, 5, time.time())  # M5 = 300 segundos
                    
                    # Verificar padrão MHI M5 (exemplo simplificado)
                    if len(velas) >= 3:
                        # Verificar se as últimas 3 velas seguem um padrão específico
                        ultimas_cores = [1 if vela['close'] > vela['open'] else 0 for vela in velas[-3:]]
                        
                        # Exemplo: entrar se tiver alternância de cores nas últimas 3 velas
                        if ultimas_cores == [1, 0, 1] or ultimas_cores == [0, 1, 0]:
                            condicoes_atendidas = True
                            direcao = "CALL" if ultimas_cores[-1] == 0 else "PUT"
                        else:
                            motivo_nao_entrada = f"Padrão MHI M5 não identificado. Padrão atual: {ultimas_cores}"
                    else:
                        motivo_nao_entrada = "Dados insuficientes para análise MHI M5"
                except Exception as e:
                    motivo_nao_entrada = f"Erro na análise MHI M5: {str(e)}"
            
            else:
                motivo_nao_entrada = f"Estratégia '{estrategia}' não implementada"
            
            # Realizar entrada se condições forem atendidas
            if condicoes_atendidas:
                log_message(f"✅ CONDIÇÕES ATENDIDAS: Realizando entrada {direcao} em {ativo}")
                
                # Implementação da função de compra baseada no script original
                entrada_valor = valor_atual
                
                # Lógica de Soros (baseada no script original)
                if usar_soros:
                    if nivel_atual_soros == 0:
                        entrada_valor = valor_atual
                    elif nivel_atual_soros >= 1 and nivel_atual_soros <= niveis_soros:
                        # Usar o valor acumulado com o lucro anterior
                        entrada_valor = valor_atual  # Já foi ajustado após o WIN anterior
                    elif nivel_atual_soros > niveis_soros:
                        # Reset do soros após atingir o nível máximo
                        nivel_atual_soros = 0
                        entrada_valor = valor_entrada
                else:
                    entrada_valor = valor_atual
                
                # Realizar a compra (com suporte a martingale)
                resultado = None
                valor_compra = entrada_valor
                
                for i in range(nivel_atual_martingale + 1):
                    if i > 0:
                        # Aplicar martingale
                        valor_compra = round(valor_compra * fator_martingale, 2)
                        log_message(f"🔄 MARTINGALE {i}: Aumentando valor para {valor_compra:.2f}")
                    
                    # Executar a compra na API
                    try:
                        log_message(f"🔄 ENTRADA REALIZADA: {ativo}, Direção: {direcao}, Valor: {valor_compra:.2f}")
                        
                        if tipo.lower() == 'digital':
                            status, id = api.buy_digital_spot_v2(ativo, valor_compra, direcao, 1)  # 1 minuto de expiração
                        else:
                            status, id = api.buy(valor_compra, ativo, direcao, 1)  # 1 minuto de expiração
                        
                        if status:
                            log_message(f"✅ Ordem aberta com sucesso{' para gale ' + str(i) if i > 0 else ''}")
                            
                            # Aguardar resultado
                            tempo_espera = 0
                            while tempo_espera < 60:  # Esperar até 60 segundos pelo resultado
                                time.sleep(1)
                                tempo_espera += 1
                                
                                try:
                                    if tipo.lower() == 'digital':
                                        status_ordem, resultado_valor = api.check_win_digital_v2(id)
                                    else:
                                        resultado_valor = api.check_win_v3(id)
                                        status_ordem = True
                                    
                                    if status_ordem:
                                        # Registra o timestamp da operação
                                        timestamp = datetime.now().strftime("%H:%M:%S")
                                        resultado_valor = round(resultado_valor, 2)
                                        
                                        if resultado_valor > 0:
                                            # WIN
                                            resultado = 'WIN'
                                            lucro_atual += resultado_valor
                                            st.session_state.bot_wins += 1
                                            st.session_state.bot_lucro_total += resultado_valor
                                            log_message(f"✅ RESULTADO: WIN +{resultado_valor:.2f}{' no gale ' + str(i) if i > 0 else ''} | Lucro Total: {lucro_atual:.2f}")
                                            
                                            # Registra a operação no histórico
                                            st.session_state.bot_historico.append({
                                                'timestamp': timestamp,
                                                'resultado': 'WIN',
                                                'valor': valor_compra,
                                                'lucro': resultado_valor,
                                                'lucro_acumulado': lucro_atual,
                                                'estrategia': estrategia,
                                                'ativo': ativo,
                                                'direcao': direcao,
                                                'martingale': i if i > 0 else None
                                            })
                                            
                                            # Reset martingale
                                            nivel_atual_martingale = 0
                                            valor_atual = valor_entrada
                                            
                                            # Lógica de Soros
                                            if usar_soros and nivel_atual_soros < niveis_soros:
                                                nivel_atual_soros += 1
                                                valor_atual = valor_atual + resultado_valor
                                                log_message(f"🔄 SOROS: Próxima entrada com {valor_atual:.2f}")
                                            else:
                                                nivel_atual_soros = 0
                                                valor_atual = valor_entrada
                                            
                                            break  # Sai do loop de martingale após um WIN
                                            
                                        elif resultado_valor == 0:
                                            # EMPATE
                                            resultado = 'EMPATE'
                                            st.session_state.bot_empates += 1
                                            log_message(f"🔄 RESULTADO: EMPATE{' no gale ' + str(i) if i > 0 else ''} | Lucro Total: {lucro_atual:.2f}")
                                            
                                            # Registra a operação no histórico
                                            st.session_state.bot_historico.append({
                                                'timestamp': timestamp,
                                                'resultado': 'EMPATE',
                                                'valor': valor_compra,
                                                'lucro': 0,
                                                'lucro_acumulado': lucro_atual,
                                                'estrategia': estrategia,
                                                'ativo': ativo,
                                                'direcao': direcao,
                                                'martingale': i if i > 0 else None
                                            })
                                            
                                            break  # Não continua o martingale em caso de empate
                                            
                                        else:
                                            # LOSS
                                            resultado = 'LOSS'
                                            lucro_atual += resultado_valor  # Resultado negativo
                                            st.session_state.bot_losses += 1
                                            st.session_state.bot_lucro_total += resultado_valor
                                            log_message(f"❌ RESULTADO: LOSS {resultado_valor:.2f}{' no gale ' + str(i) if i > 0 else ''} | Lucro Total: {lucro_atual:.2f}")
                                            
                                            # Registra a operação no histórico
                                            st.session_state.bot_historico.append({
                                                'timestamp': timestamp,
                                                'resultado': 'LOSS',
                                                'valor': valor_compra,
                                                'lucro': resultado_valor,
                                                'lucro_acumulado': lucro_atual,
                                                'estrategia': estrategia,
                                                'ativo': ativo,
                                                'direcao': direcao,
                                                'martingale': i if i > 0 else None
                                            })
                                            
                                            # Reset soros
                                            nivel_atual_soros = 0
                                            
                                            # Continua para o próximo nível de martingale se não for o último
                                            if i < nivel_atual_martingale:
                                                break  # Sai do loop de espera para ir para o próximo martingale
                                        
                                        st.session_state.bot_total_ops += 1
                                        break  # Sai do loop de espera após obter o resultado
                                
                                except Exception as e:
                                    log_message(f"❌ Erro ao verificar resultado: {str(e)}")
                                    if tempo_espera >= 59:  # Se estiver no último segundo de espera
                                        break
                        else:
                            log_message(f"❌ Erro na abertura da ordem: {id}")
                            break  # Sai do loop de martingale em caso de erro
                    
                    except Exception as e:
                        log_message(f"❌ Erro ao realizar entrada: {str(e)}")
                        break  # Sai do loop de martingale em caso de erro
                    
                    # Se teve WIN, sai do loop de martingale
                    if resultado == 'WIN' or resultado == 'EMPATE':
                        break
                
                # Atualiza o nível de martingale para a próxima operação
                if resultado == 'LOSS' and usar_martingale and nivel_atual_martingale < niveis_martingale:
                    nivel_atual_martingale += 1
                    valor_atual = valor_atual * fator_martingale
                    log_message(f"🔄 MARTINGALE: Próxima entrada será com {valor_atual:.2f}")
                elif resultado == 'LOSS':
                    nivel_atual_martingale = 0
                    valor_atual = valor_entrada
            else:
                # Informar o motivo da não entrada
                log_message(f"❌ ENTRADA NÃO REALIZADA: {motivo_nao_entrada}")
            
            # Aguarda intervalo entre operações com contagem regressiva
            log_message(f"⏱️ Aguardando próxima operação...")
            for i in range(tempo_entre_operacoes, 0, -1):
                if not BOT_RUNNING:
                    break
                if i % 10 == 0 or i <= 5:  # Mostrar apenas a cada 10 segundos e nos últimos 5 segundos
                    log_message(f"⏱️ Próxima análise em {i} segundos...")
                time.sleep(1)
            
        except Exception as e:
            log_message(f"❌ Erro na execução do bot: {str(e)}")
            time.sleep(5)

# -----------------------------------------------------------------------------
# Seção: Iniciar Bot e Dashboard de Resultados
if "API" in st.session_state:
    st.markdown("<h2 class='sub-header'>🤖 3 - Iniciar Bot e Acompanhar Resultados</h2>", unsafe_allow_html=True)
    
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
        
        if st.button("▶️ Iniciar Bot", use_container_width=True):
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
                
                # Suprimir todos os avisos
                warnings.filterwarnings("ignore")
                
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
                    
                    # Desativar todos os logs do Streamlit
                    for logger_name in ['streamlit', 'streamlit.runtime', 'streamlit.runtime.scriptrunner']:
                        logging.getLogger(logger_name).setLevel(logging.CRITICAL)
                    
                    # Chamar a função real do bot
                    run_bot(api)
                finally:
                    # Restaurar stderr original
                    sys.stderr = original_stderr

            # Inicia a thread do bot com supressão de avisos
            bot_thread = threading.Thread(target=run_bot_with_warnings_suppressed, args=(api_instance,), daemon=True)
            bot_thread.start()

    st.markdown("<h3 class='sub-header'>📊 Dashboard de Resultados</h3>", unsafe_allow_html=True)
    
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
                label="💰 Lucro Total", 
                value=f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {lucro_total:.2f}",
                delta=None
            )
            
            operacoes_container.metric(
                label="🔄 Operações", 
                value=f"{st.session_state.bot_total_ops}",
                delta=f"✅ {st.session_state.bot_wins} | ❌ {st.session_state.bot_losses} | 🤝 {st.session_state.bot_empates}"
            )
            
            taxa_acerto_container.metric(
                label="📈 Taxa de Acerto", 
                value=f"{taxa_acerto:.1f}%",
                delta=None
            )
            
            stop_win_container.metric(
                label="🎯 Stop Win", 
                value=f"{st.session_state.cifrao if 'cifrao' in st.session_state else '$'} {stop_win}",
                delta=f"{(lucro_total/stop_win)*100:.1f}%" if stop_win > 0 else None
            )
            
            stop_loss_container.metric(
                label="🛑 Stop Loss", 
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
                        labels = ['Vitórias', 'Derrotas', 'Empates']
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
                            <tr><td>Estratégia</td><td>{estrategia_choice}</td></tr>
                            <tr><td>Ativo</td><td>{ativo_input}</td></tr>
                            <tr><td>Valor Entrada</td><td>{valor_entrada}</td></tr>
                            <tr><td>Tipo</td><td>{tipo}</td></tr>
                            <tr><td>Martingale</td><td>{"Sim" if usar_martingale else "Não"}</td></tr>
                            <tr><td>Soros</td><td>{"Sim" if usar_soros else "Não"}</td></tr>
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
