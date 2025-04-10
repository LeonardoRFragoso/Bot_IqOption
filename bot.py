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
                            green+'-->'+ white +' ')
    
    estrategia =  int(estrategia)

    if estrategia == 1:
        break
    if estrategia == 2:
        break
    if estrategia == 3:
        break
    else:
        print(red+'Escolha incorreta! Digite 1 a 3')


ativo = input(green+ '\n>>'+white+' Digite o ativo que você deseja operar: ').upper()
print('\n')

if estrategia == 1:
    estrategia_mhi()
if estrategia == 2:
    estrategia_torresgemeas()
if estrategia == 3:
    estrategia_mhi_m5()