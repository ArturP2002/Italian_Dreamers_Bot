"""Notify users and admins via Telegram Bot API (best-effort)."""

from __future__ import annotations

import html
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import Settings
from app.models import AdRequest, LegacyAnketa, MessageRequest, Profile, User
from app.services.telegram_api import TelegramApiError, get_bot_username, send_message

logger = logging.getLogger(__name__)


def _app_link(settings: Settings, startapp: str) -> str:
    # Telegram iOS web views load only the HTML for nested paths like /inbox/1,
    # so deep links always go through the root URL and the app routes by startapp.
    return f"{settings.webapp_url.rstrip('/')}/?startapp={startapp}"


def _webapp_button(url: str, label: str) -> dict:
    return {"inline_keyboard": [[{"text": label, "web_app": {"url": url}}]]}


def _channel_line(settings: Settings, lang: str) -> str:
    url = (settings.channel_url or "").strip()
    if not url:
        return ""
    if lang == "it":
        return f"\n\nCanale: {url}"
    return f"\n\nКанал: {url}"


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
    username = profile.telegram_username or user.telegram_username
    nick = f"@{username}" if username else "⚠️ нет ника"
    text = (
        f"🆕 Новая анкета на модерации\n"
        f"ID: {profile.id}\n"
        f"Имя: {name}, {profile.age}\n"
        f"{nick}\n"
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
            f"{_channel_line(settings, 'it')}"
        )
    else:
        text = (
            f"✅ Анкета <b>{profile.name}</b> одобрена.\n\n"
            f"Чтобы опубликовать её в канале, оплатите <b>{stars} ★</b>.\n"
            "Счёт в Telegram Stars — в следующем сообщении."
            f"{_channel_line(settings, 'ru')}"
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
            f"Profilo rifiutato.\n\n"
            f"<b>Cosa correggere:</b>\n{feedback.strip()}\n\n"
            "Puoi modificare il profilo nell’app e inviarlo di nuovo."
        )
    else:
        text = (
            f"Анкета отклонена.\n\n"
            f"<b>Что поправить:</b>\n{feedback.strip()}\n\n"
            "Исправьте анкету в Mini App и отправьте снова."
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
            f"{_channel_line(settings, 'it')}"
        )
    else:
        text = (
            f"📅 Дата публикации анкеты <b>{profile.name}</b>:\n"
            f"<b>{date_str}</b> (по Риму)."
            f"{_channel_line(settings, 'ru')}"
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
    extra = _channel_line(settings, lang)
    if lang == "it":
        text = f"🎉 Il profilo <b>{profile.name}</b> è stato pubblicato nel canale.{extra}"
    else:
        text = f"🎉 Анкета <b>{profile.name}</b> опубликована в канале.{extra}"
    try:
        await send_message(settings, user.telegram_id, text, disable_link_preview=True)
    except Exception:
        logger.exception("Failed to notify user %s about publish", user.telegram_id)


async def notify_unpaid_reminder(
    settings: Settings,
    *,
    user: User,
    profile: Profile,
    day: int,
) -> bool:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    extra = _channel_line(settings, lang)
    left = max(30 - day, 0)
    app_url = _app_link(settings, "home")
    if lang == "it":
        text = (
            f"⏰ Promemoria: il profilo <b>{html.escape(profile.name, quote=False)}</b> "
            f"è approvato, manca il pagamento della pubblicazione.\n"
            f"Senza pagamento verrà eliminato tra {left} giorni.{extra}"
        )
        btn = "Paga la pubblicazione"
    else:
        text = (
            f"⏰ Напоминание: анкета <b>{html.escape(profile.name, quote=False)}</b> "
            f"одобрена, осталось оплатить публикацию.\n"
            f"Без оплаты анкета будет удалена через {left} дн.{extra}"
        )
        btn = "Оплатить публикацию"
    try:
        await send_message(
            settings,
            user.telegram_id,
            text,
            reply_markup=_webapp_button(app_url, btn),
            disable_link_preview=True,
        )
        return True
    except Exception:
        logger.exception("Failed unpaid reminder day %s for %s", day, user.telegram_id)
        return False


async def notify_unpaid_deleted(
    settings: Settings,
    *,
    user: User,
    profile_name: str,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    extra = _channel_line(settings, lang)
    name = html.escape(profile_name, quote=False)
    if lang == "it":
        text = (
            f"Il profilo <b>{name}</b> è stato eliminato perché non è stato pagato entro 30 giorni. "
            f"Puoi compilarne uno nuovo.{extra}"
        )
    else:
        text = (
            f"Анкета <b>{name}</b> удалена: публикация не была оплачена за 30 дней. "
            f"Можно заполнить заново.{extra}"
        )
    try:
        await send_message(settings, user.telegram_id, text, disable_link_preview=True)
    except Exception:
        logger.exception("Failed unpaid-deleted notify for %s", user.telegram_id)


async def notify_user_profile_deleted(
    settings: Settings,
    *,
    user: User,
    profile_name: str,
) -> bool:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    name = html.escape(profile_name, quote=False)
    if lang == "it":
        text = (
            f"Il profilo <b>{name}</b> è stato rimosso dal canale ed eliminato. "
            "Se vuoi, puoi compilarne uno nuovo."
        )
    else:
        text = (
            f"Анкета <b>{name}</b> снята с публикации и удалена. "
            "Если захотите — можно заполнить новую."
        )
    try:
        await send_message(settings, user.telegram_id, text)
    except Exception:
        logger.exception("Failed to notify user %s about take-down", user.telegram_id)
        return False
    return True


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


def _replied_verb(lang: str, gender: str | None) -> str:
    if lang == "it":
        if gender == "female":
            return "ti ha risposto"
        if gender == "male":
            return "ti ha risposto"
        return "ti ha risposto"
    if gender == "female":
        return "ответила"
    if gender == "male":
        return "ответил"
    return "ответил(а)"


async def notify_recipient_rejected(
    settings: Settings,
    *,
    initiator: User,
    request: MessageRequest,
    credit_refunded: bool = False,
) -> None:
    lang = initiator.language_code if initiator.language_code in {"ru", "it"} else "ru"
    profile_name = request.profile.name if request.profile else "—"
    if lang == "it":
        text = f"La lettera a <b>{html.escape(profile_name)}</b> non ha ricevuto interesse."
        if credit_refunded:
            text += " Il credito dell’incontro è tornato sul saldo."
        else:
            text += " Nessun pagamento."
    else:
        text = f"Письмо к <b>{html.escape(profile_name)}</b> не заинтересовало."
        if credit_refunded:
            text += " Знакомство вернулось на баланс."
        else:
            text += " Оплаты нет."
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
    from pathlib import Path

    from app.services.telegram_api import send_photo_file, send_photo_media

    lang = initiator.language_code if initiator.language_code in {"ru", "it"} else "ru"
    profile_name = request.profile.name if request.profile else "—"
    gender = request.profile.gender if request.profile else None
    app_url = _app_link(settings, f"inbox_{request.id}")
    safe_name = html.escape(profile_name)
    quote = (request.reply_text or "").strip().replace("\n", " ")
    if len(quote) > 60:
        quote = quote[:57].rstrip() + "…"
    quote_html = html.escape(quote) if quote else ""
    if lang == "it":
        text = f"💌 <b>{safe_name}</b> {_replied_verb(lang, gender)}!"
        if quote_html:
            text += f"\n«{quote_html}»"
        text += "\nApri la chat con un regalo o <b>Dreamers Plus</b>."
        btn = "Apri la risposta"
    else:
        text = f"💌 <b>{safe_name}</b> {_replied_verb(lang, gender)} тебе!"
        if quote_html:
            text += f"\n«{quote_html}»"
        text += "\nОткрой переписку подарком или <b>Dreamers Plus</b>."
        btn = "Открыть ответ"
    markup = _webapp_button(app_url, btn)
    photo_source = None
    if request.profile and request.profile.photos:
        first = sorted(request.profile.photos, key=lambda p: p.position)[0]
        fid = first.file_id or ""
        if fid.startswith("local:"):
            path = Path(__file__).resolve().parents[2] / "media" / "profiles" / fid.removeprefix("local:")
            if path.exists():
                photo_source = path
        elif fid:
            photo_source = fid
    try:
        if isinstance(photo_source, Path):
            await send_photo_file(
                settings, initiator.telegram_id, photo_source, caption=text, reply_markup=markup
            )
        elif isinstance(photo_source, str):
            await send_photo_media(
                settings, initiator.telegram_id, photo_source, caption=text, reply_markup=markup
            )
        else:
            await send_message(settings, initiator.telegram_id, text, reply_markup=markup)
    except Exception:
        logger.exception("Failed to notify initiator %s about reply", initiator.telegram_id)
        try:
            await send_message(settings, initiator.telegram_id, text, reply_markup=markup)
        except Exception:
            logger.exception("Fallback text notify also failed for %s", initiator.telegram_id)


async def notify_letter_expired(
    settings: Settings,
    *,
    request: MessageRequest,
) -> None:
    """Sender: credit returned. Recipient: conversation closed until a late reply."""
    sender = request.sender
    owner = request.profile.user if request.profile else None
    profile_name = request.profile.name if request.profile else "—"
    safe_name = html.escape(profile_name)
    days = 3
    app_url = _app_link(settings, f"inbox_{request.id}")

    if sender:
        lang_s = sender.language_code if sender.language_code in {"ru", "it"} else "ru"
        if lang_s == "it":
            text_s = (
                f"⏱ Nessuna risposta da <b>{safe_name}</b> in {days} giorni.\n"
                f"L’incontro è tornato sul saldo (ora: <b>{sender.message_credits}</b>). "
                "La chat è chiusa. Se risponderà più tardi, riceverai una notifica "
                "e potrai riaprirla."
            )
            btn_s = "I miei incontri"
        else:
            text_s = (
                f"⏱ Нет ответа от <b>{safe_name}</b> за {days} дня.\n"
                f"Знакомство вернулось на баланс (сейчас: <b>{sender.message_credits}</b>). "
                "Переписка закрыта. Если ответит позже — придёт уведомление, "
                "и вы сможете открыть её снова."
            )
            btn_s = "Мои знакомства"
        try:
            await send_message(
                settings,
                sender.telegram_id,
                text_s,
                reply_markup=_webapp_button(app_url, btn_s),
            )
        except Exception:
            logger.exception("Failed expire notify to sender %s", sender.telegram_id)

    if owner:
        sender_name = request.sender_name or (sender.telegram_first_name if sender else None) or "—"
        safe_sender = html.escape(sender_name)
        lang_o = owner.language_code if owner.language_code in {"ru", "it"} else "ru"
        owner_gender = request.profile.gender if request.profile else None
        if lang_o == "it":
            text_o = (
                f"⏱ Non hai risposto a <b>{safe_sender}</b> entro {days} giorni: "
                "la chat è chiusa. Se scrivi ora, riceverà una notifica e potrà "
                "riaprirla (1 credito, pagamento o Dreamers Plus)."
            )
            btn_o = "Apri lettera"
        else:
            silent = (
                "не ответила"
                if owner_gender == "female"
                else "не ответил"
                if owner_gender == "male"
                else "не ответили"
            )
            text_o = (
                f"⏱ Ты {silent} за {days} дня <b>{safe_sender}</b> — переписка закрылась. "
                "Если напишешь, он получит уведомление и сможет открыть её снова "
                "(1 знакомство, оплата или Dreamers Plus)."
            )
            btn_o = "Открыть письмо"
        try:
            await send_message(
                settings,
                owner.telegram_id,
                text_o,
                reply_markup=_webapp_button(app_url, btn_o),
            )
        except Exception:
            logger.exception("Failed expire notify to owner %s", owner.telegram_id)


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
    """After unlock: Mini App chat link only (Telegram contacts are opt-in)."""
    sender = request.sender
    owner = request.profile.user if request.profile else None
    if not sender or not owner:
        return

    chat_url = _app_link(settings, f"chat_{request.id}")

    lang_s = sender.language_code if sender.language_code in {"ru", "it"} else "ru"
    if lang_s == "it":
        text_s = (
            f"✅ Chat sbloccata con <b>{request.profile.name}</b>.\n"
            "Scrivi nell’app (traduzione automatica)."
        )
        btn_app = "Apri chat"
    else:
        text_s = (
            f"✅ Чат с <b>{request.profile.name}</b> открыт.\n"
            "Пишите в Mini App (автоперевод)."
        )
        btn_app = "Открыть чат"
    markup_s: dict = {"inline_keyboard": [[{"text": btn_app, "web_app": {"url": chat_url}}]]}
    try:
        await send_message(settings, sender.telegram_id, text_s, reply_markup=markup_s)
    except Exception:
        logger.exception("Failed unlock notify to sender %s", sender.telegram_id)

    lang_o = owner.language_code if owner.language_code in {"ru", "it"} else "ru"
    sender_name = request.sender_name or sender.telegram_first_name or "—"
    if lang_o == "it":
        text_o = (
            f"✅ Chat aperta con <b>{sender_name}</b>.\n"
            "Continuate nell’app con traduzione automatica."
        )
        btn_app_o = "Apri chat"
    else:
        text_o = (
            f"✅ Чат с <b>{sender_name}</b> открыт.\n"
            "Продолжайте в Mini App с автопереводом."
        )
        btn_app_o = "Открыть чат"
    markup_o: dict = {"inline_keyboard": [[{"text": btn_app_o, "web_app": {"url": chat_url}}]]}
    try:
        await send_message(settings, owner.telegram_id, text_o, reply_markup=markup_o)
    except Exception:
        logger.exception("Failed unlock notify to owner %s", owner.telegram_id)


async def notify_telegram_shared(
    settings: Settings,
    *,
    request: MessageRequest,
    sharer: User,
) -> None:
    """Peer gets a bot notice that someone shared their Telegram."""
    sender = request.sender
    owner = request.profile.user if request.profile else None
    if not sender or not owner or not request.profile:
        return
    peer = owner if sharer.id == sender.id else sender
    sharer_name = (
        request.profile.name
        if sharer.id == owner.id
        else (request.sender_name or sharer.telegram_first_name or "—")
    )
    uname = (sharer.telegram_username or "").strip().lstrip("@")
    if sharer.id == owner.id:
        uname = (request.profile.telegram_username or uname or "").strip().lstrip("@")
    link = _tg_link(uname)
    chat_url = _app_link(settings, f"chat_{request.id}")
    lang = peer.language_code if peer.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        text = f"💌 <b>{sharer_name}</b> ti ha dato il suo Telegram"
        btn = f"Scrivi a {sharer_name} su Telegram" if link else "Apri chat"
    else:
        text = f"💌 <b>{sharer_name}</b> дал(а) тебе свой Telegram"
        btn = f"Написать {sharer_name} в Telegram" if link else "Открыть чат"
    markup: dict = {"inline_keyboard": []}
    if link:
        markup["inline_keyboard"].append([{"text": btn, "url": link}])
    markup["inline_keyboard"].append(
        [{"text": "Apri chat" if lang == "it" else "Открыть чат", "web_app": {"url": chat_url}}]
    )
    try:
        await send_message(settings, peer.telegram_id, text, reply_markup=markup)
    except Exception:
        logger.exception("Failed telegram-shared notify to %s", peer.telegram_id)


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
    top_days: int = 0,
) -> None:
    lang = referrer.language_code if referrer.language_code in {"ru", "it"} else "ru"
    name = html.escape(invited.telegram_first_name or "")
    if lang == "it":
        who = f"<b>{name}</b>" if name else "una nuova persona"
        text = f"🎉 {who} si è unito a Italian Dreamers con il tuo link.\n"
        if top_days:
            text += f"Bonus top catalogo: <b>+{top_days} giorni</b>.\n"
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
        if top_days:
            text += f"Бонус топа в каталоге: <b>+{top_days} дн.</b>\n"
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


async def notify_match(
    settings: Settings,
    *,
    a: User,
    b: User,
    liked_profile: Profile,
    viewer_profile: Profile | None,
) -> None:
    async def _one(user: User, other: User, other_name: str) -> None:
        lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
        name = html.escape(other_name or other.telegram_first_name or "—")
        if lang == "it":
            text = f"❤️ È un match con <b>{name}</b>!\nAprite i profili nel catalogo."
            btn = "Apri catalogo"
        else:
            text = f"❤️ У вас взаимная симпатия с <b>{name}</b>!\nОткройте анкеты в каталоге."
            btn = "Открыть каталог"
        start = f"catalog_{liked_profile.id if user.id == a.id else (viewer_profile.id if viewer_profile else liked_profile.id)}"
        try:
            await send_message(
                settings,
                user.telegram_id,
                text,
                reply_markup=_webapp_button(_app_link(settings, start), btn),
            )
        except Exception:
            logger.exception("Failed match notify %s", user.telegram_id)

    await _one(a, b, liked_profile.name)
    await _one(b, a, viewer_profile.name if viewer_profile else (a.telegram_first_name or "—"))


async def notify_legacy_invite(settings: Settings, *, anketa: LegacyAnketa, link: str) -> None:
    nick = (anketa.telegram_username or "").strip().lstrip("@")
    text = (
        f"📩 Старая анкета: {anketa.name}\n"
        f"Инвайт в Mini App:\n{link}"
    )
    if nick:
        # Cannot DM without knowing telegram_id; admins get the link to forward.
        text = f"@{nick}\n" + text
    for admin_id in settings.admin_ids:
        try:
            await send_message(settings, admin_id, text, parse_mode=None)
        except Exception:
            logger.exception("Failed legacy invite notify admin %s", admin_id)


async def notify_initiator_chat_opened(
    settings: Settings,
    *,
    initiator: User,
    request: MessageRequest,
) -> None:
    lang = initiator.language_code if initiator.language_code in {"ru", "it"} else "ru"
    profile_name = request.profile.name if request.profile else "—"
    app_url = _app_link(settings, f"chat_{request.id}")
    if lang == "it":
        text = (
            f"✨ <b>{html.escape(profile_name)}</b> ti ha risposto.\n\n"
            "Con l’abbonamento illimitato la chat è già aperta."
        )
        btn = "Apri chat"
    else:
        text = (
            f"✨ Вам ответил(а) <b>{html.escape(profile_name)}</b>.\n\n"
            "С безлимитом чат уже открыт."
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
        logger.exception("Failed to notify initiator %s about opened chat", initiator.telegram_id)


async def notify_verification_result(
    settings: Settings,
    *,
    user: User,
    profile: Profile,
    approved: bool,
    feedback: str | None = None,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if approved:
        text = (
            "✅ Il tuo profilo è verificato. In catalogo compare il badge."
            if lang == "it"
            else "✅ Анкета подтверждена. В каталоге появится значок."
        )
    else:
        extra = html.escape((feedback or "").strip())
        if lang == "it":
            text = "❌ Verifica non accettata. Carica un selfie più nitido."
            if extra:
                text += f"\n{extra}"
        else:
            text = "❌ Проверку не приняли. Загрузите более чёткое селфи."
            if extra:
                text += f"\n{extra}"
    try:
        await send_message(settings, user.telegram_id, text)
    except Exception:
        logger.exception("Failed verification notify %s", user.telegram_id)


async def notify_unlimited_queued(
    settings: Settings,
    *,
    user: User,
    profile: Profile,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        text = (
            f"✅ Profilo <b>{html.escape(profile.name)}</b> approvato.\n"
            "Con l’abbonamento illimitato entra in coda e in cima al catalogo, senza fattura extra."
        )
    else:
        text = (
            f"✅ Анкета <b>{html.escape(profile.name)}</b> одобрена.\n"
            "С безлимитом она в очереди и в топе каталога — без отдельного счёта."
        )
    try:
        await send_message(settings, user.telegram_id, text)
    except Exception:
        logger.exception("Failed unlimited-queued notify %s", user.telegram_id)
