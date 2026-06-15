"""Stripe Checkout + webhook for Premium subscriptions."""

import logging

import stripe
from aiohttp import web
from aiogram import Bot

import db
from config import (
    PREMIUM_DAYS,
    PREMIUM_PRICE_GROSZE,
    PREMIUM_PRICE_PLN,
    PUBLIC_URL,
    STRIPE_PRICE_ID,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
)
from premium import stripe_configured

logger = logging.getLogger(__name__)

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


async def create_checkout_session(user_id: int) -> str | None:
    if not stripe_configured():
        return None

    success_url = f"{PUBLIC_URL}/pay/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{PUBLIC_URL}/pay/cancel"

    line_items: list[dict]
    mode = "subscription"

    if STRIPE_PRICE_ID:
        line_items = [{"price": STRIPE_PRICE_ID, "quantity": 1}]
    else:
        line_items = [
            {
                "price_data": {
                    "currency": "pln",
                    "product_data": {"name": "CursorRandka Premium"},
                    "unit_amount": PREMIUM_PRICE_GROSZE,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }
        ]

    session = stripe.checkout.Session.create(
        mode=mode,
        line_items=line_items,
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(user_id),
        metadata={"user_id": str(user_id)},
        subscription_data={"metadata": {"user_id": str(user_id)}},
    )

    await db.record_payment(
        user_id,
        PREMIUM_PRICE_GROSZE,
        stripe_session_id=session.id,
        status="pending",
    )
    return session.url


async def _activate_from_session(session: dict, bot: Bot | None) -> None:
    user_id = int(session.get("client_reference_id") or session.get("metadata", {}).get("user_id", 0))
    if not user_id:
        logger.warning("Stripe session without user_id: %s", session.get("id"))
        return

    session_id = session.get("id", "")
    subscription_id = session.get("subscription")
    await db.mark_payment_completed(session_id, subscription_id)
    until = await db.activate_premium(user_id, PREMIUM_DAYS)
    logger.info("Premium activated user=%s until=%s session=%s", user_id, until, session_id)

    if bot:
        try:
            await bot.send_message(
                user_id,
                "⭐ <b>Premium aktywne!</b>\n\n"
                f"Masz dostęp do wszystkich funkcji Premium do "
                f"<b>{until[:10]}</b>.\n\n"
                "Sprawdź ⭐ Premium w menu!",
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning("Could not notify user %s about premium: %s", user_id, exc)


async def _extend_from_invoice(invoice: dict, bot: Bot | None) -> None:
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return
    try:
        sub = stripe.Subscription.retrieve(subscription_id)
        user_id = int(sub.get("metadata", {}).get("user_id", 0))
    except Exception as exc:
        logger.warning("Invoice subscription lookup failed: %s", exc)
        return
    if not user_id:
        return
    until = await db.activate_premium(user_id, PREMIUM_DAYS)
    logger.info("Premium renewed user=%s until=%s", user_id, until)
    if bot:
        try:
            await bot.send_message(
                user_id,
                f"⭐ Premium przedłużone do <b>{until[:10]}</b>! Dziękujemy 💕",
                parse_mode="HTML",
            )
        except Exception:
            pass


async def handle_stripe_webhook(request: web.Request) -> web.Response:
    bot: Bot | None = request.app.get("bot")
    payload = await request.read()
    sig = request.headers.get("Stripe-Signature", "")

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        else:
            import json

            event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    except Exception as exc:
        logger.warning("Stripe webhook verify failed: %s", exc)
        return web.Response(status=400, text="invalid payload")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        if data.get("payment_status") == "paid" or data.get("status") == "complete":
            await _activate_from_session(data, bot)
    elif event_type == "invoice.payment_succeeded":
        if data.get("billing_reason") in ("subscription_cycle", "subscription_create"):
            await _extend_from_invoice(data, bot)

    return web.Response(text="ok")


async def pay_success_page(request: web.Request) -> web.Response:
    html = (
        "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
        "<h1>⭐ Premium aktywne!</h1>"
        "<p>Wróć do bota na Telegramie — Premium jest już włączone.</p>"
        "</body></html>"
    )
    session_id = request.query.get("session_id")
    if session_id and stripe_configured():
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            bot: Bot | None = request.app.get("bot")
            if session.get("payment_status") == "paid":
                await _activate_from_session(session, bot)
        except Exception as exc:
            logger.warning("Success page activation failed: %s", exc)
    return web.Response(text=html, content_type="text/html")


async def pay_cancel_page(_request: web.Request) -> web.Response:
    html = (
        "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
        "<h1>Płatność anulowana</h1>"
        "<p>Możesz spróbować ponownie w bocie — ⭐ Premium.</p>"
        "</body></html>"
    )
    return web.Response(text=html, content_type="text/html")


async def health_check(_request: web.Request) -> web.Response:
    return web.Response(text="ok")


def create_webhook_app(bot: Bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/health", health_check)
    app.router.add_post("/stripe/webhook", handle_stripe_webhook)
    app.router.add_get("/pay/success", pay_success_page)
    app.router.add_get("/pay/cancel", pay_cancel_page)
    return app
