"""
Telegram notification service for trading operations
"""
import requests
import logging
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)

# Telegram credentials
TELEGRAM_BOT_TOKEN = "8581657481:AAFdv3vZ-fT6kAmoNuRwVuHLLbGwVAkw4kI"
TELEGRAM_ADMIN_CHAT_ID = "833732395"


class TelegramService:
    """Service for sending Telegram notifications"""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_ADMIN_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.debug(f"[Telegram] Mensagem enviada com sucesso")
                return True
            else:
                logger.error(f"[Telegram] Erro ao enviar: {response.text}")
                return False
        except Exception as e:
            logger.error(f"[Telegram] Exceção ao enviar mensagem: {e}")
            return False
    
    def send_operation_result(
        self,
        asset: str,
        direction: str,
        amount: float,
        result: str,
        profit_loss: float,
        gale_level: int = 0,
        wins: int = 0,
        losses: int = 0,
        total_profit: float = 0.0
    ) -> bool:
        """Send operation result notification"""
        
        # Emojis based on result
        if result.upper() == 'WIN':
            result_emoji = "✅"
            result_text = "WIN"
        elif result.upper() == 'LOSS':
            result_emoji = "❌"
            result_text = "LOSS"
        elif result.upper() == 'DRAW':
            result_emoji = "🔄"
            result_text = "DRAW"
        else:
            result_emoji = "⏳"
            result_text = "PENDING"
        
        # Gale indicator
        gale_text = f"Gale {gale_level}" if gale_level > 0 else "Entrada"
        
        # Direction emoji
        direction_emoji = "🟢" if direction.upper() == "CALL" else "🔴"
        
        # Profit/Loss formatting
        pl_sign = "+" if profit_loss >= 0 else ""
        pl_color = "🟢" if profit_loss >= 0 else "🔴"
        
        # Score difference
        score_diff = wins - losses
        score_emoji = "📈" if score_diff > 0 else "📉" if score_diff < 0 else "➖"
        
        message = f"""
{result_emoji} <b>{result_text}</b> | {gale_text}

{direction_emoji} <b>{asset}</b> · {direction.upper()}
💰 Valor: ${amount:.2f}
{pl_color} P&L: {pl_sign}${profit_loss:.2f}

{score_emoji} <b>Placar: {wins}x{losses}</b> ({score_diff:+d})
💵 Lucro Total: ${total_profit:.2f}
"""
        return self.send_message(message.strip())
    
    def send_session_start(
        self,
        asset: str,
        strategy: str,
        account_type: str,
        initial_balance: float
    ) -> bool:
        """Send session start notification"""
        message = f"""
🚀 <b>SESSÃO INICIADA</b>

📊 Ativo: <b>{asset}</b>
🎯 Estratégia: <b>{strategy.upper()}</b>
💼 Conta: <b>{account_type}</b>
💰 Saldo Inicial: <b>${initial_balance:.2f}</b>

⏰ Iniciado em: {self._get_timestamp()}
"""
        return self.send_message(message.strip())
    
    def send_session_end(
        self,
        asset: str,
        strategy: str,
        wins: int,
        losses: int,
        total_profit: float,
        final_balance: float,
        stop_reason: str = "Manual"
    ) -> bool:
        """Send session end notification"""
        
        # Determine overall result
        if total_profit > 0:
            result_emoji = "🏆"
            result_text = "LUCRO"
        elif total_profit < 0:
            result_emoji = "💔"
            result_text = "PREJUÍZO"
        else:
            result_emoji = "🔄"
            result_text = "EMPATE"
        
        score_diff = wins - losses
        
        message = f"""
🛑 <b>SESSÃO FINALIZADA</b>

{result_emoji} <b>{result_text}: ${abs(total_profit):.2f}</b>

📊 Ativo: {asset}
🎯 Estratégia: {strategy.upper()}
📈 Placar Final: <b>{wins}x{losses}</b> ({score_diff:+d})
💰 Saldo Final: ${final_balance:.2f}
🔔 Motivo: {stop_reason}

⏰ Finalizado em: {self._get_timestamp()}
"""
        return self.send_message(message.strip())
    
    def send_stop_alert(
        self,
        stop_type: str,
        wins: int,
        losses: int,
        total_profit: float
    ) -> bool:
        """Send stop win/loss alert"""
        
        if stop_type == "WIN":
            emoji = "🏆"
            title = "STOP WIN"
        else:
            emoji = "🛑"
            title = "STOP LOSS"
        
        score_diff = wins - losses
        
        message = f"""
{emoji} <b>{title} ATINGIDO!</b>

📈 Placar: <b>{wins}x{losses}</b> ({score_diff:+d})
💰 Resultado: <b>${total_profit:.2f}</b>

⏰ {self._get_timestamp()}
"""
        return self.send_message(message.strip())
    
    def _get_timestamp(self) -> str:
        """Get current timestamp formatted"""
        from datetime import datetime
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


# Singleton instance
_telegram_service: Optional[TelegramService] = None


def get_telegram_service() -> TelegramService:
    """Get or create Telegram service instance"""
    global _telegram_service
    if _telegram_service is None:
        _telegram_service = TelegramService()
    return _telegram_service


def send_operation_notification(
    asset: str,
    direction: str,
    amount: float,
    result: str,
    profit_loss: float,
    gale_level: int = 0,
    wins: int = 0,
    losses: int = 0,
    total_profit: float = 0.0
) -> bool:
    """Convenience function to send operation notification"""
    service = get_telegram_service()
    return service.send_operation_result(
        asset=asset,
        direction=direction,
        amount=amount,
        result=result,
        profit_loss=profit_loss,
        gale_level=gale_level,
        wins=wins,
        losses=losses,
        total_profit=total_profit
    )
