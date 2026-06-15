# Premium / Stripe на Railway

Цена: **24,99 zł / mies.** (2499 groszy в Stripe)

## 1. Stripe Dashboard

1. Создай аккаунт на https://dashboard.stripe.com
2. **Products** → Add product → «CursorRandka Premium»
3. Price: **24.99 PLN**, recurring **monthly**
4. Скопируй **Price ID** (`price_...`) → `STRIPE_PRICE_ID`
5. **Developers → API keys** → Secret key → `STRIPE_SECRET_KEY`

## 2. Railway variables

```
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...
PUBLIC_URL=https://twoja-usluga.up.railway.app
```

`PUBLIC_URL` — публичный URL сервиса Railway (без слэша в конце).

## 3. Stripe Webhook

**Developers → Webhooks → Add endpoint**

- URL: `https://twoja-usluga.up.railway.app/stripe/webhook`
- Events:
  - `checkout.session.completed`
  - `invoice.payment_succeeded`

Скопируй **Signing secret** → `STRIPE_WEBHOOK_SECRET`

## 4. Deploy

Push на GitHub → Railway redeploy. В логах должно быть:

```
build=2025-06-13-premium-v10 stripe=yes public_url=https://...
Webhook server on 0.0.0.0:8080
```

## 5. Тест без Stripe

Админ-команда:

```
/givepremium <telegram_user_id> 30
```

## 6. Проверка

1. В боте: **⭐ Premium** → **💳 Kup Premium**
2. Оплата картой (test mode: `4242 4242 4242 4242`)
3. После оплаты — сообщение «Premium aktywne!»
4. В меню появится **💖 Kto Cię polubił**

## Premium функции

- Безлимитные лайки (вместо 50/день)
- Kto Cię polubił
- Cofnij ostatnie pominięcie (5×/день)
- Возраст ±5 лет (вместо ±2)
- Приоритет в ленте
- Super polubienie (1×/день)
- Расширенная статистика
- Значок ⭐ на профиле
