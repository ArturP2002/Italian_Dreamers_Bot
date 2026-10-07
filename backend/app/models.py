"""ORM models: legacy entities + Phase 0 monetization / moderation extensions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LanguageCode(StrEnum):
    RU = "ru"
    IT = "it"


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class WantsChildren(StrEnum):
    YES = "yes"
    NO = "no"
    UNSURE = "unsure"


class MaritalStatus(StrEnum):
    SINGLE = "single"
    DIVORCED = "divorced"


class PublicationOption(StrEnum):
    STANDARD = "standard"
    PRIORITY = "priority"


class ProfileStatus(StrEnum):
    DRAFT = "draft"
    NEW = "new"  # submitted for moderation
    APPROVED = "approved"
    AWAITING_PAYMENT = "awaiting_payment"
    QUEUED = "queued"  # paid, waiting for scheduled_at
    PUBLISHED = "published"
    HIDDEN = "hidden"  # rejected / taken down
    REJECTED = "rejected"


class MessageRequestStatus(StrEnum):
    PENDING = "pending"
    REPLIED = "replied"
    UNLOCKED = "unlocked"
    CHATTING = "chatting"
    REJECTED = "rejected"
    # legacy alias kept for compatibility
    ACCEPTED = "accepted"


class PaymentProduct(StrEnum):
    MESSAGE_CREDIT = "message_credit"
    MESSAGE_PACK_9 = "message_pack_9"
    PROFILE_PUBLISH = "profile_publish"
    AD_SLOT = "ad_slot"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class LedgerEntryType(StrEnum):
    PURCHASE = "purchase"
    SPEND = "spend"
    ADMIN_GRANT = "admin_grant"
    REFUND = "refund"
    REFERRAL = "referral"


class AdRequestStatus(StrEnum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    AWAITING_PAYMENT = "awaiting_payment"
    QUEUED = "queued"
    ACTIVE = "active"
    EXPIRED = "expired"
    REJECTED = "rejected"


class ComplaintStatus(StrEnum):
    OPEN = "open"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str] = mapped_column(String(2), nullable=False, default=LanguageCode.RU.value)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    stated_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stated_name: Mapped[str | None] = mapped_column(String(20), nullable=True)
    stated_photo_file_id: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    stated_photo_file_unique_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    message_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    soft_ban_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    referral_code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    referred_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    profile: Mapped[Profile | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    payments: Mapped[list[Payment]] = relationship(back_populates="user")
    ledger_entries: Mapped[list[CreditLedgerEntry]] = relationship(back_populates="user")
    complaints_filed: Mapped[list[Complaint]] = relationship(
        back_populates="reporter",
        foreign_keys="Complaint.reporter_user_id",
    )


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    age: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    age_min: Mapped[int] = mapped_column(Integer, nullable=False, default=18)
    age_max: Mapped[int] = mapped_column(Integer, nullable=False, default=99)
    height_cm: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_children: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    wants_children: Mapped[str] = mapped_column(String(16), nullable=False, default=WantsChildren.UNSURE.value)
    marital_status: Mapped[str] = mapped_column(String(32), nullable=False, default=MaritalStatus.SINGLE.value)
    country: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    city: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    profession: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    hobbies: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    about: Mapped[str] = mapped_column(Text, nullable=False, default="")
    desired_partner: Mapped[str] = mapped_column(Text, nullable=False, default="")
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    personal_data_agreement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    publication_option: Mapped[str] = mapped_column(
        String(32),
        default=PublicationOption.STANDARD.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), default=ProfileStatus.DRAFT.value, nullable=False)

    # Channel splash (Unical_Post): 1 of 9 questions + answer ≤70
    cover_question_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover_answer: Mapped[str | None] = mapped_column(String(70), nullable=True)
    # «Мечтаю увидеть» location key for cover art
    dream_location: Mapped[str | None] = mapped_column(String(64), nullable=True)

    moderation_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    channel_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    splash_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    name_translated: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city_translated: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country_translated: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profession_translated: Mapped[str | None] = mapped_column(Text, nullable=True)
    about_translated: Mapped[str | None] = mapped_column(Text, nullable=True)
    desired_partner_translated: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_answer_translated: Mapped[str | None] = mapped_column(String(70), nullable=True)
    translated_language: Mapped[str | None] = mapped_column(String(2), nullable=True)
    translated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="profile")
    photos: Mapped[list[ProfilePhoto]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProfilePhoto.position",
    )
    message_requests: Mapped[list[MessageRequest]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ProfilePhoto(Base):
    __tablename__ = "profile_photos"
    __table_args__ = (UniqueConstraint("profile_id", "position", name="uq_profile_photos_profile_position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    file_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_unique_id: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    profile: Mapped[Profile] = relationship(back_populates="photos")


class MessageRequest(Base):
    __tablename__ = "message_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_translated: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_text_translated: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sender_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sender_photo_file_id: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default=MessageRequestStatus.PENDING.value, nullable=False, index=True
    )
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Plain int to avoid circular FK with payments.related_message_request_id
    charged_payment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="message_requests")
    sender: Mapped[User] = relationship(foreign_keys=[sender_user_id])
    chat_messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="message_request",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_request_id: Mapped[int] = mapped_column(
        ForeignKey("message_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_translated: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    message_request: Mapped[MessageRequest] = relationship(back_populates="chat_messages")
    sender: Mapped[User] = relationship()


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=PaymentStatus.PENDING.value, nullable=False, index=True)
    stars_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    telegram_payment_charge_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    telegram_payload: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    related_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    related_message_request_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    related_ad_request_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="payments")


class CreditLedgerEntry(Base):
    __tablename__ = "credit_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)
    message_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("message_requests.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="ledger_entries")


class AdRequest(Base):
    __tablename__ = "ad_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default=AdRequestStatus.PENDING.value, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    desired_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    media_file_id: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    moderation_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reminded_7d_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminded_30d_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship()


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporter_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reported_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    message_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("message_requests.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=ComplaintStatus.OPEN.value, nullable=False, index=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reporter: Mapped[User] = relationship(
        back_populates="complaints_filed",
        foreign_keys=[reporter_user_id],
    )
