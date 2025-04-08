import streamlit as st
import time
import json
import sys
import threading
from datetime import datetime, timedelta
import pandas as pd
from iqoptionapi.stable_api import IQ_Option
from configobj import ConfigObj
from catalogador_original import catag  # Função de catalogação dos ativos

# =========================
# Configuração da Página
# =========================
st.set_page_config(
    page_title="IQOption Trading Bot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS para formatação
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: 700; color: #4CAF50; text-align: center; }
    .sub-header { font-size: 1.5rem; font-weight: 500; color: #2E7D32; }
    .success { color: #4CAF50; font-weight: 600; }
    .warning { color: #FFC107; font-weight: 600; }
    .error { color: #F44336; font-weight: 600; }
    .info { color: #2196F3; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# Logo
st.markdown("""
<div style="text-align: center;">
    <h1 class="main-header">
        ██████╗ ██╗   ██╗███████╗ ██████╗██████╗ ██╗██████╗ ████████╗
        ██╔══██╗╚██╗ ██╔╝██╔════╝██╔════╝██╔══██╗██║██╔══██╗╚══██╔══╝
        ██████╔╝ ╚████╔╝ ███████╗██║     ██████╔╝██║██████╔╝   ██║   
        ██╔═══╝   ╚██╔╝  ╚════██║██║     ██╔══██╗██║██╔═══╝    ██║   
        ██║        ██║   ███████║╚██████╗██║  ██║██║██║        ██║   
        ╚═╝        ╚═╝   ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝╚═╝        ╚═╝   
    </h1>
    <h3 class="sub-header" style="margin-top: -15px;">IQOption Trading Bot com Interface Streamlit</h3>
</div>
""", unsafe_allow_html=True)

# =========================
# Inicialização do Session State
# =========================
if 'api' not in st.session_state:
    st.session_state.api = None
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'cifrao' not in st.session_state:
    st.session_state.cifrao = "$"
if 'account_balance' not in st.session_state:
    st.session_state.account_balance = 0
if 'log_messages' not in st.session_state:
    st.session_state.log_messages = []
if 'operations' not in st.session_state:
    st.session_state.operations = []
if 'catalog_results' not in st.session_state:
    st.session_state.catalog_results = None
if 'bot_running' not in st.session_state:
    st.session_state.bot_running = False
if 'stop_bot' not in st.session_state:
    st.session_state.stop_bot = False

# Variáveis de configuração (serão carregadas via formulário)
if 'email' not in st.session_state: st.session_state.email = ""
if 'senha' not in st.session_state: st.session_state.senha = ""
if 'tipo' not in st.session_state: st.session_state.tipo = "automatico"
if 'valor_entrada' not in st.session_state: st.session_state.valor_entrada = 3.0
if 'stop_win' not in st.session_state: st.session_state.stop_win = 50.0
if 'stop_loss' not in st.session_state: st.session_state.stop_loss = 70.0
if 'analise_medias' not in st.session_state: st.session_state.analise_medias = "N"
if 'velas_medias' not in st.session_state: st.session_state.velas_medias = 3
if 'usar_martingale' not in st.session_state: st.session_state.usar_martingale = True
if 'niveis_martingale' not in st.session_state: st.session_state.niveis_martingale = 1
if 'fator_martingale' not in st.session_state: st.session_state.fator_martingale = 2.0
if 'usar_soros' not in st.session_state: st.session_state.usar_soros = True
if 'niveis_soros' not in st.session_state: st.session_state.niveis_soros = 1

# =========================
# Funções Auxiliares
# =========================

def add_log(message, level="info"):
    """Adiciona uma mensagem de log com timestamp."""
    st.session_state.log_messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def connect_iqoption(email, password):
    """Conecta à IQOption utilizando as credenciais informadas."""
    st.session_state.api = IQ_Option(email, password)
    check, reason = st.session_state.api.connect()
    if check:
        st.session_state.connected = True
        # Atualiza dados do perfil e saldo
        profile = st.session_state.api.get_profile_ansyc()
        if profile:
            st.session_state.cifrao = str(profile.get('currency_char', '$'))
        st.session_state.account_balance = float(st.session_state.api.get_balance())
        add_log("Conectado com sucesso!")
        return True, "Conectado com sucesso!"
    else:
        st.session_state.connected = False
        add_log(f"Falha na conexão: {reason}", "error")
        return False, reason

def get_payout(api, asset):
    """Obtém os payouts para o ativo informado."""
    profit = api.get_all_profit()
    all_assets = api.get_all_open_time()
    try:
        if all_assets['binary'][asset]['open']:
            binary = round(profit[asset]['binary'], 2) * 100 if profit[asset]['binary'] > 0 else 0
        else:
            binary = 0
    except:
        binary = 0
    try:
        if all_assets['turbo'][asset]['open']:
            turbo = round(profit[asset]['turbo'], 2) * 100 if profit[asset]['turbo'] > 0 else 0
        else:
            turbo = 0
    except:
        turbo = 0
    try:
        if all_assets['digital'][asset]['open']:
            digital = api.get_digital_payout(asset)
        else:
            digital = 0
    except:
        digital = 0
    return binary, turbo, digital

def calculate_moving_average(candles, period):
    total = sum(c['close'] for c in candles[-period:])
    return total / period

def analyze_trend(candles, period):
    ma = calculate_moving_average(candles, period)
    return 'put' if ma > candles[-1]['close'] else 'call'

def make_trade(api, asset, entry_value, direction, expiration, trade_type,
               martingale_levels, martingale_factor, use_soros, soros_levels, stop_win, stop_loss):
    """
    Executa a operação com a lógica de Martingale e Soros, atualizando o placar.
    A função chama os métodos da API para abrir a operação e aguarda o resultado.
    """
    # Define o valor inicial de entrada
    entrada = entry_value
    # Itera pelos níveis de martingale
    for i in range(martingale_levels + 1):
        if st.session_state.stop_bot:
            break
        if i > 0:
            entrada = round(entrada * martingale_factor, 2)
        # Executa a ordem conforme o tipo (digital ou binária)
        if trade_type == 'digital':
            success, trade_id = api.buy_digital_spot_v2(asset, entrada, direction, expiration)
        else:
            success, trade_id = api.buy(entrada, asset, direction, expiration)
        if success:
            add_log(f"Ordem aberta ({'Martingale nível ' + str(i) if i > 0 else 'Ordem inicial'}) para {asset} com entrada {st.session_state.cifrao}{entrada}", "info")
            # Aguarda o resultado da operação
            while True:
                time.sleep(0.1)
                if trade_type == 'digital':
                    status, result = api.check_win_digital_v2(trade_id)
                else:
                    if hasattr(api, 'check_win_v3'):
                        result = api.check_win_v3(trade_id)
                        status = True
                    else:
                        status, result = api.check_win_v2(trade_id)
                if status:
                    result = round(result, 2)
                    st.session_state.account_balance = float(api.get_balance())
                    # Registra a operação no placar
                    st.session_state.operations.append({
                        "Ativo": asset,
                        "Entrada": entrada,
                        "Direção": direction,
                        "Resultado": result,
                        "Horário": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    if result > 0:
                        add_log(f"Resultado: WIN {'(Martingale nível ' + str(i) + ')' if i > 0 else ''} - Lucro: {st.session_state.cifrao}{result}", "success")
                    elif result == 0:
                        add_log(f"Resultado: EMPATE {'(Martingale nível ' + str(i) + ')' if i > 0 else ''} - Valor: {st.session_state.cifrao}{result}", "warning")
                    else:
                        add_log(f"Resultado: LOSS {'(Martingale nível ' + str(i) + ')' if i > 0 else ''} - Perda: {st.session_state.cifrao}{result}", "error")
                    # Verifica as condições de stop win e stop loss
                    if st.session_state.account_balance <= -abs(stop_loss):
                        add_log(f"STOP LOSS atingido: {st.session_state.cifrao}{st.session_state.account_balance}", "error")
                        st.session_state.stop_bot = True
                    if st.session_state.account_balance >= abs(stop_win):
                        add_log(f"STOP WIN atingido: {st.session_state.cifrao}{st.session_state.account_balance}", "success")
                        st.session_state.stop_bot = True
                    # Se houve lucro, interrompe o loop de martingale
                    if result > 0:
                        break
                    break
            break
        else:
            add_log(f"Erro ao abrir ordem: ID {trade_id} para {asset}", "error")

# =========================
# Estratégias de Operação
# Cada função roda em loop (em thread separada) e verifica periodicamente se é o momento de entrada.
# =========================

def run_mhi_strategy(api, asset, entry_value, trade_type, martingale_levels,
                     martingale_factor, use_soros, soros_levels, analyze_mas, mas_candles,
                     stop_win, stop_loss):
    if trade_type == 'automatico':
        binary, turbo, digital = get_payout(api, asset)
        add_log(f"Payouts - Binary: {binary}%, Turbo: {turbo}%, Digital: {digital}%")
        if digital > turbo:
            add_log("Entradas serão realizadas nas digitais", "info")
            trade_type = 'digital'
        elif turbo > digital:
            add_log("Entradas serão realizadas nas binárias", "info")
            trade_type = 'binary'
        else:
            add_log("Par fechado, escolha outro", "error")
            st.session_state.stop_bot = True
            return
    while not st.session_state.stop_bot:
        time.sleep(0.1)
        try:
            st.session_state.account_balance = float(api.get_balance())
        except:
            pass
        # Obtem horário do servidor para determinar o momento de entrada
        minutes = float(datetime.fromtimestamp(api.get_server_timestamp()).strftime('%M.%S')[1:])
        entry_time = True if (minutes >= 4.59 and minutes <= 5.00) or (minutes >= 9.59) else False
        if entry_time:
            add_log(f"Iniciando análise da estratégia MHI para {asset}", "info")
            direction = None
            timeframe = 60
            candles_count = 3
            if analyze_mas == 'S':
                candles = api.get_candles(asset, timeframe, mas_candles, time.time())
                trend = analyze_trend(candles, mas_candles)
            else:
                candles = api.get_candles(asset, timeframe, candles_count, time.time())
            try:
                vela1 = 'Verde' if candles[-3]['open'] < candles[-3]['close'] else 'Vermelha' if candles[-3]['open'] > candles[-3]['close'] else 'Doji'
                vela2 = 'Verde' if candles[-2]['open'] < candles[-2]['close'] else 'Vermelha' if candles[-2]['open'] > candles[-2]['close'] else 'Doji'
                vela3 = 'Verde' if candles[-1]['open'] < candles[-1]['close'] else 'Vermelha' if candles[-1]['open'] > candles[-1]['close'] else 'Doji'
            except Exception as e:
                add_log("Erro ao obter velas para análise", "error")
                continue
            colors = [vela1, vela2, vela3]
            if colors.count('Verde') > colors.count('Vermelha') and 'Doji' not in colors:
                direction = 'put'
            elif colors.count('Verde') < colors.count('Vermelha') and 'Doji' not in colors:
                direction = 'call'
            if analyze_mas == 'S' and direction is not None:
                if direction != trend:
                    direction = 'abortar'
            if direction in ['put', 'call']:
                add_log(f"Velas: {vela1}, {vela2}, {vela3} - Entrada para {direction.upper()}", "info")
                make_trade(api, asset, entry_value, direction, 1, trade_type,
                           martingale_levels, martingale_factor, use_soros, soros_levels, stop_win, stop_loss)
            else:
                if direction == 'abortar':
                    add_log(f"Velas: {vela1}, {vela2}, {vela3} - Entrada abortada (Contra Tendência)", "warning")
                else:
                    add_log(f"Velas: {vela1}, {vela2}, {vela3} - Entrada abortada (Doji detectado)", "warning")
                time.sleep(2)
            add_log("Fim da operação MHI", "info")
        time.sleep(0.5)

def run_torres_gemeas_strategy(api, asset, entry_value, trade_type, martingale_levels,
                                martingale_factor, use_soros, soros_levels, analyze_mas, mas_candles,
                                stop_win, stop_loss):
    if trade_type == 'automatico':
        binary, turbo, digital = get_payout(api, asset)
        add_log(f"Payouts - Binary: {binary}%, Turbo: {turbo}%, Digital: {digital}%")
        if digital > turbo:
            add_log("Entradas serão realizadas nas digitais", "info")
            trade_type = 'digital'
        elif turbo > digital:
            add_log("Entradas serão realizadas nas binárias", "info")
            trade_type = 'binary'
        else:
            add_log("Par fechado, escolha outro", "error")
            st.session_state.stop_bot = True
            return
    while not st.session_state.stop_bot:
        time.sleep(0.1)
        try:
            st.session_state.account_balance = float(api.get_balance())
        except:
            pass
        minutes = float(datetime.fromtimestamp(api.get_server_timestamp()).strftime('%M.%S')[1:])
        entry_time = True if (minutes >= 3.59 and minutes <= 4.00) or (minutes >= 8.59 and minutes <= 9.00) else False
        if entry_time:
            add_log(f"Iniciando análise da estratégia Torres Gêmeas para {asset}", "info")
            direction = None
            timeframe = 60
            candles_count = 4
            if analyze_mas == 'S':
                candles = api.get_candles(asset, timeframe, mas_candles, time.time())
                trend = analyze_trend(candles, mas_candles)
            else:
                candles = api.get_candles(asset, timeframe, candles_count, time.time())
            try:
                # Utiliza a vela de índice -4 para análise
                vela4 = 'Verde' if candles[-4]['open'] < candles[-4]['close'] else 'Vermelha' if candles[-4]['open'] > candles[-4]['close'] else 'Doji'
            except Exception as e:
                add_log("Erro ao obter velas para análise", "error")
                continue
            if vela4 != 'Doji':
                direction = 'call' if vela4 == 'Verde' else 'put'
            if analyze_mas == 'S' and direction is not None:
                if direction != trend:
                    direction = 'abortar'
            if direction in ['put', 'call']:
                add_log(f"Vela de análise: {vela4} - Entrada para {direction.upper()}", "info")
                make_trade(api, asset, entry_value, direction, 1, trade_type,
                           martingale_levels, martingale_factor, use_soros, soros_levels, stop_win, stop_loss)
            else:
                if direction == 'abortar':
                    add_log(f"Vela de análise: {vela4} - Entrada abortada (Contra Tendência)", "warning")
                else:
                    add_log(f"Vela de análise: {vela4} - Entrada abortada (Doji detectado)", "warning")
                time.sleep(2)
            add_log("Fim da operação Torres Gêmeas", "info")
        time.sleep(0.5)

def run_mhi_m5_strategy(api, asset, entry_value, trade_type, martingale_levels,
                        martingale_factor, use_soros, soros_levels, analyze_mas, mas_candles,
                        stop_win, stop_loss):
    if trade_type == 'automatico':
        binary, turbo, digital = get_payout(api, asset)
        add_log(f"Payouts - Binary: {binary}%, Turbo: {turbo}%, Digital: {digital}%")
        if digital > turbo:
            add_log("Entradas serão realizadas nas digitais", "info")
            trade_type = 'digital'
        elif turbo > digital:
            add_log("Entradas serão realizadas nas binárias", "info")
            trade_type = 'binary'
        else:
            add_log("Par fechado, escolha outro", "error")
            st.session_state.stop_bot = True
            return
    while not st.session_state.stop_bot:
        time.sleep(0.1)
        try:
            st.session_state.account_balance = float(api.get_balance())
        except:
            pass
        minutes = float(datetime.fromtimestamp(api.get_server_timestamp()).strftime('%M.%S'))
        entry_time = True if (minutes >= 29.59 and minutes <= 30.00) or minutes == 59.59 else False
        if entry_time:
            add_log(f"Iniciando análise da estratégia MHI M5 para {asset}", "info")
            direction = None
            timeframe = 300
            candles_count = 3
            if analyze_medias == 'S':
                candles = api.get_candles(asset, timeframe, mas_candles, time.time())
                trend = analyze_trend(candles, mas_candles)
            else:
                candles = api.get_candles(asset, timeframe, candles_count, time.time())
            try:
                vela1 = 'Verde' if candles[-3]['open'] < candles[-3]['close'] else 'Vermelha' if candles[-3]['open'] > candles[-3]['close'] else 'Doji'
                vela2 = 'Verde' if candles[-2]['open'] < candles[-2]['close'] else 'Vermelha' if candles[-2]['open'] > candles[-2]['close'] else 'Doji'
                vela3 = 'Verde' if candles[-1]['open'] < candles[-1]['close'] else 'Vermelha' if candles[-1]['open'] > candles[-1]['close'] else 'Doji'
            except Exception as e:
                add_log("Erro ao obter velas para análise", "error")
                continue
            colors = [vela1, vela2, vela3]
            if colors.count('Verde') > colors.count('Vermelha') and 'Doji' not in colors:
                direction = 'put'
            elif colors.count('Verde') < colors.count('Vermelha') and 'Doji' not in colors:
                direction = 'call'
            if analyze_mas == 'S' and direction is not None:
                if direction != trend:
                    direction = 'abortar'
            if direction in ['put', 'call']:
                add_log(f"Velas: {vela1}, {vela2}, {vela3} - Entrada para {direction.upper()}", "info")
                make_trade(api, asset, entry_value, direction, 5, trade_type,
                           martingale_levels, martingale_factor, use_soros, soros_levels, stop_win, stop_loss)
            else:
                if direction == 'abortar':
                    add_log(f"Velas: {vela1}, {vela2}, {vela3} - Entrada abortada (Contra Tendência)", "warning")
                else:
                    add_log(f"Velas: {vela1}, {vela2}, {vela3} - Entrada abortada (Doji detectado)", "warning")
                time.sleep(2)
            add_log("Fim da operação MHI M5", "info")
        time.sleep(0.5)

# =========================
# Interface do Usuário (Frontend)
# =========================

st.sidebar.header("Configurações da Operação")
with st.sidebar.form(key='config_form'):
    st.text_input("Email", key="input_email", value=st.session_state.email)
    st.text_input("Senha", key="input_senha", type="password", value=st.session_state.senha)
    account_type = st.selectbox("Tipo de conta", ["PRACTICE", "REAL"], index=0)
    st.selectbox("Tipo de operação", ["automatico", "digital", "binary"], key="input_tipo", index=0)
    st.number_input("Valor de entrada", key="input_valor_entrada", value=st.session_state.valor_entrada, min_value=0.1)
    st.number_input("Stop Win", key="input_stop_win", value=st.session_state.stop_win)
    st.number_input("Stop Loss", key="input_stop_loss", value=st.session_state.stop_loss)
    st.selectbox("Analisar Médias", ["S", "N"], key="input_analise_medias", index=1)
    st.number_input("Número de velas para médias", key="input_velas_medias", value=st.session_state.velas_medias, min_value=1)
    st.checkbox("Usar Martingale", key="input_usar_martingale", value=st.session_state.usar_martingale)
    st.number_input("Níveis de Martingale", key="input_niveis_martingale", value=st.session_state.niveis_martingale, min_value=0)
    st.number_input("Fator de Martingale", key="input_fator_martingale", value=st.session_state.fator_martingale, step=0.1)
    st.checkbox("Usar Soros", key="input_usar_soros", value=st.session_state.usar_soros)
    st.number_input("Níveis de Soros", key="input_niveis_soros", value=st.session_state.niveis_soros, min_value=0)
    submit_config = st.form_submit_button("Salvar Configurações")
    
if submit_config:
    st.session_state.email = st.session_state.input_email
    st.session_state.senha = st.session_state.input_senha
    st.session_state.tipo = st.session_state.input_tipo
    st.session_state.valor_entrada = st.session_state.input_valor_entrada
    st.session_state.stop_win = st.session_state.input_stop_win
    st.session_state.stop_loss = st.session_state.input_stop_loss
    st.session_state.analise_medias = st.session_state.input_analise_medias
    st.session_state.velas_medias = st.session_state.input_velas_medias
    st.session_state.usar_martingale = st.session_state.input_usar_martingale
    st.session_state.niveis_martingale = st.session_state.input_niveis_martingale
    st.session_state.fator_martingale = st.session_state.input_fator_martingale
    st.session_state.usar_soros = st.session_state.input_usar_soros
    st.session_state.niveis_soros = st.session_state.input_niveis_soros
    add_log("Configurações salvas.")

st.sidebar.markdown("---")
# Botão para conectar à IQOption
if st.sidebar.button("Conectar IQOption"):
    if st.session_state.email != "" and st.session_state.senha != "":
        success, msg = connect_iqoption(st.session_state.email, st.session_state.senha)
        if success:
            st.sidebar.success(msg)
        else:
            st.sidebar.error(msg)
    else:
        st.sidebar.error("Preencha os dados de login.")

# Se conectado, exibe informações e permite catalogação
if st.session_state.connected:
    st.sidebar.markdown(f"**Saldo:** {st.session_state.cifrao}{st.session_state.account_balance}")
    if st.sidebar.button("Catalogar Ativos"):
        catalog, linha = catag(st.session_state.api)
        st.session_state.catalog_results = catalog
        st.sidebar.success("Catalogação concluída!")
    if st.session_state.catalog_results:
        assets = [row[1] for row in st.session_state.catalog_results]
        strategy_options = ["MHI", "Torres Gêmeas", "MHI M5"]
        selected_asset = st.selectbox("Selecione o ativo", options=assets)
        selected_strategy = st.selectbox("Selecione a estratégia", options=strategy_options)
        col1, col2 = st.columns(2)
        if col1.button("Iniciar Bot"):
            st.session_state.stop_bot = False
            # Seleciona a função de estratégia conforme a escolha
            if selected_strategy == "MHI":
                bot_func = run_mhi_strategy
            elif selected_strategy == "Torres Gêmeas":
                bot_func = run_torres_gemeas_strategy
            elif selected_strategy == "MHI M5":
                bot_func = run_mhi_m5_strategy
            else:
                bot_func = run_mhi_strategy
            # Inicia a thread do bot
            st.session_state.bot_thread = threading.Thread(target=bot_func, args=(
                st.session_state.api,
                selected_asset,
                st.session_state.valor_entrada,
                st.session_state.tipo,
                st.session_state.niveis_martingale,
                st.session_state.fator_martingale,
                st.session_state.usar_soros,
                st.session_state.niveis_soros,
                st.session_state.analise_medias,
                st.session_state.velas_medias,
                st.session_state.stop_win,
                st.session_state.stop_loss
            ))
            st.session_state.bot_thread.start()
            st.session_state.bot_running = True
            add_log("Bot iniciado.")
        if col2.button("Pausar Bot"):
            st.session_state.stop_bot = True
            if st.session_state.bot_thread:
                st.session_state.bot_thread.join(timeout=1)
            st.session_state.bot_running = False
            add_log("Bot pausado.")

# =========================
# Exibição do Placar e Logs
# =========================
st.header("Placar de Operações")
if st.session_state.operations:
    df_ops = pd.DataFrame(st.session_state.operations)
    st.dataframe(df_ops)
else:
    st.write("Nenhuma operação realizada ainda.")

st.header("Logs")
for log in st.session_state.log_messages:
    st.write(log)
