import streamlit as st
import time
import json
import sys
from datetime import datetime, timedelta
from configobj import ConfigObj
import pandas as pd
import threading
import matplotlib.pyplot as plt
from iqoptionapi.stable_api import IQ_Option
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import base64
from io import BytesIO

# Set page configuration
st.set_page_config(
    page_title="IQOption Trading Bot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #4CAF50;
        margin-bottom: 1rem;
        text-align: center;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: 500;
        color: #2E7D32;
        margin-bottom: 0.5rem;
    }
    .success {
        color: #4CAF50;
        font-weight: 600;
    }
    .warning {
        color: #FFC107;
        font-weight: 600;
    }
    .error {
        color: #F44336;
        font-weight: 600;
    }
    .info {
        color: #2196F3;
        font-weight: 600;
    }
    .metrics-container {
        background-color: #f9f9f9;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .stButton>button {
        width: 100%;
        font-weight: 600;
    }
    .stSelectbox>div>div>div {
        background-color: #f1f8e9;
    }
    .stNumberInput>div>div>div {
        background-color: #f1f8e9;
    }
    .stTextInput>div>div>div {
        background-color: #f1f8e9;
    }
    .css-1d391kg {
        padding-top: 3rem;
    }
</style>
""", unsafe_allow_html=True)

# =========================
# Inicialização do Session State
# =========================
if 'api' not in st.session_state:
    st.session_state.api = None
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'account_type' not in st.session_state:
    st.session_state.account_type = None
if 'catalog_results' not in st.session_state:
    st.session_state.catalog_results = None
if 'bot_running' not in st.session_state:
    st.session_state.bot_running = False
if 'stop_bot' not in st.session_state:
    st.session_state.stop_bot = False
if 'lucro_total' not in st.session_state:
    st.session_state.lucro_total = 0
if 'operations' not in st.session_state:
    st.session_state.operations = []
if 'bot_thread' not in st.session_state:
    st.session_state.bot_thread = None
if 'selected_asset' not in st.session_state:
    st.session_state.selected_asset = None
if 'selected_strategy' not in st.session_state:
    st.session_state.selected_strategy = None
if 'cifrao' not in st.session_state:
    st.session_state.cifrao = "$"
if 'strategy_results' not in st.session_state:
    st.session_state.strategy_results = {"win": 0, "loss": 0, "draw": 0}
if 'last_operation_time' not in st.session_state:
    st.session_state.last_operation_time = None
if 'nivel_soros' not in st.session_state:
    st.session_state.nivel_soros = 0
if 'valor_soros' not in st.session_state:
    st.session_state.valor_soros = 0
if 'lucro_op_atual' not in st.session_state:
    st.session_state.lucro_op_atual = 0
if 'candles_data' not in st.session_state:
    st.session_state.candles_data = None
if 'account_balance' not in st.session_state:
    st.session_state.account_balance = 0
if 'log_messages' not in st.session_state:
    st.session_state.log_messages = []

# =========================
# Função: Wrapper para get_candles
# =========================
def safe_get_candles(api, pair, timeframe, count, end_time):
    attempts = 0
    candles = None
    while attempts < 3 and not candles:
        try:
            candles = api.get_candles(pair, timeframe, count, end_time)
            if candles:
                return candles
        except Exception as e:
            add_log(f"Erro get_candles para {pair}: {str(e)}. Tentando reconectar...", "error")
            try:
                api.connect()
                # Se houver indicação de qual conta usar, pode ser passado via st.session_state.account_type
                if st.session_state.account_type:
                    api.change_balance(st.session_state.account_type)
            except Exception as e2:
                add_log(f"Erro na reconexão: {str(e2)}", "error")
        attempts += 1
        time.sleep(2)
    return candles

# =========================
# Funções Auxiliares
# =========================

def add_log(message, level="info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.log_messages.append((timestamp, level, message))
    with st.container():
        for time_stamp, lvl, msg in reversed(st.session_state.log_messages[-10:]):
            if lvl == "info":
                st.markdown(f"<div class='info'>[{time_stamp}] {msg}</div>", unsafe_allow_html=True)
            elif lvl == "warning":
                st.markdown(f"<div class='warning'>[{time_stamp}] {msg}</div>", unsafe_allow_html=True)
            elif lvl == "error":
                st.markdown(f"<div class='error'>[{time_stamp}] {msg}</div>", unsafe_allow_html=True)
            elif lvl == "success":
                st.markdown(f"<div class='success'>[{time_stamp}] {msg}</div>", unsafe_allow_html=True)

def connect_iqoption(email, password):
    st.session_state.api = IQ_Option(email, password)
    check, reason = st.session_state.api.connect()
    if check:
        st.session_state.connected = True
        # Atualiza dados do perfil e saldo
        profile = st.session_state.api.get_profile_ansyc()
        if profile:
            st.session_state.cifrao = str(profile.get('currency_char', '$'))
        st.session_state.account_balance = float(st.session_state.api.get_balance())
        add_log("Conectado com sucesso!", "success")
        return True, "Conectado com sucesso!"
    else:
        st.session_state.connected = False
        add_log(f"Falha na conexão: {reason}", "error")
        if "invalid_credentials" in reason:
            return False, "Email ou senha incorreta"
        else:
            return False, f"Houve um problema na conexão: {reason}"

def change_account(account_type):
    if st.session_state.api:
        st.session_state.api.change_balance(account_type)
        st.session_state.account_type = account_type
        profile = json.loads(json.dumps(st.session_state.api.get_profile_ansyc()))
        st.session_state.cifrao = str(profile['currency_char'])
        st.session_state.account_balance = float(st.session_state.api.get_balance())
        return True, f"Conta {account_type} selecionada. Saldo atual: {st.session_state.cifrao}{st.session_state.account_balance}"
    return False, "Você precisa se conectar primeiro!"

def get_open_pairs(api):
    all_assets = api.get_all_open_time()
    pairs = []
    for pair in all_assets['digital']:
        if all_assets['digital'][pair]['open']:
            pairs.append(pair)
    for pair in all_assets['turbo']:
        if all_assets['turbo'][pair]['open'] and pair not in pairs:
            pairs.append(pair)
    return pairs

def analyze_candles(candles, strategy_type):
    results = {'doji': 0, 'win': 0, 'loss': 0, 'gale1': 0, 'gale2': 0}
    for i in range(2, len(candles)):
        minutes = float(datetime.fromtimestamp(candles[i]['from']).strftime('%M')[1:])
        if strategy_type == 'mhi' and (minutes == 5 or minutes == 0):
            analyze_mhi(candles, i, results)
        elif strategy_type == 'torres' and (minutes == 4 or minutes == 9):
            analyze_torres(candles, i, results)
        elif strategy_type == 'mhi_m5' and (minutes == 30 or minutes == 0):
            analyze_mhi(candles, i, results, timeframe=300)
    return results

def analyze_mhi(candles, i, results, timeframe=60):
    try:
        vela1 = 'Verde' if candles[i-3]['open'] < candles[i-3]['close'] else 'Vermelha'
        vela2 = 'Verde' if candles[i-2]['open'] < candles[i-2]['close'] else 'Vermelha'
        vela3 = 'Verde' if candles[i-1]['open'] < candles[i-1]['close'] else 'Vermelha'
        if vela1 == 'Doji' or vela2 == 'Doji' or vela3 == 'Doji':
            results['doji'] += 1
            return
        direcao = 'put' if [vela1, vela2, vela3].count('Verde') > [vela1, vela2, vela3].count('Vermelha') else 'call'
        entrada1 = 'Verde' if candles[i]['open'] < candles[i]['close'] else ('Doji' if candles[i]['open'] == candles[i]['close'] else 'Vermelha')
        entrada2 = 'Verde' if candles[i+1]['open'] < candles[i+1]['close'] else ('Doji' if candles[i+1]['open'] == candles[i+1]['close'] else 'Vermelha')
        entrada3 = 'Verde' if candles[i+2]['open'] < candles[i+2]['close'] else ('Doji' if candles[i+2]['open'] == candles[i+2]['close'] else 'Vermelha')
        entradas = [entrada1, entrada2, entrada3]
        update_results(entradas, direcao, results)
    except Exception as e:
        add_log(f"Erro em analyze_mhi: {str(e)}", "error")
        pass

def analyze_torres(candles, i, results):
    try:
        vela1 = 'Verde' if candles[i-4]['open'] < candles[i-4]['close'] else 'Vermelha'
        if vela1 == 'Doji':
            results['doji'] += 1
            return
        direcao = 'call' if vela1 == 'Verde' else 'put'
        entrada1 = 'Verde' if candles[i]['open'] < candles[i]['close'] else ('Doji' if candles[i]['open'] == candles[i]['close'] else 'Vermelha')
        entrada2 = 'Verde' if candles[i+1]['open'] < candles[i+1]['close'] else ('Doji' if candles[i+1]['open'] == candles[i+1]['close'] else 'Vermelha')
        entrada3 = 'Verde' if candles[i+2]['open'] < candles[i+2]['close'] else ('Doji' if candles[i+2]['open'] == candles[i+2]['close'] else 'Vermelha')
        entradas = [entrada1, entrada2, entrada3]
        update_results(entradas, direcao, results)
    except Exception as e:
        add_log(f"Erro em analyze_torres: {str(e)}", "error")
        pass

def update_results(entradas, direcao, results):
    expected_color = 'Verde' if direcao == 'call' else 'Vermelha'
    if entradas[0] == expected_color:
        results['win'] += 1
    elif entradas[1] == expected_color:
        results['gale1'] += 1
    elif entradas[2] == expected_color:
        results['gale2'] += 1
    else:
        results['loss'] += 1
    return results

def calculate_percentages(results):
    total_entries = results['win'] + results['loss'] + results['gale1'] + results['gale2']
    if total_entries == 0:
        return [0, 0, 0]
    win_rate = round(results['win'] / total_entries * 100, 2)
    gale1_rate = round((results['win'] + results['gale1']) / total_entries * 100, 2)
    gale2_rate = round((results['win'] + results['gale1'] + results['gale2']) / total_entries * 100, 2)
    return [win_rate, gale1_rate, gale2_rate]

def get_results(api, pairs, progress_bar=None):
    timeframe = 60
    qnt_velas = 120
    qnt_velas_m5 = 146
    strategies = ['mhi', 'torres', 'mhi_m5']
    results = []
    
    total_operations = len(strategies) * len(pairs)
    operation_count = 0
    
    for strategy in strategies:
        for pair in pairs:
            if progress_bar:
                operation_count += 1
                progress_bar.progress(operation_count / total_operations)
            attempts = 0
            candles = None
            while attempts < 3 and not candles:
                candles = safe_get_candles(api, pair, timeframe, qnt_velas if strategy != 'mhi_m5' else qnt_velas_m5, time.time())
                if not candles:
                    add_log(f"⚠️ Tentativa {attempts+1}: falha ao obter velas de {pair}. Tentando reconectar...", "warning")
                    api.connect()
                    if st.session_state.account_type:
                        api.change_balance(st.session_state.account_type)
                    time.sleep(2)
                    attempts += 1
            if candles:
                strategy_results = analyze_candles(candles, strategy)
                percentages = calculate_percentages(strategy_results)
                results.append([strategy.upper(), pair] + percentages)
                time.sleep(0.5)
            else:
                add_log(f"❌ Não foi possível obter os dados do ativo {pair} após múltiplas tentativas.", "error")
    return results

def get_payout(api, pair):
    profit = api.get_all_profit()
    all_asset = api.get_all_open_time()
    try:
        if all_asset['binary'][pair]['open']:
            binary = round(profit[pair]['binary'], 2) * 100 if profit[pair]['binary'] > 0 else 0
        else:
            binary = 0
    except:
        binary = 0
    try:
        if all_asset['turbo'][pair]['open']:
            turbo = round(profit[pair]['turbo'], 2) * 100 if profit[pair]['turbo'] > 0 else 0
        else:
            turbo = 0
    except:
        turbo = 0
    try:
        if all_asset['digital'][pair]['open']:
            digital = api.get_digital_payout(pair)
        else:
            digital = 0
    except:
        digital = 0
    return binary, turbo, digital

def check_stop_conditions(valor_entrada, stop_win, stop_loss):
    if st.session_state.lucro_total <= float('-' + str(abs(stop_loss))):
        add_log(f"🛑 STOP LOSS BATIDO: {st.session_state.cifrao}{st.session_state.lucro_total}", "error")
        st.session_state.stop_bot = True
        return False
    if st.session_state.lucro_total >= float(abs(stop_win)):
        add_log(f"🎉 STOP WIN BATIDO: {st.session_state.cifrao}{st.session_state.lucro_total}", "success")
        st.session_state.stop_bot = True
        return False
    return True

def calculate_moving_average(candles, period):
    total = sum(c['close'] for c in candles[-period:])
    return total / period

def analyze_trend(candles, period):
    ma = calculate_moving_average(candles, period)
    return 'put' if ma > candles[-1]['close'] else 'call'

# =========================
# Estratégias de Operação
# =========================

def run_mhi_strategy(api, asset, entry_value, trade_type, martingale_levels, martingale_factor, use_soros, soros_levels, analyze_mas, mas_candles, stop_win, stop_loss):
    if trade_type == 'automatico':
        binary, turbo, digital = get_payout(api, asset)
        add_log(f"Payouts - Binary: {binary}%, Turbo: {turbo}%, Digital: {digital}%", "info")
        if digital > turbo:
            add_log("Suas entradas serão realizadas nas digitais", "info")
            trade_type = 'digital'
        elif turbo > digital:
            add_log("Suas entradas serão realizadas nas binárias", "info")
            trade_type = 'binary'
        else:
            add_log("Par fechado, escolha outro", "error")
            st.session_state.stop_bot = True
            return
    candles_data = safe_get_candles(api, asset, 60, 20, time.time())
    st.session_state.candles_data = candles_data
    while not st.session_state.stop_bot:
        time.sleep(0.1)
        try:
            st.session_state.account_balance = float(api.get_balance())
        except:
            pass
        minutes = float(datetime.fromtimestamp(api.get_server_timestamp()).strftime('%M.%S')[1:])
        entry_time = True if (minutes >= 4.59 and minutes <= 5.00) or minutes >= 9.59 else False
        if entry_time:
            add_log(f"⏰ Iniciando análise da estratégia MHI para {asset}", "info")
            direction = None
            timeframe = 60
            candles_count = 3
            if analyze_mas == 'S':
                candles = safe_get_candles(api, asset, timeframe, mas_candles, time.time())
                trend = analyze_trend(candles, mas_candles)
            else:
                candles = safe_get_candles(api, asset, timeframe, candles_count, time.time())
            st.session_state.candles_data = candles
            try:
                vela1 = 'Verde' if candles[-3]['open'] < candles[-3]['close'] else ('Vermelha' if candles[-3]['open'] > candles[-3]['close'] else 'Doji')
                vela2 = 'Verde' if candles[-2]['open'] < candles[-2]['close'] else ('Vermelha' if candles[-2]['open'] > candles[-2]['close'] else 'Doji')
                vela3 = 'Verde' if candles[-1]['open'] < candles[-1]['close'] else ('Vermelha' if candles[-1]['open'] > candles[-1]['close'] else 'Doji')
            except Exception as e:
                add_log("Erro ao obter velas para análise: " + str(e), "error")
                continue
            colors = [vela1, vela2, vela3]
            if colors.count('Verde') > colors.count('Vermelha') and colors.count('Doji') == 0:
                direction = 'put'
            elif colors.count('Verde') < colors.count('Vermelha') and colors.count('Doji') == 0:
                direction = 'call'
            if analyze_mas == 'S' and direction is not None:
                if direction != trend:
                    direction = 'abortar'
            if direction in ['put', 'call']:
                add_log(f"🕯️ Velas: {vela1}, {vela2}, {vela3} - Entrada para {direction.upper()}", "info")
                make_trade(api, asset, entry_value, direction, 1, trade_type, martingale_levels, martingale_factor, use_soros, soros_levels, stop_win, stop_loss)
            else:
                if direction == 'abortar':
                    add_log(f"🕯️ Velas: {vela1}, {vela2}, {vela3}", "warning")
                    add_log("⚠️ Entrada abortada - Contra Tendência.", "warning")
                else:
                    add_log(f"🕯️ Velas: {vela1}, {vela2}, {vela3}", "warning")
                    add_log("⚠️ Entrada abortada - Foi encontrado um doji na análise.", "warning")
                time.sleep(2)
            add_log("➖" * 30, "info")
        time.sleep(0.5)

def run_torres_gemeas_strategy(api, asset, entry_value, trade_type, martingale_levels, martingale_factor, use_soros, soros_levels, analyze_mas, mas_candles, stop_win, stop_loss):
    if trade_type == 'automatico':
        binary, turbo, digital = get_payout(api, asset)
        add_log(f"Payouts - Binary: {binary}%, Turbo: {turbo}%, Digital: {digital}%", "info")
        if digital > turbo:
            add_log("Suas entradas serão realizadas nas digitais", "info")
            trade_type = 'digital'
        elif turbo > digital:
            add_log("Suas entradas serão realizadas nas binárias", "info")
            trade_type = 'binary'
        else:
            add_log("Par fechado, escolha outro", "error")
            st.session_state.stop_bot = True
            return
    candles_data = safe_get_candles(api, asset, 60, 20, time.time())
    st.session_state.candles_data = candles_data
    while not st.session_state.stop_bot:
        time.sleep(0.1)
        try:
            st.session_state.account_balance = float(api.get_balance())
        except:
            pass
        minutes = float(datetime.fromtimestamp(api.get_server_timestamp()).strftime('%M.%S')[1:])
        entry_time = True if (minutes >= 3.59 and minutes <= 4.00) or (minutes >= 8.59 and minutes <= 9.00) else False
        if entry_time:
            add_log(f"⏰ Iniciando análise da estratégia Torres Gêmeas para {asset}", "info")
            direction = None
            timeframe = 60
            candles_count = 4
            if analyze_mas == 'S':
                candles = safe_get_candles(api, asset, timeframe, mas_candles, time.time())
                trend = analyze_trend(candles, mas_candles)
            else:
                candles = safe_get_candles(api, asset, timeframe, candles_count, time.time())
            st.session_state.candles_data = candles
            try:
                vela4 = 'Verde' if candles[-4]['open'] < candles[-4]['close'] else ('Vermelha' if candles[-4]['open'] > candles[-4]['close'] else 'Doji')
            except Exception as e:
                add_log("Erro ao obter vela para análise: " + str(e), "error")
                continue
            if vela4 != 'Doji':
                direction = 'call' if vela4 == 'Verde' else 'put'
            if analyze_mas == 'S' and direction is not None:
                if direction != trend:
                    direction = 'abortar'
            if direction in ['put', 'call']:
                add_log(f"🕯️ Vela de análise: {vela4} - Entrada para {direction.upper()}", "info")
                make_trade(api, asset, entry_value, direction, 1, trade_type, martingale_levels, martingale_factor, use_soros, soros_levels, stop_win, stop_loss)
            else:
                if direction == 'abortar':
                    add_log(f"🕯️ Vela de análise: {vela4}", "warning")
                    add_log("⚠️ Entrada abortada - Contra Tendência.", "warning")
                else:
                    add_log(f"🕯️ Vela de análise: {vela4}", "warning")
                    add_log("⚠️ Entrada abortada - Foi encontrado um doji na análise.", "warning")
                time.sleep(2)
            add_log("➖" * 30, "info")
        time.sleep(0.5)

def run_mhi_m5_strategy(api, asset, entry_value, trade_type, martingale_levels, martingale_factor, use_soros, soros_levels, analyze_mas, mas_candles, stop_win, stop_loss):
    if trade_type == 'automatico':
        binary, turbo, digital = get_payout(api, asset)
        add_log(f"Payouts - Binary: {binary}%, Turbo: {turbo}%, Digital: {digital}%", "info")
        if digital > turbo:
            add_log("Suas entradas serão realizadas nas digitais", "info")
            trade_type = 'digital'
        elif turbo > digital:
            add_log("Suas entradas serão realizadas nas binárias", "info")
            trade_type = 'binary'
        else:
            add_log("Par fechado, escolha outro", "error")
            st.session_state.stop_bot = True
            return
    candles_data = safe_get_candles(api, asset, 300, 20, time.time())
    st.session_state.candles_data = candles_data
    while not st.session_state.stop_bot:
        time.sleep(0.1)
        try:
            st.session_state.account_balance = float(api.get_balance())
        except:
            pass
        minutes = float(datetime.fromtimestamp(api.get_server_timestamp()).strftime('%M.%S'))
        entry_time = True if (minutes >= 29.59 and minutes <= 30.00) or minutes == 59.59 else False
        if entry_time:
            add_log(f"⏰ Iniciando análise da estratégia MHI M5 para {asset}", "info")
            direction = None
            timeframe = 300
            candles_count = 3
            if analyze_mas == 'S':
                candles = safe_get_candles(api, asset, timeframe, mas_candles, time.time())
                trend = analyze_trend(candles, mas_candles)
            else:
                candles = safe_get_candles(api, asset, timeframe, candles_count, time.time())
            st.session_state.candles_data = candles
            try:
                vela1 = 'Verde' if candles[-3]['open'] < candles[-3]['close'] else ('Vermelha' if candles[-3]['open'] > candles[-3]['close'] else 'Doji')
                vela2 = 'Verde' if candles[-2]['open'] < candles[-2]['close'] else ('Vermelha' if candles[-2]['open'] > candles[-2]['close'] else 'Doji')
                vela3 = 'Verde' if candles[-1]['open'] < candles[-1]['close'] else ('Vermelha' if candles[-1]['open'] > candles[-1]['close'] else 'Doji')
            except Exception as e:
                add_log("Erro ao obter velas para análise: " + str(e), "error")
                continue
            colors = [vela1, vela2, vela3]
            if colors.count('Verde') > colors.count('Vermelha') and colors.count('Doji') == 0:
                direction = 'put'
            elif colors.count('Verde') < colors.count('Vermelha') and colors.count('Doji') == 0:
                direction = 'call'
            if analyze_mas == 'S' and direction is not None:
                if direction != trend:
                    direction = 'abortar'
            if direction in ['put', 'call']:
                add_log(f"🔧 Velas: {vela1}, {vela2}, {vela3} - Entrada para {direction.upper()}", "info")
                make_trade(api, asset, entry_value, direction, 5, trade_type, martingale_levels, martingale_factor, use_soros, soros_levels, stop_win, stop_loss)
            else:
                if direction == 'abortar':
                    add_log(f"🔧 Velas: {vela1}, {vela2}, {vela3}", "warning")
                    add_log("⚠️ Entrada abortada - Contra Tendência.", "warning")
                else:
                    add_log(f"🔧 Velas: {vela1}, {vela2}, {vela3}", "warning")
                    add_log("⚠️ Entrada abortada - Foi encontrado um doji na análise.", "warning")
                time.sleep(2)
            add_log("➖" * 30, "info")
        time.sleep(0.5)

def make_trade(api, asset, entry_value, direction, expiration, trade_type, martingale_levels, martingale_factor, use_soros, soros_levels, stop_win, stop_loss):
    lucro_total = 0
    nivel_soros = st.session_state.nivel_soros
    valor_soros = st.session_state.valor_soros
    lucro_op_atual = 0
    entrada = entry_value
    if use_soros and nivel_soros > 0:
        entrada += valor_soros
    for gale in range(martingale_levels + 1):
        if gale > 0:
            entrada = round(entrada * martingale_factor, 2)
        if trade_type == 'digital':
            success, trade_id = api.buy_digital_spot_v2(asset, entrada, direction, expiration)
        else:
            success, trade_id = api.buy(entrada, asset, direction, expiration)
        if success:
            add_log(f"💰 Ordem aberta {'(Gale ' + str(gale) + ')' if gale > 0 else ''} | Par: {asset} | Valor: {st.session_state.cifrao}{entrada}", "info")
            while True:
                time.sleep(0.1)
                if trade_type == 'digital':
                    status, result = api.check_win_digital_v2(trade_id)
                else:
                    result = api.check_win_v3(trade_id)
                    status = True
                if status:
                    result = round(result, 2)
                    lucro_total += result
                    valor_soros += result
                    lucro_op_atual += result
                    st.session_state.lucro_total += result
                    if result > 0:
                        st.session_state.strategy_results['win'] += 1
                        add_log(f"✅ WIN {'(Gale ' + str(gale) + ')' if gale > 0 else ''} | Lucro: {st.session_state.cifrao}{result}", "success")
                    elif result == 0:
                        st.session_state.strategy_results['draw'] += 1
                        add_log(f"🔄 EMPATE {'(Gale ' + str(gale) + ')' if gale > 0 else ''}", "warning")
                    else:
                        st.session_state.strategy_results['loss'] += 1
                        add_log(f"❌ LOSS {'(Gale ' + str(gale) + ')' if gale > 0 else ''} | Perda: {st.session_state.cifrao}{abs(result)}", "error")
                    check_stop_conditions(entry_value, stop_win, stop_loss)
                    break
            if result > 0:
                break
        else:
            add_log(f"❌ Erro ao abrir ordem no ativo {asset}", "error")
    if use_soros:
        if lucro_op_atual > 0:
            st.session_state.nivel_soros += 1
        else:
            st.session_state.valor_soros = 0
            st.session_state.nivel_soros = 0

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
    add_log("Configurações salvas.", "success")

st.sidebar.markdown("---")
# Botão para conectar à IQOption
if st.sidebar.button("Conectar IQOption"):
    if st.session_state.email != "" and st.session_state.senha != "":
        success, msg = connect_iqoption(st.session_state.email, st.session_state.senha)
        if success:
            st.sidebar.success(msg)
            st.session_state.account_type = account_type  # Salva o tipo de conta selecionado.
        else:
            st.sidebar.error(msg)
    else:
        st.sidebar.error("Preencha os dados de login.")

# Se conectado, exibe informações e permite catalogação
if st.session_state.connected:
    st.sidebar.markdown(f"**Saldo:** {st.session_state.cifrao}{st.session_state.account_balance}")
    if st.sidebar.button("Catalogar Ativos"):
        try:
            catalog, linha = __import__("catalogador_original").catag(st.session_state.api)
            st.session_state.catalog_results = catalog
            st.sidebar.success("Catalogação concluída!")
        except Exception as e:
            add_log(f"Erro na catalogação: {str(e)}. Tentando reconectar...", "error")
            connect_iqoption(st.session_state.email, st.session_state.senha)
            try:
                catalog, linha = __import__("catalogador_original").catag(st.session_state.api)
                st.session_state.catalog_results = catalog
                st.sidebar.success("Catalogação concluída após reconectar!")
            except Exception as e2:
                st.sidebar.error(f"Erro crítico na catalogação: {str(e2)}")
    if st.session_state.catalog_results:
        assets = [row[1] for row in st.session_state.catalog_results]
        strategy_options = ["MHI", "Torres Gêmeas", "MHI M5"]
        selected_asset = st.selectbox("Selecione o ativo", options=assets)
        selected_strategy = st.selectbox("Selecione a estratégia", options=strategy_options)
        col1, col2 = st.columns(2)
        if col1.button("Iniciar Bot"):
            st.session_state.stop_bot = False
            if selected_strategy == "MHI":
                bot_func = run_mhi_strategy
            elif selected_strategy == "Torres Gêmeas":
                bot_func = run_torres_gemeas_strategy
            elif selected_strategy == "MHI M5":
                bot_func = run_mhi_m5_strategy
            else:
                bot_func = run_mhi_strategy
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
            add_log("Bot iniciado.", "success")
        if col2.button("Pausar Bot"):
            st.session_state.stop_bot = True
            if st.session_state.bot_thread:
                st.session_state.bot_thread.join(timeout=1)
            st.session_state.bot_running = False
            add_log("Bot pausado.", "warning")

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
for time_stamp, lvl, msg in st.session_state.log_messages:
    if lvl == "info":
        st.markdown(f"<div class='info'>[{time_stamp}] {msg}</div>", unsafe_allow_html=True)
    elif lvl == "warning":
        st.markdown(f"<div class='warning'>[{time_stamp}] {msg}</div>", unsafe_allow_html=True)
    elif lvl == "error":
        st.markdown(f"<div class='error'>[{time_stamp}] {msg}</div>", unsafe_allow_html=True)
    elif lvl == "success":
        st.markdown(f"<div class='success'>[{time_stamp}] {msg}</div>", unsafe_allow_html=True)
