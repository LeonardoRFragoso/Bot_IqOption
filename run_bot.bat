@echo off
REM Ativa o ambiente virtual
call venv\Scripts\activate.bat

REM Executa o script
python bot.py

REM Mantém a janela aberta para visualizar a saída
pause
