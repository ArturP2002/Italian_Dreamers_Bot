"""/terms, /support, /paysupport — required by Telegram for bots that accept payments."""

from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import BotCommand, Message

from app.config import Settings, get_settings

router = Router(name="info")

COMMANDS = {
    "ru": [
        BotCommand(command="start", description="Открыть Italian Dreamers"),
        BotCommand(command="terms", description="Условия использования и оплаты"),
        BotCommand(command="support", description="Поддержка"),
        BotCommand(command="paysupport", description="Вопросы по оплате"),
    ],
    "it": [
        BotCommand(command="start", description="Apri Italian Dreamers"),
        BotCommand(command="terms", description="Termini di utilizzo e pagamento"),
        BotCommand(command="support", description="Assistenza"),
        BotCommand(command="paysupport", description="Domande sui pagamenti"),
    ],
}


async def set_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(COMMANDS["ru"])
    for lang, commands in COMMANDS.items():
        await bot.set_my_commands(commands, language_code=lang)


def _lang(message: Message) -> str:
    code = (message.from_user.language_code or "ru")[:2] if message.from_user else "ru"
    return code if code in {"ru", "it"} else "ru"


def _support_contact(settings: Settings) -> str:
    username = settings.support_username.strip().lstrip("@")
    if username:
        return f"@{username}"
    admin_id = next((p.strip() for p in settings.admin_telegram_ids.split(",") if p.strip()), None)
    if admin_id is None:
        return ""
    return f'<a href="tg://user?id={admin_id}">admin</a>'


def _terms_text(settings: Settings, lang: str) -> str:
    prices = {
        "publish": settings.price_profile_publish_stars,
        "credit": settings.price_message_credit_stars,
        "size": settings.message_pack_size,
        "pack": settings.price_message_pack_10_stars,
        "ad": settings.price_ad_slot_stars,
    }
    if lang == "it":
        return (
            "<b>Termini di utilizzo — Italian Dreamers</b>\n\n"
            "1. Italian Dreamers aiuta italiani e russofoni a conoscersi: i profili vengono "
            "pubblicati nel canale, la comunicazione avviene tramite lettere e chat nell'app.\n\n"
            "2. Il servizio è riservato ai maggiori di 18 anni. Il profilo deve contenere dati "
            "veri e foto tue.\n\n"
            "3. Ogni profilo viene verificato manualmente da un moderatore. Possiamo rifiutare "
            "un profilo, rimuoverlo dal canale ed eliminarlo, oppure limitare l'accesso per dati "
            "falsi, truffe, spam, insulti o contatti condivisi aggirando il servizio.\n\n"
            "4. <b>Servizi a pagamento</b> (Telegram Stars):\n"
            f"• pubblicazione del profilo nel canale — {prices['publish']} ⭐ "
            "(si paga dopo l'approvazione del moderatore);\n"
            f"• 1 messaggio (apre la chat con chi ha risposto alla tua lettera) — {prices['credit']} ⭐;\n"
            f"• pacchetto da {prices['size']} messaggi — {prices['pack']} ⭐;\n"
            f"• spazio pubblicitario nel canale — {prices['ad']} ⭐.\n"
            "I crediti non scadono; il saldo è visibile nell'app.\n\n"
            "5. I servizi sono digitali e vengono forniti subito dopo il pagamento. Se il "
            "pagamento è andato a buon fine ma il servizio non è stato fornito per un problema "
            "tecnico (profilo non pubblicato, crediti non accreditati), correggiamo l'errore o "
            "rimborsiamo le Stars — scrivi a /paysupport. Le Stars per un profilo rimosso per "
            "violazione delle regole non vengono rimborsate.\n\n"
            "6. Quando un profilo viene rimosso dal canale, foto, video e testo vengono eliminati.\n\n"
            "Assistenza: /support · Pagamenti: /paysupport"
        )
    return (
        "<b>Условия использования — Italian Dreamers</b>\n\n"
        "1. Italian Dreamers помогает русскоязычным и итальянцам знакомиться: анкеты "
        "публикуются в канале, общение — через письма и чат в приложении.\n\n"
        "2. Сервисом можно пользоваться с 18 лет. В анкете должны быть правдивые данные "
        "и ваши собственные фото.\n\n"
        "3. Каждую анкету вручную проверяет модератор. Мы можем отклонить анкету, снять её "
        "с публикации и удалить или ограничить доступ за фейковые данные, мошенничество, спам, "
        "оскорбления или обмен контактами в обход сервиса.\n\n"
        "4. <b>Платные услуги</b> (Telegram Stars):\n"
        f"• публикация анкеты в канале — {prices['publish']} ⭐ "
        "(оплачивается после одобрения модератором);\n"
        f"• 1 сообщение (открывает чат с тем, кто ответил на ваше письмо) — {prices['credit']} ⭐;\n"
        f"• пакет {prices['size']} сообщений — {prices['pack']} ⭐;\n"
        f"• рекламное размещение в канале — {prices['ad']} ⭐.\n"
        "Сообщения из пакета не сгорают, остаток виден в приложении.\n\n"
        "5. Услуги цифровые и оказываются сразу после оплаты. Если оплата прошла, а услуга "
        "не оказана по технической причине (анкета не опубликована, сообщения не начислены), "
        "мы исправим ошибку или вернём звёзды — напишите в /paysupport. Звёзды за анкету, "
        "снятую за нарушение правил, не возвращаются.\n\n"
        "6. Когда анкета снимается с публикации, её фото, видео и текст удаляются.\n\n"
        "Поддержка: /support · Оплата: /paysupport"
    )


@router.message(Command("terms"))
async def cmd_terms(message: Message) -> None:
    await message.answer(_terms_text(get_settings(), _lang(message)), disable_web_page_preview=True)


@router.message(Command("support"))
async def cmd_support(message: Message) -> None:
    contact = _support_contact(get_settings())
    if _lang(message) == "it":
        text = (
            "<b>Assistenza Italian Dreamers</b>\n\n"
            f"Per domande sul profilo, sulle lettere o sulla chat scrivi a {contact}.\n"
            "Descrivi il problema e, se puoi, allega uno screenshot.\n\n"
            "Domande sui pagamenti: /paysupport · Termini: /terms"
        )
    else:
        text = (
            "<b>Поддержка Italian Dreamers</b>\n\n"
            f"По вопросам анкеты, писем или чата напишите {contact}.\n"
            "Опишите проблему и, если можно, приложите скриншот.\n\n"
            "Вопросы по оплате: /paysupport · Условия: /terms"
        )
    await message.answer(text, disable_web_page_preview=True)


@router.message(Command("paysupport"))
async def cmd_paysupport(message: Message) -> None:
    contact = _support_contact(get_settings())
    if _lang(message) == "it":
        text = (
            "<b>Pagamenti</b>\n\n"
            f"Per domande su un pagamento in Stars o per un rimborso scrivi a {contact}.\n"
            "Indica data e ora del pagamento e cosa hai acquistato (pubblicazione, messaggi, "
            "pubblicità).\n\n"
            "Il supporto di Telegram non può aiutare con gli acquisti fatti in questo bot.\n\n"
            "Termini: /terms"
        )
    else:
        text = (
            "<b>Вопросы по оплате</b>\n\n"
            f"По вопросам оплаты в Stars или возврата напишите {contact}.\n"
            "Укажите дату и время платежа и что вы покупали (публикация, сообщения, реклама).\n\n"
            "Поддержка Telegram не может помочь с покупками в этом боте.\n\n"
            "Условия: /terms"
        )
    await message.answer(text, disable_web_page_preview=True)
