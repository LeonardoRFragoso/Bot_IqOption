from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions, status
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging
import requests

from .models import Subscription, Payment
from .serializers import (
    SubscriptionStatusSerializer,
    PaymentSerializer,
    AdminUserSubscriptionSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# Helpers

def _is_platform_admin(user) -> bool:
    try:
        return user and user.email == getattr(settings, 'PLATFORM_ADMIN_EMAIL', '')
    except Exception:
        return False


def _create_mp_preference(user):
    """Create a Mercado Pago preference for this user. Returns (preference_id, init_point) or (None, None)."""
    access_token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', '')
    if not access_token:
        return None, None

    try:
        # Build preference payload
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
            "external_reference": f"user:{user.id}",
        }

        # Only include redirect/back_urls and auto_return for public frontends (avoid strict validations on localhost)
        try:
            is_local_front = any(h in back_base for h in ["localhost", "127.0.0.1", "0.0.0.0"])
        except Exception:
            is_local_front = True

        if not is_local_front:
            payload["back_urls"] = {
                "success": f"{back_base}/pay?status=approved",
                "pending": f"{back_base}/pay?status=pending",
                "failure": f"{back_base}/pay?status=failure",
            }
            payload["auto_return"] = "approved"
        else:
            logger.warning("[Billing] Local frontend detected, skipping back_urls/auto_return. FRONTEND_URL=%s", back_base)

        # Only include notification_url if it looks public AND uses https (Mercado Pago rejects localhost and often plain http)
        try:
            include_notification = (
                bool(notification_url)
                and not any(h in notification_url for h in ["localhost", "127.0.0.1", "0.0.0.0"])
                and str(notification_url).startswith("https://")
            )
            if include_notification:
                payload["notification_url"] = notification_url
            else:
                logger.warning(
                    "[Billing] Skipping notification_url (not public https). MERCADOPAGO_NOTIFICATION_URL=%s",
                    notification_url,
                )
        except Exception:
            include_notification = False

        # Debug: which optional fields are present
        try:
            logger.debug("Creating MP preference with payload keys: %s", list(payload.keys()))
        except Exception:
            pass

        # Use REST API directly to avoid extra SDK dependency footprint
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
            try:
                env = "production" if (data.get("init_point") and "sandbox" not in str(data.get("init_point"))) else "sandbox"
                logger.warning("[Billing] Mercado Pago preference created [%s]: id=%s", env.upper(), pref_id)
            except Exception:
                pass
            return pref_id, init_point

        # If Mercado Pago rejects auto_return complaining about back_urls.success, retry without auto_return
        message = str(data)
        if r.status_code == 400 and (
            "invalid_auto_return" in message
            or "auto_return invalid" in message
            or "back_url.success" in message
            or "back_urls.success" in message
        ):
            try:
                payload_retry = dict(payload)
                payload_retry.pop("auto_return", None)
                r2 = requests.post(
                    "https://api.mercadopago.com/checkout/preferences",
                    json=payload_retry,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=20,
                )
                data2 = r2.json()
                if r2.status_code in (200, 201) and data2.get("id"):
                    pref_id = data2["id"]
                    init_point = data2.get("init_point") or data2.get("sandbox_init_point")
                    try:
                        env = "production" if (data2.get("init_point") and "sandbox" not in str(data2.get("init_point"))) else "sandbox"
                        logger.warning("[Billing] Mercado Pago preference created on retry without auto_return [%s]: id=%s", env.upper(), pref_id)
                    except Exception:
                        pass
                    return pref_id, init_point
                # If second attempt complains about notification_url, try again removing it too
                msg2 = str(data2)
                if r2.status_code == 400 and (
                    "invalid_notification_url" in msg2 or "notificaction_url" in msg2
                ):
                    try:
                        payload_retry2 = dict(payload_retry)
                        payload_retry2.pop("notification_url", None)
                        r3 = requests.post(
                            "https://api.mercadopago.com/checkout/preferences",
                            json=payload_retry2,
                            headers={
                                "Authorization": f"Bearer {access_token}",
                                "Content-Type": "application/json",
                            },
                            timeout=20,
                        )
                        data3 = r3.json()
                        if r3.status_code in (200, 201) and data3.get("id"):
                            pref_id = data3["id"]
                            init_point = data3.get("init_point") or data3.get("sandbox_init_point")
                            try:
                                env = "production" if (data3.get("init_point") and "sandbox" not in str(data3.get("init_point"))) else "sandbox"
                                logger.warning("[Billing] Mercado Pago preference created on retry without auto_return & notification_url [%s]: id=%s", env.upper(), pref_id)
                            except Exception:
                                pass
                            return pref_id, init_point
                        logger.error(
                            "Failed to create Mercado Pago preference (retry without auto_return & notification_url): %s",
                            data3,
                        )
                    except Exception:
                        logger.exception("Retry without auto_return & notification_url failed")
                logger.error("Failed to create Mercado Pago preference (retry without auto_return): %s", data2)
            except Exception:
                logger.exception("Retry without auto_return failed")

        # If Mercado Pago rejects notification_url on the first attempt, retry without it (and without auto_return as well)
        if r.status_code == 400 and (
            "invalid_notification_url" in message
            or "notificaction_url" in message  # some responses include this misspelling
        ):
            try:
                payload_retry2 = dict(payload)
                payload_retry2.pop("notification_url", None)
                payload_retry2.pop("auto_return", None)
                r3 = requests.post(
                    "https://api.mercadopago.com/checkout/preferences",
                    json=payload_retry2,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=20,
                )
                data3 = r3.json()
                if r3.status_code in (200, 201) and data3.get("id"):
                    pref_id = data3["id"]
                    init_point = data3.get("init_point") or data3.get("sandbox_init_point")
                    logger.info("Mercado Pago preference created on retry without notification_url and auto_return")
                    return pref_id, init_point
                logger.error("Failed to create Mercado Pago preference (retry without notification_url): %s", data3)
            except Exception:
                logger.exception("Retry without notification_url failed")

        # Final fallback: try absolute minimal payload (items + external_reference only)
        try:
            payload_min = {
                "items": payload["items"],
                "external_reference": payload.get("external_reference"),
            }
            r4 = requests.post(
                "https://api.mercadopago.com/checkout/preferences",
                json=payload_min,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                timeout=20,
            )
            data4 = r4.json()
            if r4.status_code in (200, 201) and data4.get("id"):
                pref_id = data4["id"]
                init_point = data4.get("init_point") or data4.get("sandbox_init_point")
                try:
                    env = "production" if (data4.get("init_point") and "sandbox" not in str(data4.get("init_point"))) else "sandbox"
                    logger.warning("[Billing] Mercado Pago preference created using minimal payload fallback [%s]: id=%s", env.upper(), pref_id)
                except Exception:
                    pass
                return pref_id, init_point
            logger.error("Failed to create Mercado Pago preference (minimal payload fallback): %s", data4)
        except Exception:
            logger.exception("Minimal payload fallback failed")

        logger.error("Failed to create Mercado Pago preference: %s", data)
        return None, None
    except Exception as e:
        logger.exception("Error creating Mercado Pago preference: %s", e)
        return None, None


@api_view(["GET"]) 
@permission_classes([permissions.IsAuthenticated])
def subscription_status(request):
    """Return current user's subscription status and payment options via Mercado Pago API only.
    Response fields: is_subscribed, active_until, preference_id?, init_point?, public_key?
    """
    user = request.user

    # Admin is always allowed
    is_admin = _is_platform_admin(user)

    sub = getattr(user, "subscription", None)
    if not sub:
        sub = Subscription.objects.create(user=user)

    is_active = sub.is_active() or is_admin

    preference_id = None
    init_point = None
    if not is_active:
        preference_id, init_point = _create_mp_preference(user)

    resp = {
        "is_subscribed": bool(is_active),
        "active_until": sub.active_until,
        "public_key": getattr(settings, 'MERCADOPAGO_PUBLIC_KEY', ''),
    }
    if preference_id:
        resp["preference_id"] = preference_id
    if init_point:
        resp["init_point"] = init_point
        try:
            env = "production"
            if isinstance(init_point, str) and "sandbox" in init_point:
                env = "sandbox"
            resp["mp_env"] = env
        except Exception:
            pass

    return Response(resp)


@api_view(["POST", "GET"])  # Mercado Pago may hit GET on webhook validation
@permission_classes([permissions.AllowAny])
def webhook(request):
    """Mercado Pago webhook receiver.
    Handles both new (data.id) and legacy (id/topic) formats.
    Updates Payment and activates Subscription on approved payments.
    """
    try:
        access_token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', '')
        if not access_token:
            return Response({"error": "Access token not configured"}, status=400)

        # Extract payment id
        payment_id = None
        body = request.data or {}
        if isinstance(body, dict):
            data = body.get('data') or {}
            if isinstance(data, dict):
                payment_id = data.get('id') or data.get('payment', {}).get('id')
        if not payment_id:
            payment_id = request.query_params.get('id') or request.query_params.get('data.id')

        if not payment_id:
            # Acknowledge to avoid retries; log for diagnostics
            logger.warning("Webhook called without payment id: %s %s", request.query_params, body)
            return Response({"message": "ok", "status": status_mp, "status_detail": status_detail, "payment_method_id": payment_method_id, "payment_type_id": payment_type_id})

        # Fetch payment details
        url = f"https://api.mercadopago.com/v1/payments/{payment_id}"
        r = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=20)
        data = r.json()
        if r.status_code != 200:
            logger.error("Failed to fetch payment %s: %s", payment_id, data)
            return Response({"message": "ignored"})

        status_mp = data.get('status')
        status_detail = data.get('status_detail')
        amount = data.get('transaction_amount') or 0
        currency = data.get('currency_id') or 'BRL'
        description = data.get('description') or 'Assinatura Mensal'
        payment_method_id = data.get('payment_method_id')
        payment_type_id = data.get('payment_type_id')
        preference_id = None
        try:
            additional = data.get('additional_info') or {}
            order = data.get('order') or {}
            preference_id = order.get('id') or additional.get('entity')
        except Exception:
            pass
        external_reference = data.get('external_reference')

        # Map payment to user using external_reference "user:<id>"
        user = None
        if external_reference and str(external_reference).startswith('user:'):
            try:
                uid = int(str(external_reference).split(':', 1)[1])
                user = User.objects.filter(id=uid).first()
            except Exception:
                user = None
        # Fallback by payer email
        if not user:
            payer = data.get('payer') or {}
            email = payer.get('email')
            if email:
                user = User.objects.filter(email=email).first()

        if not user:
            logger.warning("Payment %s without resolvable user", payment_id)
            return Response({"message": "ok"})

        # Save/Update payment
        payment, _ = Payment.objects.get_or_create(
            mp_payment_id=str(payment_id),
            defaults={
                'user': user,
                'status': status_mp,
                'amount': amount or 0,
                'currency': currency,
                'description': description,
                'mp_preference_id': preference_id,
                'external_reference': external_reference,
            }
        )
        # Update fields on repeated calls
        payment.user = user
        payment.status = status_mp
        payment.amount = amount or 0
        payment.currency = currency
        payment.description = description
        payment.mp_preference_id = preference_id
        payment.external_reference = external_reference
        if status_mp == 'approved' and not payment.paid_at:
            payment.paid_at = timezone.now()
        payment.save()

        # Activate subscription on approval
        if status_mp == 'approved':
            sub, _ = Subscription.objects.get_or_create(user=user)
            sub.activate_for_days(30)

        return Response({"message": "ok"})
    except Exception as e:
        logger.exception("Webhook error: %s", e)
        return Response({"message": "ok"})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def admin_users(request):
    if not _is_platform_admin(request.user):
        return Response({"detail": "Not authorized"}, status=403)
    users = User.objects.all().order_by('-date_joined')
    data = AdminUserSubscriptionSerializer(users, many=True).data
    return Response(data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def admin_payments(request):
    if not _is_platform_admin(request.user):
        return Response({"detail": "Not authorized"}, status=403)
    payments = Payment.objects.select_related('user').all()[:200]
    data = PaymentSerializer(payments, many=True).data
    return Response(data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def admin_grant(request):
    if not _is_platform_admin(request.user):
        return Response({"detail": "Not authorized"}, status=403)
    try:
        user_id = int(request.data.get('user_id'))
        days = int(request.data.get('days', 30))
        user = User.objects.get(id=user_id)
        sub, _ = Subscription.objects.get_or_create(user=user)
        sub.activate_for_days(days)
        return Response({"success": True, "active_until": sub.active_until})
    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=400)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def verify_return(request):
    """Verify Mercado Pago return parameters and activate subscription if payment is approved.
    This is useful in local development where the webhook may not be reachable.
    Query params typically include: status, payment_id, collection_id, preference_id, merchant_order_id.
    """
    try:
        access_token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', '')
        if not access_token:
            return Response({"success": False, "error": "Mercado Pago not configured"}, status=400)

        user = request.user
        qp = request.query_params
        payment_id = qp.get('payment_id') or qp.get('collection_id') or qp.get('data.id')
        preference_id = qp.get('preference_id') or qp.get('pref_id')

        # If we only have preference_id, try to resolve to a payment via merchant orders
        if not payment_id and preference_id:
            try:
                mo = requests.get(
                    f"https://api.mercadopago.com/merchant_orders?preference_id={preference_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=20,
                ).json()
                # Find a payment id in the response structure
                payments = []
                try:
                    elements = mo.get('elements') or []
                except Exception:
                    elements = []
                for el in elements:
                    for p in el.get('payments', []) or []:
                        if p.get('id'):
                            payments.append(str(p['id']))
                if payments:
                    payment_id = payments[0]
            except Exception:
                pass

        if not payment_id:
            return Response({"success": False, "error": "payment_id not provided and could not be resolved"}, status=400)

        # Fetch payment details
        url = f"https://api.mercadopago.com/v1/payments/{payment_id}"
        r = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=20)
        data = r.json()
        if r.status_code != 200:
            logger.error("Verify return: failed to fetch payment %s: %s", payment_id, data)
            return Response({"success": False, "error": "failed_to_fetch"}, status=400)

        status_mp = data.get('status')
        status_detail = data.get('status_detail')
        amount = data.get('transaction_amount') or 0
        currency = data.get('currency_id') or 'BRL'
        description = data.get('description') or 'Assinatura Mensal'
        payment_method_id = data.get('payment_method_id')
        payment_type_id = data.get('payment_type_id')
        pref_id = None
        try:
            additional = data.get('additional_info') or {}
            order = data.get('order') or {}
            pref_id = order.get('id') or additional.get('entity')
        except Exception:
            pass
        external_reference = data.get('external_reference')

        # Ensure the payment is linked to this user; tolerate mismatch in dev
        if external_reference and str(external_reference).startswith('user:'):
            try:
                uid = int(str(external_reference).split(':', 1)[1])
                if uid != user.id:
                    logger.warning("Verify return: payment %s belongs to user %s but current is %s", payment_id, uid, user.id)
            except Exception:
                pass

        payment, _ = Payment.objects.get_or_create(
            mp_payment_id=str(payment_id),
            defaults={
                'user': user,
                'status': status_mp,
                'amount': amount or 0,
                'currency': currency,
                'description': description,
                'mp_preference_id': pref_id or preference_id,
                'external_reference': external_reference,
            }
        )
        payment.user = user
        payment.status = status_mp
        payment.amount = amount or 0
        payment.currency = currency
        payment.description = description
        payment.mp_preference_id = pref_id or preference_id
        payment.external_reference = external_reference
        if status_mp == 'approved' and not payment.paid_at:
            payment.paid_at = timezone.now()
        payment.save()

        activated = False
        if status_mp == 'approved':
            sub, _ = Subscription.objects.get_or_create(user=user)
            sub.activate_for_days(30)
            activated = True
            return Response({
                "success": True,
                "activated": True,
                "active_until": sub.active_until,
                "payment_id": payment_id,
                "status": status_mp,
                "status_detail": status_detail,
                "payment_method_id": payment_method_id,
                "payment_type_id": payment_type_id,
            })

        return Response({
            "success": True,
            "activated": False,
            "payment_id": payment_id,
            "status": status_mp,
            "status_detail": status_detail,
            "payment_method_id": payment_method_id,
            "payment_type_id": payment_type_id,
        })
    except Exception as e:
        logger.exception("Verify return error: %s", e)
        return Response({"success": False, "error": str(e)}, status=400)
