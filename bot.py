from iqoptionapi.stable_api import IQ_Option
import time
from configobj import ConfigObj
import json, sys
from datetime import datetime, timedelta
from catalogador import catag
from tabulate import tabulate
from colorama import init, Fore, Back


init(autoreset=True)
green = Fore.GREEN
yellow = Fore.YELLOW
red = Fore.RED
white = Fore.WHITE
greenf = Back.GREEN
yellowf = Back.YELLOW
redf = Back.RED
blue = Fore.BLUE

print(green+'''
      
    
██████╗ ██╗   ██╗███████╗ ██████╗██████╗ ██╗██████╗ ████████╗
██╔══██╗╚██╗ ██╔╝██╔════╝██╔════╝██╔══██╗██║██╔══██╗╚══██╔══╝
██████╔╝ ╚████╔╝ ███████╗██║     ██████╔╝██║██████╔╝   ██║   
██╔═══╝   ╚██╔╝  ╚════██║██║     ██╔══██╗██║██╔═══╝    ██║   
██║        ██║   ███████║╚██████╗██║  ██║██║██║        ██║   
╚═╝        ╚═╝   ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝╚═╝        ╚═╝   
                                                             
'''+yellow+'''

''')

print(yellow + '***************************************************************************************\n\n')


### CRIANDO ARQUIVO DE CONFIGURAÇÃO ####
config = ConfigObj('config.txt')
email = config['LOGIN']['email']
senha = config['LOGIN']['senha']
tipo = config['AJUSTES']['tipo']
valor_entrada = float(config['AJUSTES']['valor_entrada'])
stop_win = float(config['AJUSTES']['stop_win'])
stop_loss = float(config['AJUSTES']['stop_loss'])
lucro_total = 0
stop = True

if config['MARTINGALE']['usar'].upper() == 'S':
    martingale = int(config['MARTINGALE']['niveis'])
else:
    martingale = 0
fator_mg = float(config['MARTINGALE']['fator'])


if config['SOROS']['usar'].upper() == 'S':
    soros = True
    niveis_soros = int(config['SOROS']['niveis'])
    nivel_soros = 0

else:
    soros = False
    niveis_soros = 0
    nivel_soros = 0

valor_soros = 0
lucro_op_atual = 0

analise_medias = config['AJUSTES']['analise_medias']
velas_medias = int(config['AJUSTES']['velas_medias'])

print(yellow+'Iniciando Conexão com a IQOption')
API = IQ_Option(email,senha)

### Função para conectar na IQOPTION ###
check, reason = API.connect()
if check:
    print(green + '\nConectado com sucesso')
else:
    if reason == '{"code":"invalid_credentials","message":"You entered the wrong credentials. Please ensure that your login/password is correct."}':
        print(red+'\nEmail ou senha incorreta')
        sys.exit()
        
    else:
        print(red+ '\nHouve um problema na conexão')

        print(reason)
        sys.exit()

### Função para Selecionar demo ou real ###
while True:
    escolha = input(green+'\n>>'+ white +' Selecione a conta em que deseja conectar:\n'+
                            green+'>>'+ white +' 1 - Demo\n'+
                            green+'>>'+ white +' 2 - Real\n'+
                            green+'-->'+ white +' ')
    
    escolha =  int(escolha)

    if escolha == 1:
        conta = 'PRACTICE'
        print('Conta demo selecionada')
        break
    if escolha == 2:
        conta = 'REAL'
        print('Conta real selecionada')
        break
    else:
        print(red+'Escolha incorreta! Digite demo ou real')
        
API.change_balance(conta)


### Função para checar stop win e loss
def check_stop():
    global stop,lucro_total
    if lucro_total <= float('-'+str(abs(stop_loss))):
        stop = False
        print(red+'\n#########################')
        print(red+'STOP LOSS BATIDO ',str(cifrao),str(lucro_total))
        print(red+'#########################')
        sys.exit()
        

    if lucro_total >= float(abs(stop_win)):
        stop = False
        print(green+'\n#########################')
        print(green+'STOP WIN BATIDO ',str(cifrao),str(lucro_total))
        print(green+'#########################')
        sys.exit()

def payout(par):
    profit = API.get_all_profit()
    all_asset = API.get_all_open_time()

    try:
        if all_asset['binary'][par]['open']:
            if profit[par]['binary']> 0:
                binary = round(profit[par]['binary'],2) * 100
        else:
            binary  = 0
    except:
        binary = 0

    try:
        if all_asset['turbo'][par]['open']:
            if profit[par]['turbo']> 0:
                turbo = round(profit[par]['turbo'],2) * 100
        else:
            turbo  = 0
    except:
        turbo = 0

    try:
        if all_asset['digital'][par]['open']:
            digital = API.get_digital_payout(par)
        else:
            digital  = 0
    except:
        digital = 0

    return binary, turbo, digital

def compra(ativo, valor_entrada, direcao, exp, tipo):
    global stop, lucro_total, nivel_soros, niveis_soros, valor_soros, lucro_op_atual

    if soros:
        if nivel_soros == 0:
            entrada = valor_entrada
        elif nivel_soros >= 1 and valor_soros > 0 and nivel_soros <= niveis_soros:
            entrada = valor_entrada + valor_soros
        elif nivel_soros > niveis_soros:
            lucro_op_atual = 0
            valor_soros = 0
            entrada = valor_entrada
            nivel_soros = 0
    else:
        entrada = valor_entrada

    for i in range(martingale + 1):
        if stop:
            # Aplica Martingale antes da nova entrada (exceto na primeira)
            if i > 0:
                entrada = round(entrada * fator_mg, 2)

            if tipo == 'digital':
                check, id = API.buy_digital_spot_v2(ativo, entrada, direcao, exp)
            else:
                check, id = API.buy(entrada, ativo, direcao, exp)

            if check:
                print(f"\n>> Ordem aberta{' para gale ' + str(i) if i > 0 else ''}")
                print(f">> Par: {ativo}")
                print(f">> Timeframe: {exp}")
                print(f">> Entrada de: {cifrao}{entrada}")

                while True:
                    time.sleep(0.1)

                    if tipo == 'digital':
                        status, resultado = API.check_win_digital_v2(id)
                    else:
                        if hasattr(API, 'check_win_v3'):
                            resultado = API.check_win_v3(id)
                            status = True
                        else:
                            status, resultado = API.check_win_v2(id)

                    if status:
                        resultado = round(resultado, 2)
                        lucro_total += resultado
                        valor_soros += resultado
                        lucro_op_atual += resultado

                        if resultado > 0:
                            print(green + f'\n>> Resultado: WIN{" no gale " + str(i) if i > 0 else ""}')
                        elif resultado == 0:
                            print(yellow + f'\n>> Resultado: EMPATE{" no gale " + str(i) if i > 0 else ""}')
                        else:
                            print(red + f'\n>> Resultado: LOSS{" no gale " + str(i) if i > 0 else ""}')

                        print(white + f">> Lucro: {resultado}")
                        print(white + f">> Par: {ativo}")
                        print(white + f">> Lucro total: {lucro_total}")
                        check_stop()
                        break

                if resultado > 0:
                    break

            else:
                print(red + f'Erro na abertura da ordem, ID: {id}, Ativo: {ativo}')

    if soros:
        if lucro_op_atual > 0:
            nivel_soros += 1
            lucro_op_atual = 0
        else:
            valor_soros = 0
            nivel_soros = 0
            lucro_op_atual = 0


### Fução que busca hora da corretora ###
def horario():
    x = API.get_server_timestamp()
    now = datetime.fromtimestamp(API.get_server_timestamp())
    
    return now

def medias(velas):
    soma = 0
    for i in velas:
        soma += i['close']
    media = soma / velas_medias

    if media > velas[-1]['close']:
        tendencia = 'put'
    else:
        tendencia = 'call'

    return tendencia

### Função de análise MHI   
def estrategia_mhi():
    global tipo

    if tipo == 'automatico':
        binary, turbo, digital = payout(ativo)
        print(binary, turbo, digital )
        if digital > turbo:
            print( 'Suas entradas serão realizadas nas digitais')
            tipo = 'digital'
        elif turbo > digital:
            print( 'Suas entradas serão realizadas nas binárias')
            tipo = 'binary'
        else:
            print(' Par fechado, escolha outro')
            sys.exit()


    
    while True:
        time.sleep(0.1)

        ### Horario do computador ###
        #minutos = float(datetime.now().strftime('%M.%S')[1:])

        ### horario da iqoption ###
        minutos = float(datetime.fromtimestamp(API.get_server_timestamp()).strftime('%M.%S')[1:])

        entrar = True if (minutos >= 4.59 and minutos <= 5.00) or minutos >= 9.59 else False

        print('Aguardando Horário de entrada ' ,minutos, end='\r')
        

        if entrar:
            print('\n>> Iniciando análise da estratégia MHI')

            direcao = False

            timeframe = 60
            qnt_velas = 3


            if analise_medias == 'S':
                velas = API.get_candles(ativo, timeframe, velas_medias, time.time())
                tendencia = medias(velas)

            else:
                velas = API.get_candles(ativo, timeframe, qnt_velas, time.time())


            velas[-1] = 'Verde' if velas[-1]['open'] < velas[-1]['close'] else 'Vermelha' if velas[-1]['open'] > velas[-1]['close'] else 'Doji'
            velas[-2] = 'Verde' if velas[-2]['open'] < velas[-2]['close'] else 'Vermelha' if velas[-2]['open'] > velas[-2]['close'] else 'Doji'
            velas[-3] = 'Verde' if velas[-3]['open'] < velas[-3]['close'] else 'Vermelha' if velas[-3]['open'] > velas[-3]['close'] else 'Doji'


            cores = velas[-3] ,velas[-2] ,velas[-1] 

            if cores.count('Verde') > cores.count('Vermelha') and cores.count('Doji') == 0: direcao = 'put'
            if cores.count('Verde') < cores.count('Vermelha') and cores.count('Doji') == 0: direcao = 'call'

            if analise_medias =='S':
                if direcao == tendencia:
                    pass
                else:
                    direcao = 'abortar'



            if direcao == 'put' or direcao == 'call':
                print('Velas: ',velas[-3] ,velas[-2] ,velas[-1] , ' - Entrada para ', direcao)


                compra(ativo,valor_entrada,direcao,1,tipo)

                   
                print('\n')

            else:
                if direcao == 'abortar':
                    print('Velas: ',velas[-3] ,velas[-2] ,velas[-1] )
                    print('Entrada abortada - Contra Tendência.')

                else:
                    print('Velas: ',velas[-3] ,velas[-2] ,velas[-1] )
                    print('Entrada abortada - Foi encontrado um doji na análise.')

                time.sleep(2)

            print('\n######################################################################\n')

### Função de análise TORRES GEMEAS   
def estrategia_torresgemeas():
    global tipo

    if tipo == 'automatico':
        binary, turbo, digital = payout(ativo)
        print(binary, turbo, digital )
        if digital > turbo:
            print( 'Suas entradas serão realizadas nas digitais')
            tipo = 'digital'
        elif turbo > digital:
            print( 'Suas entradas serão realizadas nas binárias')
            tipo = 'binary'
        else:
            print(' Par fechado, escolha outro')
            sys.exit()


    
    while True:
        time.sleep(0.1)

        ### Horario do computador ###
        #minutos = float(datetime.now().strftime('%M.%S')[1:])

        ### horario da iqoption ###
        minutos = float(datetime.fromtimestamp(API.get_server_timestamp()).strftime('%M.%S')[1:])

        entrar = True if (minutos >= 3.59 and minutos <= 4.00) or (minutos >= 8.59 and minutos <= 9.00) else False

        print('Aguardando Horário de entrada ' ,minutos, end='\r')
        

        if entrar:
            print('\n>> Iniciando análise da estratégia MHI')

            direcao = False

            timeframe = 60
            qnt_velas = 4


            if analise_medias == 'S':
                velas = API.get_candles(ativo, timeframe, velas_medias, time.time())
                tendencia = medias(velas)

            else:
                velas = API.get_candles(ativo, timeframe, qnt_velas, time.time())

            velas[-4] = 'Verde' if velas[-4]['open'] < velas[-4]['close'] else 'Vermelha' if velas[-4]['open'] > velas[-4]['close'] else 'Doji'


            cores = velas[-4]

            if cores.count('Verde') > cores.count('Vermelha') and cores.count('Doji') == 0: direcao = 'call'
            if cores.count('Verde') < cores.count('Vermelha') and cores.count('Doji') == 0: direcao = 'put'

            if analise_medias =='S':
                if direcao == tendencia:
                    pass
                else:
                    direcao = 'abortar'



            if direcao == 'put' or direcao == 'call':
                print('Velas: ',velas[-3] ,velas[-2] ,velas[-1] , ' - Entrada para ', direcao)


                compra(ativo,valor_entrada,direcao,1,tipo)

                   
                print('\n')

            else:
                if direcao == 'abortar':
                    print('Velas: ',velas[-3] ,velas[-2] ,velas[-1] )
                    print('Entrada abortada - Contra Tendência.')

                else:
                    print('Velas: ',velas[-3] ,velas[-2] ,velas[-1] )
                    print('Entrada abortada - Foi encontrado um doji na análise.')

                time.sleep(2)

            print('\n######################################################################\n')


### Função de análise mhi m5  
def estrategia_mhi_m5():
    global tipo

    if tipo == 'automatico':
        binary, turbo, digital = payout(ativo)
        print(binary, turbo, digital )
        if digital > turbo:
            print( 'Suas entradas serão realizadas nas digitais')
            tipo = 'digital'
        elif turbo > digital:
            print( 'Suas entradas serão realizadas nas binárias')
            tipo = 'binary'
        else:
            print(' Par fechado, escolha outro')
            sys.exit()


    
    while True:
        time.sleep(0.1)

        ### Horario do computador ###
        #minutos = float(datetime.now().strftime('%M.%S')[1:])

        ### horario da iqoption ###
        minutos = float(datetime.fromtimestamp(API.get_server_timestamp()).strftime('%M.%S'))

        entrar = True if  (minutos >= 29.59 and minutos <= 30.00) or minutos == 59.59  else False

        print('Aguardando Horário de entrada ' ,minutos, end='\r')
        

        if entrar:
            print('\n>> Iniciando análise da estratégia MHI')

            direcao = False

            timeframe = 300
            qnt_velas = 3


            if analise_medias == 'S':
                velas = API.get_candles(ativo, timeframe, velas_medias, time.time())
                tendencia = medias(velas)

            else:
                velas = API.get_candles(ativo, timeframe, qnt_velas, time.time())

            velas[-1] = 'Verde' if velas[-1]['open'] < velas[-1]['close'] else 'Vermelha' if velas[-1]['open'] > velas[-1]['close'] else 'Doji'
            velas[-2] = 'Verde' if velas[-2]['open'] < velas[-2]['close'] else 'Vermelha' if velas[-2]['open'] > velas[-2]['close'] else 'Doji'
            velas[-3] = 'Verde' if velas[-3]['open'] < velas[-3]['close'] else 'Vermelha' if velas[-3]['open'] > velas[-3]['close'] else 'Doji'


            cores = velas[-3] ,velas[-2] ,velas[-1] 

            if cores.count('Verde') > cores.count('Vermelha') and cores.count('Doji') == 0: direcao = 'put'
            if cores.count('Verde') < cores.count('Vermelha') and cores.count('Doji') == 0: direcao = 'call'

            if analise_medias =='S':
                if direcao == tendencia:
                    pass
                else:
                    direcao = 'abortar'



            if direcao == 'put' or direcao == 'call':
                print('Velas: ',velas[-3] ,velas[-2] ,velas[-1] , ' - Entrada para ', direcao)


                compra(ativo,valor_entrada,direcao,5,tipo)

                   
                print('\n')

            else:
                if direcao == 'abortar':
                    print('Velas: ',velas[-3] ,velas[-2] ,velas[-1] )
                    print('Entrada abortada - Contra Tendência.')

                else:
                    print('Velas: ',velas[-3] ,velas[-2] ,velas[-1] )
                    print('Entrada abortada - Foi encontrado um doji na análise.')

                time.sleep(2)

            print('\n######################################################################\n')

### DEFININCãO INPUTS NO INICIO DO ROBÔ ###


perfil = json.loads(json.dumps(API.get_profile_ansyc()))
cifrao = str(perfil['currency_char'])
nome = str(perfil['name'])

valorconta = float(API.get_balance())

print(yellow+'\n######################################################################')
print('\nOlá, ',nome, '\nSeja bem vindo ao Robô da PyScript.')
print('\nSeu Saldo na conta ',escolha, 'é de', cifrao,valorconta)
print('\nSeu valor de entrada é de ',cifrao,valor_entrada)
print('\nStop win:',cifrao,stop_win)
print('\nStop loss:',cifrao,'-',stop_loss)
print(yellow+'\n######################################################################\n\n')



print('>> Iniciando catalogação')
lista_catalog , linha = catag(API)

print(yellow+ tabulate(lista_catalog, headers=['ESTRATEGIA','PAR','WIN','GALE1','GALE2']))

estrateg = lista_catalog[0][0]
ativo = lista_catalog[0][1]
assertividade = lista_catalog[0][linha]

print('\n>> Melhor par: ', ativo, ' | Estrategia: ',estrateg,' | Assertividade: ', assertividade)
print('\n')


### Função para escolher estrategia ###
while True:
    estrategia = input(green+'\n>>'+ white +' Selecione a estratégia desejada:\n'+
                            green+'>>'+ white +' 1 - MHI\n'+
                            green+'>>'+ white +' 2 - Torres Gêmeas\n'+
                            green+'>>'+ white +' 3 - MHI M5\n'+
                            green+'>>'+ white +' 4 - BB\n'+
                            green+'-->'+ white +' ')
    
    estrategia =  int(estrategia)

    if estrategia == 1:
        break
    if estrategia == 2:
        break
    if estrategia == 3:
        break
    if estrategia == 4:
        break
    else:
        print(red+'Escolha incorreta! Digite 1 a 4')


ativo = input(green+ '\n>>'+white+' Digite o ativo que você deseja operar: ').upper()
print('\n')

if estrategia == 1:
    estrategia_mhi()
if estrategia == 2:
    estrategia_torresgemeas()
if estrategia == 3:
    estrategia_mhi_m5()
if estrategia == 4:
    estrategia_bb()

### Funções auxiliares para estratégia BB ###

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

def valida_tendencia_macro(ativo, timeframe=300, num_candles=100):
    """
    Valida a tendência macro do ativo usando médias móveis de longo prazo.
    Retorna True se a tendência for considerada estável.
    """
    try:
        # Obter candles para análise de tendência
        timestamp_atual = time.time()
        candles = API.get_candles(ativo, timeframe, num_candles, timestamp_atual)
        
        if candles is None or len(candles) < 50:
            print("Dados insuficientes para análise de tendência macro")
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
        print(f"Erro ao validar tendência macro: {e}")
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
        print(f"Erro ao registrar auditoria: {e}")

### Estratégia BB ###
def estrategia_bb():
    """
    Estratégia BB + Retração/Pullback/Reversão adaptada para M5.
    Utiliza a média móvel simples dos 50 últimos fechamentos (BB50),
    verificação de candle de força, padrões (Pinbar, Engolfo),
    níveis Fibonacci e validação por zona SR.
    Também registra o sinal em auditoria e evita múltiplas entradas por candle.
    """
    global API, ativo, valor_entrada, tipo, stop
    ultima_execucao = None  # controle para evitar múltiplas execuções no mesmo período
    
    print(green + '\nEstratégia BB iniciada para o ativo ' + ativo)
    print(yellow + '\n######################################################################\n')
    
    while stop:
        time.sleep(0.1)
        
        # Verificar stop win/loss
        check_stop()
        if not stop:
            break
            
        agora = datetime.fromtimestamp(API.get_server_timestamp())
        minuto = agora.minute
        segundo = agora.second
        
        # Para M5, disparamos a análise quando o minuto é divisível por 5 e os segundos estão entre 0 e 4
        if (minuto % 5 == 0) and (segundo < 5) and (ultima_execucao != f"{minuto}:{segundo}"):
            ultima_execucao = f"{minuto}:{segundo}"
            
            # Valida tendência macro antes de operar
            if not valida_tendencia_macro(ativo):
                print("Tendência macro não confirmada, operação abortada.")
                continue

            print('\n>> Iniciando análise da estratégia BB (M5)')
            timeframe = 300            # M5: 300 segundos
            quantidade_candles = 60
            timestamp_atual = time.time()
            candles = API.get_candles(ativo, timeframe, quantidade_candles, timestamp_atual)
            
            if candles is None or len(candles) < 50:
                print("Número insuficiente de candles para análise BB")
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
            print(f"Fechamento: {close_last}, Média BB50: {media_50}")
            print(f"Candle atual: open={open_last}, close={close_last}, high={high_last}, low={low_last}")
            print(f"Candle de força? {'Sim' if candle_forca else 'Não'}")

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
            if sinal_engolfo:
                sinal_info += " Padrão Engolfo identificado."
            if zona_sr:
                sinal_info += " Zona de suporte/resistência validada."

            print("Níveis Fibonacci calculados:", fibo_levels)
            if direcao is not None:
                print("Sinal:", sinal_info)
                log_auditoria(sinal_info, ativo, "BB")
                # Para M5, passamos expiração de 5 minutos
                compra(ativo, valor_entrada, direcao, 5, tipo)
            else:
                print("Nenhum sinal acionado no momento.")

            print('\n######################################################################\n')