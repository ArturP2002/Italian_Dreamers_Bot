"""Profile draft / submit helpers for Mini App."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Profile, ProfileStatus, User
from app.services.anti_contact import contains_contact_info

# Published in the channel, so contacts here would bypass the paid chat.
CONTACT_CHECKED_FIELDS = (
    "name",
    "country",
    "city",
    "profession",
    "hobbies",
    "about",
    "desired_partner",
    "cover_answer",
)


def fields_with_contacts(values: dict) -> list[str]:
    return [
        key
        for key in CONTACT_CHECKED_FIELDS
        if isinstance(values.get(key), str) and contains_contact_info(values[key])
    ]


EDITABLE_STATUSES = frozenset(
    {
        ProfileStatus.DRAFT.value,
        ProfileStatus.REJECTED.value,
    }
)

SUBMITTABLE_STATUSES = EDITABLE_STATUSES


async def get_user_profile(session: AsyncSession, user_id: int) -> Profile | None:
    result = await session.execute(
        select(Profile)
        .where(Profile.user_id == user_id)
        .options(selectinload(Profile.photos))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def get_or_create_draft(session: AsyncSession, user: User) -> Profile:
    profile = await get_user_profile(session, user.id)
    if profile is None:
        profile = Profile(
            user_id=user.id,
            gender=user.gender,
            telegram_username=user.telegram_username,
            status=ProfileStatus.DRAFT.value,
        )
        session.add(profile)
        await session.commit()
        return await get_user_profile(session, user.id)  # type: ignore[return-value]
    return profile


async def seed_mini_anketa_from_letter(
    session: AsyncSession,
    *,
    user: User,
    name: str,
    age: int,
    photo_file_id: str | None,
    adult_confirmed: bool = True,
) -> Profile:
    """First «Написать» becomes the draft Profile (photo + name + age + 18+).

    Does not commit — caller owns the transaction.
    """
    from app.models import ProfilePhoto

    profile = await get_user_profile(session, user.id)
    if profile is None:
        profile = Profile(
            user_id=user.id,
            gender=user.gender,
            telegram_username=user.telegram_username,
            status=ProfileStatus.DRAFT.value,
        )
        session.add(profile)
        await session.flush()
    if profile.status not in {ProfileStatus.DRAFT.value, ProfileStatus.REJECTED.value}:
        return profile
    cleaned = (name or "").strip()[:255]
    if cleaned:
        profile.name = cleaned
    if 18 <= age <= 99:
        profile.age = age
    if adult_confirmed:
        profile.personal_data_agreement = True
    photos = list(profile.photos or [])
    if photo_file_id and not photos:
        session.add(
            ProfilePhoto(
                profile_id=profile.id,
                file_id=photo_file_id,
                position=0,
            )
        )
    session.add(profile)
    return profile


def profile_completion_percent(profile: Profile | None) -> int:
    """Rough readiness for soft nudges (0–100)."""
    if profile is None:
        return 0
    checks = [
        bool((profile.name or "").strip()),
        bool(profile.age and profile.age >= 18),
        bool(profile.photos),
        bool(profile.personal_data_agreement),
        bool((profile.city or "").strip()),
        bool((profile.profession or "").strip()),
        bool((profile.about or "").strip()),
        bool((profile.desired_partner or "").strip()),
        bool(profile.height_cm and profile.height_cm >= 140),
        bool(profile.cover_question_id and (profile.cover_answer or "").strip()),
    ]
    done = sum(1 for c in checks if c)
    return int(round(100 * done / len(checks)))


def assert_editable(profile: Profile) -> None:
    if profile.status not in EDITABLE_STATUSES:
        raise ValueError(f"Profile status '{profile.status}' is not editable")


def validate_for_submit(profile: Profile) -> list[str]:
    errors: list[str] = []
    if not (profile.name or "").strip():
        errors.append("name")
    if not (18 <= profile.age <= 99):
        errors.append("age")
    if not (140 <= profile.height_cm <= 210):
        errors.append("height_cm")
    if not (profile.country or "").strip():
        errors.append("country")
    if not (profile.city or "").strip():
        errors.append("city")
    if not (profile.profession or "").strip():
        errors.append("profession")
    if not (profile.about or "").strip():
        errors.append("about")
    if not (profile.desired_partner or "").strip():
        errors.append("desired_partner")
    age_min = profile.age_min or 0
    age_max = profile.age_max or 0
    if age_min < 18 or age_max > 99 or age_min > age_max:
        errors.append("partner_age")
    if profile.cover_question_id is None or not (1 <= profile.cover_question_id <= 9):
        errors.append("cover_question_id")
    answer = (profile.cover_answer or "").strip()
    if not answer or len(answer) > 70:
        errors.append("cover_answer")
    if not profile.personal_data_agreement:
        errors.append("personal_data_agreement")
    if len(profile.photos or []) != 3:
        errors.append("photos")
    if not profile.gender:
        errors.append("gender")
    return errors
