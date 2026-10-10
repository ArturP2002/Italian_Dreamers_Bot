#!/usr/bin/env python3
"""Build Italian Dreamers user + admin PDF manual with Mini App screenshots."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "docs" / "manual_screenshots"
OUT = ROOT / "Italian_Dreamers_Инструкция.pdf"

FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_ITALIC = "/System/Library/Fonts/Supplemental/Arial Italic.ttf"

INK = HexColor("#1A1511")
MUTED = HexColor("#5C534C")
ACCENT = HexColor("#8B6914")
CREAM = HexColor("#F4EFE6")
CARD = HexColor("#2A221C")
RULE = HexColor("#D9D0C4")


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("Manual", FONT_REG))
    pdfmetrics.registerFont(TTFont("Manual-Bold", FONT_BOLD))
    pdfmetrics.registerFont(TTFont("Manual-Italic", FONT_ITALIC))


def styles():
    base = getSampleStyleSheet()
    s = {
        "cover_brand": ParagraphStyle(
            "cover_brand",
            parent=base["Normal"],
            fontName="Manual-Bold",
            fontSize=28,
            leading=34,
            textColor=white,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["Normal"],
            fontName="Manual",
            fontSize=13,
            leading=18,
            textColor=HexColor("#E8DFD2"),
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Manual-Bold",
            fontSize=20,
            leading=26,
            textColor=INK,
            spaceBefore=4,
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Manual-Bold",
            fontSize=14,
            leading=19,
            textColor=INK,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "h3",
            parent=base["Heading3"],
            fontName="Manual-Bold",
            fontSize=12,
            leading=16,
            textColor=ACCENT,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Manual",
            fontSize=10,
            leading=14,
            textColor=INK,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontName="Manual",
            fontSize=10,
            leading=13.5,
            textColor=INK,
            leftIndent=2,
            spaceAfter=2,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["Normal"],
            fontName="Manual-Italic",
            fontSize=8.5,
            leading=11,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceBefore=3,
            spaceAfter=10,
        ),
        "note": ParagraphStyle(
            "note",
            parent=base["Normal"],
            fontName="Manual",
            fontSize=9.5,
            leading=13,
            textColor=INK,
            backColor=CREAM,
            borderPadding=6,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "toc": ParagraphStyle(
            "toc",
            parent=base["Normal"],
            fontName="Manual",
            fontSize=11,
            leading=18,
            textColor=INK,
            leftIndent=8,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontName="Manual",
            fontSize=8,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }
    return s


def shot(name: str, caption: str, width: float = 72 * mm) -> list:
    path = SHOTS / f"{name}.png"
    if not path.exists():
        return [Paragraph(f"<i>[нет скриншота: {name}]</i>", styles()["caption"])]
    img = Image(str(path), width=width, height=width * (844 / 390))
    img.hAlign = "CENTER"
    return [KeepTogether([img, Paragraph(caption, styles()["caption"])])]


def bullets(items: list[str], st) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(x, st["bullet"]), leftIndent=12, value="•") for x in items],
        bulletType="bullet",
        start="•",
        leftIndent=10,
        spaceBefore=2,
        spaceAfter=8,
    )


def section_banner(title: str) -> Table:
    data = [[Paragraph(title, ParagraphStyle(
        "banner",
        fontName="Manual-Bold",
        fontSize=16,
        leading=20,
        textColor=white,
        alignment=TA_LEFT,
    ))]]
    t = Table(data, colWidths=[170 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CARD),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("ROUNDEDCORNERS", [6, 6, 6, 6]),
            ]
        )
    )
    return t


def add_page_decorations(canvas, doc):
    canvas.saveState()
    page = canvas.getPageNumber()
    if page > 1:
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.6)
        canvas.line(18 * mm, A4[1] - 12 * mm, A4[0] - 18 * mm, A4[1] - 12 * mm)
        canvas.setFont("Manual", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, A4[1] - 10 * mm, "Italian Dreamers — инструкция")
        canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 10 * mm, f"{page}")
        canvas.line(18 * mm, 12 * mm, A4[0] - 18 * mm, 12 * mm)
        canvas.drawCentredString(A4[0] / 2, 7 * mm, "Для пользователей и администраторов Mini App")
    canvas.restoreState()


def cover_page(story, st):
    story.append(Spacer(1, 28 * mm))
    block = Table(
        [[
            Paragraph("ITALIAN DREAMERS", st["cover_brand"]),
        ], [
            Paragraph("Telegram Mini App · знакомства Россия ↔ Италия", st["cover_sub"]),
        ], [
            Spacer(1, 6),
        ], [
            Paragraph("Инструкция по работе", ParagraphStyle(
                "cover_h", parent=st["cover_brand"], fontSize=22, leading=28,
            )),
        ], [
            Paragraph(
                "Часть 1 — для пользователей<br/>Часть 2 — для администраторов",
                st["cover_sub"],
            ),
        ]],
        colWidths=[170 * mm],
    )
    block.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CARD),
                ("TOPPADDING", (0, 0), (-1, 0), 28),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 28),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(block)
    story.append(Spacer(1, 16 * mm))
    story.append(
        Paragraph(
            "Документ описывает полный путь пользователя в Mini App "
            "(вход, анкета, письма, чат, кредиты, рефералы, реклама) "
            "и рабочие сценарии модератора в админ-панели.",
            st["body"],
        )
    )
    story.append(
        Paragraph(
            "Скриншоты сделаны с реального интерфейса приложения. "
            "Цены в Telegram Stars настраиваются в конфигурации сервиса и могут отличаться "
            "от тестовых значений на скриншотах.",
            st["note"],
        )
    )
    story.append(PageBreak())


def toc(story, st):
    story.append(Paragraph("Содержание", st["h1"]))
    items = [
        "1. Коротко о сервисе",
        "2. Как открыть Mini App",
        "3. Выбор языка и главная",
        "4. Создание и публикация анкеты",
        "5. Мои знакомства: письма и ответы",
        "6. Чат, перевод и Telegram-контакт",
        "7. Кредиты сообщений",
        "8. Реферальная программа",
        "9. Реклама в канале",
        "10. Ограничения и поддержка",
        "11. Админка: вход и структура",
        "12. Модерация анкет",
        "13. Очередь и публикация",
        "14. Реклама, жалобы, пользователи, платежи, статистика",
        "15. Типовые сценарии администратора",
    ]
    for item in items:
        story.append(Paragraph(item, st["toc"]))
    story.append(PageBreak())


def build() -> Path:
    register_fonts()
    st = styles()
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Italian Dreamers — инструкция",
        author="Italian Dreamers",
    )
    story: list = []

    cover_page(story, st)
    toc(story, st)

    # -------- USER PART --------
    story.append(section_banner("Часть 1. Как пользоваться ботом пользователям"))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("1. Коротко о сервисе", st["h1"]))
    story.append(
        Paragraph(
            "<b>Italian Dreamers</b> — Telegram-бот и Mini App для знакомств между "
            "Россией и Италией. Основная работа происходит не в чате с командами, "
            "а внутри Mini App: анкета, письма, ответы, чат с автопереводом, кредиты, "
            "рефералы и реклама в канале.",
            st["body"],
        )
    )
    story.append(bullets([
        "Анкета публикуется в Telegram-канале после модерации и оплаты.",
        "Знакомство начинается с письма — без телефона и @username в тексте.",
        "Когда второй человек ответил, инициатор открывает чат кредитом (или покупкой).",
        "В чате доступен перевод; после открытия можно перейти в Telegram собеседника.",
        "Интерфейс доступен на русском и итальянском.",
    ], st))

    story.append(Paragraph("2. Как открыть Mini App", st["h1"]))
    story.append(
        Paragraph(
            "В Telegram найдите бота Italian Dreamers и отправьте команду <b>/start</b> "
            "(или <b>/app</b>). Бот ответит приветствием и кнопкой "
            "<b>«Открыть Italian Dreamers»</b> — нажмите её, чтобы запустить Mini App.",
            st["body"],
        )
    )
    story.append(bullets([
        "Если вы пришли по реферальной ссылке вида <b>ref_…</b>, бот засчитает приглашение автоматически.",
        "Если вы нажали «Написать» под анкетой в канале, откроется экран письма к этой анкете.",
        "С телефона Mini App открывается внутри Telegram; на десктопе — в окне WebApp.",
    ], st))

    story.append(Paragraph("3. Выбор языка и главная", st["h1"]))
    story.append(
        Paragraph(
            "При первом входе показывается брендовый экран. Выберите язык кнопкой "
            "<b>Войти</b> (русский) или <b>Entra</b> (итальянский). Позже язык можно "
            "переключить переключателем на главной: «Русская версия / Versione italiana».",
            st["body"],
        )
    )
    story.extend(shot("01_language", "Рис. 1. Стартовый экран и выбор языка (Войти / Entra)"))

    story.append(
        Paragraph(
            "На главной видны приветствие, статус анкеты и основные разделы. "
            "Пока анкета не создана или отклонена — крупная карточка ведёт в мастер анкеты. "
            "После публикации на первом плане — «Мои знакомства».",
            st["body"],
        )
    )
    story.extend(shot("02_home_draft", "Рис. 2. Главная при незаполненной / черновой анкете"))
    story.extend(shot("09_home_published", "Рис. 3. Главная при опубликованной анкете"))

    story.append(Paragraph("Статусы анкеты на главной", st["h3"]))
    story.append(bullets([
        "<b>Черновик</b> — можно продолжить заполнение.",
        "<b>На модерации</b> — анкета отправлена, ждите решения.",
        "<b>Одобрена / ожидает оплаты</b> — оплатите публикацию (счёт в чате с ботом, Telegram Stars).",
        "<b>В очереди</b> — оплата получена, дату публикации назначит администратор.",
        "<b>Опубликована</b> — анкета в канале, можно получать письма.",
        "<b>Отклонена</b> — исправьте анкету по комментарию модератора и отправьте снова.",
    ], st))

    story.append(Paragraph("4. Создание и публикация анкеты", st["h1"]))
    story.append(
        Paragraph(
            "Откройте «Создать анкету» / «Продолжить анкету». Мастер состоит из коротких шагов: "
            "пол и возраст 18+, советы, имя, возраст, рост, страна/город, профессия, "
            "семейное положение и дети, «о себе», кого ищете, видео-приветствие (по желанию), "
            "вопрос-ответ для заставки канала, 3 фото, согласие и Telegram username.",
            st["body"],
        )
    )
    story.append(bullets([
        "Оплата публикации списывается <b>только после одобрения</b> модератором.",
        "В анкете и письмах нельзя указывать телефон, @username и внешние ссылки — система блокирует контакты.",
        "После отправки вы увидите карточку «Анкета отправлена» и превью данных.",
        "Когда модератор одобрит анкету, на главной появится кнопка «Оплатить публикацию», "
        "а в чат с ботом придёт счёт в Stars.",
    ], st))
    story.extend(shot("03_profile_intro", "Рис. 4. Анкета отправлена на модерацию — превью данных"))
    story.extend(shot("13_my_profile", "Рис. 5. «Моя анкета» после публикации (просмотр своей карточки)"))

    story.append(
        Paragraph(
            "<b>Важно:</b> публикация в канале включает уникальную заставку (вопрос и ответ), "
            "альбом анкеты (первым идёт видео-приветствие, если оно записано, затем фото) с текстом, "
            "а также кнопку «Написать», которая открывает Mini App на экране письма.",
            st["note"],
        )
    )

    story.append(Paragraph("5. Мои знакомства: письма и ответы", st["h1"]))
    story.append(
        Paragraph(
            "Раздел «Мои знакомства» — входящие и исходящие письма. "
            "Чтобы написать человеку из канала, нажмите кнопку под его постом: откроется форма письма.",
            st["body"],
        )
    )
    story.extend(shot("08_write_letter", "Рис. 6. Форма «Написать» письмо к анкете из канала"))
    story.append(bullets([
        "Укажите имя, возраст (от 18), фото и текст. Контакты в тексте запрещены.",
        "Если у вас уже есть анкета, письмо может уйти от данных анкеты.",
        "Получатель видит письмо во «Входящих» и может ответить бесплатно или отметить «Не интересно».",
        "Ответ адресата для инициатора платный: нужно списать 1 кредит или купить пакет.",
    ], st))
    story.extend(shot("10_inbox", "Рис. 7. Список знакомств (входящие / исходящие)"))
    story.extend(shot("11_message_card", "Рис. 8. Карточка письма: перевод, ответ, открытие чата"))

    story.append(Paragraph("Статусы писем", st["h3"]))
    story.append(bullets([
        "<b>Ожидает ответа</b> — письмо отправлено, ответа ещё нет.",
        "<b>Ответили — оплатите</b> — есть ответ, нужно открыть чат кредитом/покупкой.",
        "<b>Чат открыт / Переписка</b> — можно писать в чате Mini App.",
        "<b>Отклонено</b> — адресат нажал «Не интересно».",
    ], st))

    story.append(Paragraph("6. Чат, перевод и Telegram-контакт", st["h1"]))
    story.append(
        Paragraph(
            "После открытия знакомства доступен чат. Сообщения можно смотреть в оригинале "
            "или в переводе (переключатель «Перевод / Оригинал»). "
            "Когда чат открыт, появляется возможность перейти к собеседнику в Telegram.",
            st["body"],
        )
    )
    story.extend(shot("12_chat", "Рис. 9. Экран чата"))
    story.append(
        Paragraph(
            "Если собеседник нарушает правила, на карточке письма есть кнопка "
            "<b>«Пожаловаться»</b> — заявка уходит модератору.",
            st["note"],
        )
    )

    story.append(Paragraph("7. Кредиты сообщений", st["h1"]))
    story.append(
        Paragraph(
            "1 кредит = одно открытие знакомства (когда вам ответили и вы хотите продолжить переписку). "
            "Пакет кредитов не сгорает. Покупка оформляется через Telegram Stars: бот присылает счёт в чат.",
            st["body"],
        )
    )
    story.append(bullets([
        "На главной баланс виден на плитке «Кредиты сообщений».",
        "В разделе кредитов можно купить 1 кредит или пакет (размер и цена задаются конфигурацией).",
        "После оплаты баланс обновится автоматически.",
    ], st))
    story.extend(shot("14_credits_balance", "Рис. 10. Экран кредитов сообщений"))

    story.append(Paragraph("8. Реферальная программа", st["h1"]))
    story.append(
        Paragraph(
            "Раздел «Расширь свой круг» даёт личную ссылку. Когда друг открывает бота по вашей ссылке, "
            "он засчитывается как приглашённый, вам приходит уведомление, а на баланс начисляется "
            "бонусный кредит (размер бонуса настраивается, по умолчанию +1).",
            st["body"],
        )
    )
    story.extend(shot("06_referral", "Рис. 11. Реферальная ссылка и счётчик приглашённых"))

    story.append(Paragraph("9. Реклама в канале", st["h1"]))
    story.append(
        Paragraph(
            "Любой пользователь может подать заявку на рекламный слот в канале: "
            "название, категория, текст/креатив, контакт и желаемая дата. "
            "Слот рассчитан на 48 часов, публикация в 10:00 МСК. Оплата — после одобрения заявки.",
            st["body"],
        )
    )
    story.extend(shot("07_ads_form", "Рис. 12. Форма заявки на рекламу в канале"))
    story.append(bullets([
        "После отправки заявка получает статус «На модерации».",
        "После одобрения бот пришлёт счёт в Stars.",
        "После оплаты слот встаёт в очередь на ближайшее свободное окно 10:00 МСК.",
        "В разделе можно смотреть свои заявки и их статусы.",
    ], st))

    story.append(Paragraph("10. Ограничения и поддержка", st["h1"]))
    story.append(bullets([
        "Сервис только для взрослых (18+).",
        "Есть лимиты на исходящие письма (в час / в день / число ожидающих ответа). "
        "При превышении включается временное ограничение — доступ восстановится автоматически.",
        "Заблокированный пользователь не сможет пользоваться API/приложением.",
        "По вопросам модерации и ошибок пишите в поддержку через бота.",
    ], st))
    story.append(PageBreak())

    # -------- ADMIN PART --------
    story.append(section_banner("Часть 2. Как пользоваться админкой"))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("11. Админка: вход и структура", st["h1"]))
    story.append(
        Paragraph(
            "Доступ только у Telegram ID из списка администраторов. "
            "В чате с ботом отправьте команду <b>/admin</b> — бот пришлёт кнопку "
            "«Открыть админку». Также можно открыть Mini App с параметром <b>startapp=admin</b>. "
            "Обычным пользователям раздел недоступен (редирект на главную).",
            st["body"],
        )
    )
    story.append(
        Paragraph(
            "Вкладки админки: <b>Новые</b>, <b>Очередь</b>, <b>Опубликованы</b>, "
            "<b>Реклама</b>, <b>Жалобы</b>, <b>Пользователи</b>, <b>Платежи</b>, <b>Статистика</b>.",
            st["body"],
        )
    )
    story.extend(shot("20_admin_new", "Рис. 13. Админка — вкладка «Новые» (очередь на модерацию)"))

    story.append(Paragraph("12. Модерация анкет", st["h1"]))
    story.append(
        Paragraph(
            "На вкладке «Новые» лежат анкеты со статусом «на модерации». "
            "Откройте карточку: фото, видео-приветствие (если есть), тексты, город, семейное положение, "
            "ответ для заставки, все загруженные фото.",
            st["body"],
        )
    )
    story.extend(shot("21_admin_profile_detail", "Рис. 14. Карточка анкеты на модерации"))
    story.extend(shot("21b_admin_profile_actions", "Рис. 15. Действия: одобрить или отклонить с причиной"))

    story.append(Paragraph("Действия модератора", st["h3"]))
    story.append(bullets([
        "<b>Одобрить → оплата</b> — анкета одобрена, пользователю уходит счёт на публикацию в Stars.",
        "<b>Отклонить</b> — обязательно укажите причину (минимум несколько символов). "
        "Пользователь увидит комментарий и сможет исправить анкету.",
        "Проверяйте качество фото, адекватность текстов, 18+, отсутствие контактов и спама.",
    ], st))

    story.append(Paragraph("13. Очередь и публикация", st["h1"]))
    story.append(
        Paragraph(
            "После оплаты анкета попадает во вкладку <b>«Очередь»</b>. "
            "Администратор назначает дату/время публикации (МСК) или публикует сразу.",
            st["body"],
        )
    )
    story.extend(shot("24_admin_queue", "Рис. 16. Вкладка «Очередь»"))
    story.append(bullets([
        "<b>Назначить дату</b> — пользователь получает уведомление с датой выхода в канал.",
        "<b>Опубликовать сейчас</b> — в канал уходят заставка, фото, текст и кнопка «Написать».",
        "Если оплата прошла вне Stars (вручную), на карточке awaiting_payment есть "
        "«Отметить оплату вручную» — анкета перейдёт в очередь.",
    ], st))
    story.extend(shot("22_admin_published", "Рис. 17. Вкладка «Опубликованы»"))
    story.extend(shot("23_admin_published_detail", "Рис. 18. Карточка уже опубликованной анкеты"))

    story.append(Paragraph("14. Реклама, жалобы, пользователи, платежи, статистика", st["h1"]))

    story.append(Paragraph("Реклама", st["h2"]))
    story.append(
        Paragraph(
            "Фильтры: «Новые», «Очередь/активные», «Все». "
            "Для заявки на модерации: одобрить (счёт рекламодателю) или отклонить с причиной. "
            "После оплаты — очередь на слот 10:00 МСК; можно «Активировать сейчас». "
            "Активный пост снимается автоматически через 48 часов.",
            st["body"],
        )
    )
    story.extend(shot("26_admin_ads_all", "Рис. 19. Список рекламных заявок"))
    story.extend(shot("27_admin_ad_detail", "Рис. 20. Карточка рекламной заявки"))

    story.append(Paragraph("Жалобы", st["h2"]))
    story.append(
        Paragraph(
            "Вкладка «Жалобы» показывает обращения пользователей. "
            "Разберите кейс, при необходимости заблокируйте нарушителя во вкладке пользователей "
            "и отметьте жалобу как решённую / отклонённую.",
            st["body"],
        )
    )
    story.extend(shot("28_admin_complaints", "Рис. 21. Жалобы"))

    story.append(Paragraph("Пользователи", st["h2"]))
    story.append(
        Paragraph(
            "Поиск по имени, @username или Telegram ID. "
            "Можно начислить кредиты вручную, заблокировать или разблокировать пользователя. "
            "Те же действия доступны из карточки анкеты.",
            st["body"],
        )
    )
    story.extend(shot("29_admin_users", "Рис. 22. Пользователи"))

    story.append(Paragraph("Платежи", st["h2"]))
    story.append(
        Paragraph(
            "Журнал платежей: публикация анкеты, кредит, пакет писем, рекламный слот. "
            "Статусы: ждёт оплаты / оплачен / ошибка / возврат. "
            "Используйте вкладку для сверки Stars и ручных отметок оплаты.",
            st["body"],
        )
    )
    story.extend(shot("30_admin_payments", "Рис. 23. Платежи"))

    story.append(Paragraph("Статистика", st["h2"]))
    story.append(
        Paragraph(
            "Сводка по продукту: анкеты на модерации/в очереди/опубликованные, "
            "звёзды, оплаты по типам, письма, реклама, открытые жалобы, блокировки.",
            st["body"],
        )
    )
    story.extend(shot("31_admin_stats", "Рис. 24. Статистика"))

    story.append(Paragraph("15. Типовые сценарии администратора", st["h1"]))
    story.append(Paragraph("Сценарий A. Новая анкета → канал", st["h3"]))
    story.append(bullets([
        "Открыть «Новые» → проверить тексты и фото.",
        "Одобрить → пользователь платит Stars.",
        "В «Очереди» назначить дату или опубликовать сейчас.",
        "Проверить пост в канале и уведомление пользователю.",
    ], st))
    story.append(Paragraph("Сценарий B. Анкета с нарушением", st["h3"]))
    story.append(bullets([
        "Отклонить с понятной причиной (что исправить).",
        "Дождаться новой версии во вкладке «Новые».",
    ], st))
    story.append(Paragraph("Сценарий C. Реклама", st["h3"]))
    story.append(bullets([
        "Проверить креатив и контакт.",
        "Одобрить → дождаться оплаты → убедиться, что слот встал на 10:00 МСК, "
        "либо активировать вручную.",
    ], st))
    story.append(Paragraph("Сценарий D. Жалоба / абьюз", st["h3"]))
    story.append(bullets([
        "Открыть жалобу, проверить переписку/анкету.",
        "При необходимости заблокировать пользователя и начислить/не начислять кредиты.",
        "Закрыть жалобу в статусе «решена» или «отклонена».",
    ], st))

    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            "Конец документа. При обновлении интерфейса Mini App рекомендуется "
            "переснять ключевые экраны и обновить этот PDF.",
            st["note"],
        )
    )

    doc.build(story, onFirstPage=add_page_decorations, onLaterPages=add_page_decorations)
    return OUT


if __name__ == "__main__":
    path = build()
    print(path)
    print(f"size={path.stat().st_size}")
