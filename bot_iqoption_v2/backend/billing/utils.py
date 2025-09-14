from django.conf import settings
import requests
import logging

logger = logging.getLogger(__name__)


def create_mp_preference(user):
    """Create a Mercado Pago preference for a user.
    Returns (preference_id, init_point) or (None, None) when not configured or on error.
    """
    access_token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', '')
    if not access_token:
        return None, None
    try:
        notification_url = getattr(settings, 'MERCADOPAGO_NOTIFICATION_URL', '')
        back_base = getattr(settings, 'FRONTEND_URL', 'http://127.0.0.1:5173')
        price = float(getattr(settings, 'SUBSCRIPTION_PRICE', 49.90))
        payload = {
            "items": [
                {
                    "title": "Assinatura Mensal - Plataforma Bot IQ Option",
                    "description": "Acesso mensal à plataforma",
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": price,
                }
            ],
            "payer": {"email": user.email},
            "notification_url": notification_url,
            "external_reference": f"user:{user.id}",
            "back_urls": {
                "success": f"{back_base}/pay?status=approved",
                "pending": f"{back_base}/pay?status=pending",
                "failure": f"{back_base}/pay?status=failure",
            },
            "auto_return": "approved",
        }
        r = requests.post(
            "https://api.mercadopago.com/checkout/preferences",
            json=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=20,
        )
        data = r.json()
        if r.status_code in (200, 201) and data.get("id"):
            pref_id = data["id"]
            init_point = data.get("init_point") or data.get("sandbox_init_point")
            return pref_id, init_point
        logger.error("Failed to create Mercado Pago preference: %s", data)
        return None, None
    except Exception as e:
        logger.exception("Error creating Mercado Pago preference: %s", e)
        return None, None
