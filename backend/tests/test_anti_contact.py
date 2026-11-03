"""Anti-contact filter for profile texts and letters."""

from app.services.anti_contact import contains_contact_info


def test_instagram_photo_case_blocked() -> None:
    text = (
        "Ищу настоящего мужчину ,для создания семьи.просто так просьба не беспокоить."
        "inst : Alena_alena_55555"
    )
    assert contains_contact_info(text)


def test_instagram_label_variants_blocked() -> None:
    samples = [
        "inst: Alena_alena_55555",
        "inst：Alena_alena_55555",  # fullwidth colon
        "INST = alena.alena",
        "ig/alena_555",
        "ig @alena555",
        "instagram: alena_555",
        "инст: alena_555",
        "инста.alena555",
        "Мой инст alena555",
        "пиши в инст alena_petrova",
        "i n s t a : alena555",
        "Find me on instagram alena_99",
    ]
    for sample in samples:
        assert contains_contact_info(sample), sample


def test_other_messengers_with_separator_blocked() -> None:
    samples = [
        "тг: ivan_ivanov",
        "tg=ivan99",
        "wa: +79991234567",
        "telegram: @ivan_ivanov",
        "whatsapp: 79991234567",
        "tiktok: dance_girl99",
    ]
    for sample in samples:
        assert contains_contact_info(sample), sample


def test_plain_handles_and_links_blocked() -> None:
    samples = [
        "@alena_bolshaya",
        "https://instagram.com/alena",
        "www.t.me/alena",
        "alena_alena_55555",
        "пиши мне +7 999 123-45-67",
    ]
    for sample in samples:
        assert contains_contact_info(sample), sample


def test_normal_bio_allowed() -> None:
    samples = [
        "Ищу настоящего мужчину для создания семьи. Просто так просьба не беспокоить.",
        "Amo il mare, la cucina e i viaggi in Italia.",
        "Работаю в большой компании, люблю спорт и кино.",
        "Instinto e curiosità nella vita quotidiana.",  # not Instagram
        "Biggest dream is a family.",  # contains "ig" inside words only
    ]
    for sample in samples:
        assert not contains_contact_info(sample), sample
