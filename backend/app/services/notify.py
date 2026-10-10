"""Notify users and admins via Telegram Bot API (best-effort)."""

from __future__ import annotations

import html
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import Settings
from app.models import AdRequest, MessageRequest, Profile, User
from app.services.telegram_api import TelegramApiError, get_bot_username, send_message

logger = logging.getLogger(__name__)


def _app_link(settings: Settings, startapp: str) -> str:
    # Telegram iOS web views load only the HTML for nested paths like /inbox/1,
    # so deep links always go through the root URL and the app routes by startapp.
    return f"{settings.webapp_url.rstrip('/')}/?startapp={startapp}"


def _webapp_button(url: str, label: str) -> dict:
    return {"inline_keyboard": [[{"text": label, "web_app": {"url": url}}]]}


async def notify_admins_profile_submitted(
    settings: Settings,
    *,
    user: User,
    profile: Profile,
) -> None:
    admin_ids = settings.admin_ids
    if not admin_ids:
        return

    name = profile.name or user.telegram_first_name or "—"
    username = profile.telegram_username or user.telegram_username or "—"
    text = (
        f"🆕 Новая анкета на модерации\n"
        f"ID: {profile.id}\n"
        f"Имя: {name}, {profile.age}\n"
        f"@{username}\n"
        f"tg_id: {user.telegram_id}"
    )
    for admin_id in admin_ids:
        try:
            await send_message(settings, admin_id, text, parse_mode=None)
        except TelegramApiError as exc:
            # "chat not found" means the admin never pressed /start in the bot
            logger.warning("Failed to notify admin %s: %s", admin_id, exc)
        except Exception:
            logger.exception("Failed to notify admin %s", admin_id)


async def notify_user_profile_approved(
    settings: Settings,
    *,
    user: User,
    profile: Profile,
    stars: int,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        text = (
            f"✅ Il tuo profilo <b>{profile.name}</b> è stato approvato.\n\n"
            f"Per pubblicarlo nel canale, paga <b>{stars} ★</b>.\n"
            "Ti inviamo la fattura Telegram Stars qui sotto."
        )
    else:
        text = (
            f"✅ Анкета <b>{profile.name}</b> одобрена.\n\n"
            f"Чтобы опубликовать её в канале, оплатите <b>{stars} ★</b>.\n"
            "Счёт в Telegram Stars — в следующем сообщении."
        )
    try:
        await send_message(settings, user.telegram_id, text)
    except Exception:
        logger.exception("Failed to notify user %s about approval", user.telegram_id)


async def notify_user_profile_rejected(
    settings: Settings,
    *,
    user: User,
    profile: Profile,
    feedback: str,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        text = (
            f"Анкета отклонена / Profilo rifiutato.\n\n"
            f"<b>Cosa correggere:</b>\n{feedback.strip()}\n\n"
            "Puoi modificare il profilo nell’app e inviarlo di nuovo — senza pagamento."
        )
    else:
        text = (
            f"Анкета отклонена.\n\n"
            f"<b>Что поправить:</b>\n{feedback.strip()}\n\n"
            "Исправьте анкету в Mini App и отправьте снова — без оплаты."
        )
    try:
        await send_message(settings, user.telegram_id, text)
    except Exception:
        logger.exception("Failed to notify user %s about rejection", user.telegram_id)


async def notify_user_scheduled(
    settings: Settings,
    *,
    user: User,
    profile: Profile,
    scheduled_at: datetime,
) -> None:
    tz = ZoneInfo(settings.app_timezone)
    local = scheduled_at.astimezone(tz)
    date_str = local.strftime("%d.%m.%Y %H:%M")
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        text = (
            f"📅 Data di pubblicazione fissata per <b>{profile.name}</b>:\n"
            f"<b>{date_str}</b> (ora di Roma)."
        )
    else:
        text = (
            f"📅 Дата публикации анкеты <b>{profile.name}</b>:\n"
            f"<b>{date_str}</b> (по Риму)."
        )
    try:
        await send_message(settings, user.telegram_id, text)
    except Exception:
        logger.exception("Failed to notify user %s about schedule", user.telegram_id)


async def notify_user_published(
    settings: Settings,
    *,
    user: User,
    profile: Profile,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        text = f"🎉 Il profilo <b>{profile.name}</b> è stato pubblicato nel canale."
    else:
        text = f"🎉 Анкета <b>{profile.name}</b> опубликована в канале."
    try:
        await send_message(settings, user.telegram_id, text)
    except Exception:
        logger.exception("Failed to notify user %s about publish", user.telegram_id)


async def notify_new_letter(
    settings: Settings,
    *,
    recipient: User,
    request: MessageRequest,
) -> None:
    lang = recipient.language_code if recipient.language_code in {"ru", "it"} else "ru"
    name = request.sender_name or "—"
    age = request.sender_age or "—"
    app_url = _app_link(settings, f"inbox_{request.id}")
    if lang == "it":
        text = (
            f"💌 Nuova lettera da <b>{name}</b>, {age}.\n"
            "Apri l’app per rispondere o rifiutare — rispondere è gratis."
        )
        btn = "Apri lettera"
    else:
        text = (
            f"💌 Новое письмо от <b>{name}</b>, {age}.\n"
            "Откройте Mini App: ответить бесплатно или отклонить."
        )
        btn = "Открыть письмо"
    try:
        await send_message(
            settings,
            recipient.telegram_id,
            text,
            reply_markup=_webapp_button(app_url, btn),
        )
    except Exception:
        logger.exception("Failed to notify recipient %s about letter", recipient.telegram_id)


async def notify_recipient_rejected(
    settings: Settings,
    *,
    initiator: User,
    request: MessageRequest,
) -> None:
    lang = initiator.language_code if initiator.language_code in {"ru", "it"} else "ru"
    profile_name = request.profile.name if request.profile else "—"
    if lang == "it":
        text = f"La lettera a <b>{profile_name}</b> non ha ricevuto interesse. Nessun pagamento."
    else:
        text = f"Письмо к <b>{profile_name}</b> не заинтересовало. Оплаты нет."
    try:
        await send_message(settings, initiator.telegram_id, text)
    except Exception:
        logger.exception("Failed to notify initiator %s about reject", initiator.telegram_id)


async def notify_initiator_pay_to_unlock(
    settings: Settings,
    *,
    initiator: User,
    request: MessageRequest,
) -> None:
    lang = initiator.language_code if initiator.language_code in {"ru", "it"} else "ru"
    profile_name = request.profile.name if request.profile else "—"
    app_url = _app_link(settings, f"inbox_{request.id}")
    credits = initiator.message_credits
    if lang == "it":
        text = (
            f"✨ <b>{profile_name}</b> ti ha risposto.\n\n"
            f"Per aprire la chat usa 1 credito "
            f"(saldo: <b>{credits}</b>) oppure compra un pacchetto."
        )
        btn = "Sblocca chat"
    else:
        text = (
            f"✨ Вам ответил(а) <b>{profile_name}</b>.\n\n"
            f"Чтобы открыть чат — спишите 1 кредит "
            f"(баланс: <b>{credits}</b>) или купите пакет."
        )
        btn = "Открыть чат"
    try:
        await send_message(
            settings,
            initiator.telegram_id,
            text,
            reply_markup=_webapp_button(app_url, btn),
        )
    except Exception:
        logger.exception("Failed to notify initiator %s about reply", initiator.telegram_id)


def _tg_link(username: str | None) -> str | None:
    if not username:
        return None
    clean = username.strip().lstrip("@")
    if not clean:
        return None
    return f"https://t.me/{clean}"


async def notify_parties_unlocked(
    settings: Settings,
    *,
    request: MessageRequest,
) -> None:
    """After credit spend: Mini App chat + Telegram intro to both sides."""
    sender = request.sender
    owner = request.profile.user if request.profile else None
    if not sender or not owner:
        return

    chat_url = _app_link(settings, f"chat_{request.id}")
    owner_uname = (
        (request.profile.telegram_username if request.profile else None)
        or owner.telegram_username
    )
    sender_uname = sender.telegram_username
    owner_link = _tg_link(owner_uname)
    sender_link = _tg_link(sender_uname)

    # Intro to initiator (sender)
    lang_s = sender.language_code if sender.language_code in {"ru", "it"} else "ru"
    if lang_s == "it":
        text_s = (
            f"✅ Chat sbloccata con <b>{request.profile.name}</b>.\n"
            "Scrivi nell’app (traduzione automatica) "
            "oppure apri Telegram."
        )
        btn_app = "Apri chat"
        btn_tg = "Apri su Telegram"
    else:
        text_s = (
            f"✅ Чат с <b>{request.profile.name}</b> открыт.\n"
            "Пишите в Mini App (автоперевод) "
            "или перейдите в Telegram."
        )
        btn_app = "Открыть чат"
        btn_tg = "Открыть в Telegram"
    markup_s: dict = {"inline_keyboard": [[{"text": btn_app, "web_app": {"url": chat_url}}]]}
    if owner_link:
        markup_s["inline_keyboard"].append([{"text": btn_tg, "url": owner_link}])
    try:
        await send_message(settings, sender.telegram_id, text_s, reply_markup=markup_s)
    except Exception:
        logger.exception("Failed unlock notify to sender %s", sender.telegram_id)

    # Intro to recipient (profile owner)
    lang_o = owner.language_code if owner.language_code in {"ru", "it"} else "ru"
    sender_name = request.sender_name or sender.telegram_first_name or "—"
    if lang_o == "it":
        text_o = (
            f"✅ Chat aperta con <b>{sender_name}</b>.\n"
            "Continuate nell’app con traduzione automatica "
            "o su Telegram."
        )
        btn_app_o = "Apri chat"
        btn_tg_o = "Apri su Telegram"
    else:
        text_o = (
            f"✅ Чат с <b>{sender_name}</b> открыт.\n"
            "Продолжайте в Mini App с автопереводом "
            "или в Telegram."
        )
        btn_app_o = "Открыть чат"
        btn_tg_o = "Открыть в Telegram"
    markup_o: dict = {"inline_keyboard": [[{"text": btn_app_o, "web_app": {"url": chat_url}}]]}
    if sender_link:
        markup_o["inline_keyboard"].append([{"text": btn_tg_o, "url": sender_link}])
    try:
        await send_message(settings, owner.telegram_id, text_o, reply_markup=markup_o)
    except Exception:
        logger.exception("Failed unlock notify to owner %s", owner.telegram_id)

    # Best-effort: ensure bot username resolve doesn't block (unused but warms cache)
    try:
        await get_bot_username(settings)
    except Exception:
        pass


async def notify_admins_ad_submitted(
    settings: Settings,
    *,
    user: User,
    ad: AdRequest,
) -> None:
    admin_ids = settings.admin_ids
    if not admin_ids:
        return
    text = (
        f"📣 Новая заявка на рекламу\n"
        f"ID: {ad.id}\n"
        f"Бренд: {ad.title}\n"
        f"Категория: {ad.category}\n"
        f"tg_id: {user.telegram_id} @{user.telegram_username or '—'}"
    )
    for admin_id in admin_ids:
        try:
            await send_message(settings, admin_id, text, parse_mode=None)
        except Exception:
            logger.exception("Failed to notify admin %s about ad", admin_id)


async def notify_user_ad_approved(
    settings: Settings,
    *,
    user: User,
    ad: AdRequest,
    stars: int,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        text = (
            f"✅ La richiesta pubblicitaria <b>{ad.title}</b> è approvata.\n\n"
            f"Paga <b>{stars} ★</b> per lo slot di 48 ore.\n"
            "Ti inviamo la fattura Telegram Stars."
        )
    else:
        text = (
            f"✅ Заявка на рекламу <b>{ad.title}</b> одобрена.\n\n"
            f"Оплатите <b>{stars} ★</b> за слот на 48 часов.\n"
            "Счёт в Telegram Stars — следующим сообщением."
        )
    try:
        await send_message(settings, user.telegram_id, text)
    except Exception:
        logger.exception("Failed ad approve notify %s", user.telegram_id)


async def notify_user_ad_rejected(
    settings: Settings,
    *,
    user: User,
    ad: AdRequest,
    feedback: str,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        text = (
            f"Richiesta pubblicitaria rifiutata.\n\n"
            f"<b>Cosa correggere:</b>\n{feedback.strip()}\n\n"
            "Puoi inviare una nuova richiesta nell’app."
        )
    else:
        text = (
            f"Заявка на рекламу отклонена.\n\n"
            f"<b>Что поправить:</b>\n{feedback.strip()}\n\n"
            "Можно отправить новую заявку в Mini App."
        )
    try:
        await send_message(settings, user.telegram_id, text)
    except Exception:
        logger.exception("Failed ad reject notify %s", user.telegram_id)


async def notify_user_ad_activated(
    settings: Settings,
    *,
    user: User,
    ad: AdRequest,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        text = (
            f"📣 La pubblicità <b>{ad.title}</b> è online nel canale "
            "per 48 ore."
        )
    else:
        text = (
            f"📣 Реклама <b>{ad.title}</b> опубликована в канале "
            "на 48 часов."
        )
    try:
        await send_message(settings, user.telegram_id, text)
    except Exception:
        logger.exception("Failed ad activated notify %s", user.telegram_id)


async def notify_user_ad_expired(
    settings: Settings,
    *,
    user: User,
    ad: AdRequest,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    form_url = _app_link(settings, "ads")
    if lang == "it":
        text = (
            f"⏱ Lo slot di <b>{ad.title}</b> è terminato (48 ore).\n"
            "Vuoi pubblicare di nuovo? Apri il form nell’app."
        )
        btn = "Nuova richiesta"
    else:
        text = (
            f"⏱ Слот рекламы <b>{ad.title}</b> завершён (48 часов).\n"
            "Хотите разместить снова? Откройте форму в приложении."
        )
        btn = "Новая заявка"
    try:
        await send_message(
            settings,
            user.telegram_id,
            text,
            reply_markup=_webapp_button(form_url, btn),
        )
    except Exception:
        logger.exception("Failed ad expired notify %s", user.telegram_id)


async def notify_user_ad_reminder(
    settings: Settings,
    *,
    user: User,
    ad: AdRequest,
    kind: str,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    form_url = _app_link(settings, "ads")
    if lang == "it":
        text = (
            f"🔁 Vuoi pubblicare di nuovo <b>{ad.title}</b> nel canale "
            "Italian Dreamers?\nApri il form nell’app."
        )
        btn = "Pubblica di nuovo"
    else:
        text = (
            f"🔁 Хотите снова разместить <b>{ad.title}</b> в канале "
            "Italian Dreamers?\nОткройте форму в приложении."
        )
        btn = "Разместить снова"
    try:
        await send_message(
            settings,
            user.telegram_id,
            text,
            reply_markup=_webapp_button(form_url, btn),
        )
    except Exception:
        logger.exception("Failed ad reminder (%s) notify %s", kind, user.telegram_id)


async def notify_referrer_joined(
    settings: Settings,
    *,
    referrer: User,
    invited: User,
    total: int,
    bonus: int = 0,
) -> None:
    lang = referrer.language_code if referrer.language_code in {"ru", "it"} else "ru"
    name = html.escape(invited.telegram_first_name or "")
    if lang == "it":
        who = f"<b>{name}</b>" if name else "una nuova persona"
        text = f"🎉 {who} si è unito a Italian Dreamers con il tuo link.\n"
        if bonus:
            text += (
                f"Crediti per le lettere accreditati: <b>+{bonus}</b> "
                f"(saldo: <b>{referrer.message_credits}</b>).\n"
            )
        text += f"Persone invitate: <b>{total}</b>."
        btn = "Il mio link"
    else:
        who = f"<b>{name}</b>" if name else "новый участник"
        text = f"🎉 По вашей ссылке к Italian Dreamers присоединился(-ась) {who}.\n"
        if bonus:
            text += (
                f"Начислено кредитов на письма: <b>+{bonus}</b> "
                f"(баланс: <b>{referrer.message_credits}</b>).\n"
            )
        text += f"Всего приглашено: <b>{total}</b>."
        btn = "Моя ссылка"
    try:
        await send_message(
            settings,
            referrer.telegram_id,
            text,
            reply_markup=_webapp_button(_app_link(settings, "referral"), btn),
        )
    except Exception:
        logger.exception("Failed referral notify %s", referrer.telegram_id)
