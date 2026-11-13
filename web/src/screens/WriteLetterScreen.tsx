import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { type Language, t, tf } from "../i18n/messages";
import {
  createLetter,
  fetchWriteTarget,
  mediaUrl,
  type MeUser,
  type WriteTarget,
} from "../lib/api";
import { giftBannerKey } from "../lib/writePath";

type Props = {
  language: Language;
  me: MeUser | null;
  onCreditsChange?: () => void;
};

function GiftIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3.5" y="8.5" width="17" height="4" rx="1" />
      <path d="M5 12.5V20h14v-7.5M12 8.5V20" />
      <path d="M12 8.5C10.5 8.5 8 8 8 6a2 2 0 0 1 4 0c0 1 0 2.5 0 2.5Zm0 0c1.5 0 4-.5 4-2.5a2 2 0 0 0-4 0" />
    </svg>
  );
}

/** Standard camera glyph for empty photo circle (TZ mock). */
function CameraIcon() {
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3.5 9.2h3.1l1.4-2.2h7.9l1.4 2.2h3.2c.8 0 1.5.7 1.5 1.5v8.3c0 .8-.7 1.5-1.5 1.5H3.5c-.8 0-1.5-.7-1.5-1.5v-8.3c0-.8.7-1.5 1.5-1.5Z" />
      <circle cx="12" cy="14" r="3.6" />
    </svg>
  );
}

export function WriteLetterScreen({ language, me, onCreditsChange }: Props) {
  const { profileId } = useParams();
  const navigate = useNavigate();
  const id = Number(profileId);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [target, setTarget] = useState<WriteTarget | null>(null);
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [adult, setAdult] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    void fetchWriteTarget(id).then(setTarget);
  }, [id]);

  const sender = target?.sender ?? null;

  // Repeat senders: the «about me» row comes prefilled (backend keeps the saved identity).
  useEffect(() => {
    if (!sender) return;
    setName((prev) => prev || sender.name);
    setAge((prev) => prev || String(sender.age));
  }, [sender]);

  useEffect(() => {
    if (!photo) {
      setPhotoPreview(null);
      return;
    }
    const url = URL.createObjectURL(photo);
    setPhotoPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  const savedPhoto = sender?.photo_url ? mediaUrl(sender.photo_url) : null;
  const circlePhoto = photoPreview ?? savedPhoto;
  const hasPhoto = Boolean(photo) || Boolean(sender?.photo_url);
  const giftLeft = me?.gift_credits_left ?? 0;

  const confirmAgeMismatch = (message: string) =>
    new Promise<boolean>((resolve) => {
      const tg = window.Telegram?.WebApp;
      try {
        if (tg?.showPopup) {
          tg.showPopup(
            {
              message,
              buttons: [
                { id: "write", type: "default", text: t(language, "writeAnyway") },
                { id: "cancel", type: "default", text: t(language, "writeCancel") },
              ],
            },
            (btn) => resolve(btn === "write"),
          );
          return;
        }
      } catch {
        /* popups unsupported in this client version */
      }
      resolve(window.confirm(message));
    });

  const onPickPhoto = (file: File | null) => {
    setPhoto(file);
    // A stale «no person / group photo» error must not outlive the photo it was about.
    setError(null);
  };

  const onSubmit = async () => {
    setError(null);
    const ageNum = Number(age);
    if (!sender) {
      if (!name.trim()) {
        setError(t(language, "writeNameInvalid"));
        return;
      }
      if (!Number.isFinite(ageNum) || ageNum < 18 || ageNum > 99) {
        setError(t(language, "writeAgeInvalid"));
        return;
      }
    }
    if (!hasPhoto) {
      setError(t(language, "writePhotoRequired"));
      return;
    }
    if (!adult) {
      setError(t(language, "writeAdultRequired"));
      return;
    }
    if (!text.trim()) {
      setError(t(language, "fieldRequired"));
      return;
    }
    if (target) {
      const senderAge = sender ? sender.age : ageNum;
      if (senderAge < target.age_min || senderAge > target.age_max) {
        const message = tf(language, "writeAgeRangeWarn", { min: target.age_min, max: target.age_max });
        if (!(await confirmAgeMismatch(message))) return;
      }
    }
    setBusy(true);
    try {
      const created = await createLetter({
        profileId: id,
        text: text.trim(),
        senderName: sender ? undefined : name.trim(),
        senderAge: sender ? undefined : ageNum,
        photo,
        // The helper line under the photo is the confirmation: «only you, face visible».
        photoIsMine: true,
      });
      onCreditsChange?.();
      // requestWriteAccess is asked on the waiting screen, not here.
      navigate(`/inbox/${created.id}/sent`, { replace: true });
    } catch (e) {
      const raw = e instanceof Error ? e.message : "";
      let code = "";
      try {
        const parsed = JSON.parse(raw) as { detail?: { code?: string } | string };
        if (parsed?.detail && typeof parsed.detail === "object") {
          code = parsed.detail.code ?? "";
        }
      } catch {
        /* plain text / substring fallback */
      }
      if (!code) {
        const known = [
          "duplicate",
          "contact_forbidden",
          "soft_banned",
          "pending_limit",
          "rate_hour",
          "rate_day",
          "photo_required",
          "photo_not_confirmed",
          "no_person",
          "group_photo",
          "name_invalid",
          "age_invalid",
        ];
        code = known.find((k) => raw.includes(k)) ?? "";
        if (!code && (raw.includes("no_credits") || raw.includes("402"))) code = "no_credits";
      }

      const textByCode: Record<string, string> = {
        duplicate: t(language, "letterDuplicate"),
        contact_forbidden: t(language, "contactForbidden"),
        soft_banned: t(language, "letterSoftBanned"),
        pending_limit: t(language, "letterPendingLimit"),
        rate_hour: t(language, "letterRateHour"),
        rate_day: t(language, "letterRateDay"),
        photo_required: t(language, "writePhotoRequired"),
        photo_not_confirmed: t(language, "writeOnlyYou"),
        no_person: t(language, "writeOnlyYou"),
        group_photo: t(language, "writeOnlyYou"),
        name_invalid: t(language, "writeNameInvalid"),
        age_invalid: t(language, "writeAgeInvalid"),
        no_credits: t(language, "writeNeedCredit"),
      };
      const message = textByCode[code] ?? t(language, "errorGeneric");
      setError(message);
      const tg = window.Telegram?.WebApp;
      if (tg?.showAlert) tg.showAlert(message);
      else window.alert(message);
    } finally {
      setBusy(false);
    }
  };

  if (!target) {
    return (
      <section className="screen screen--milky">
        <Link to="/" className="work-back work-back--gold">
          ← {t(language, "backHome")}
        </Link>
        <p className="home-meta">{t(language, "saving")}</p>
      </section>
    );
  }

  return (
    <section className="screen screen--milky write-screen">
      <Link to="/" className="work-back work-back--gold">
        ← {t(language, "backHome")}
      </Link>

      <div className="write-recipient">
        <div className="write-recipient__photo">
          {target.photo_url ? <img src={mediaUrl(target.photo_url)} alt="" /> : null}
        </div>
        <div className="write-recipient__info">
          <p className="write-recipient__eyebrow">{t(language, "writeMessageFor")}</p>
          <h1 className="write-recipient__name">
            {target.name}, {target.age}
          </h1>
          <p className="write-recipient__meta">{target.city}</p>
          <p className="write-recipient__meta">
            {tf(language, "seekingAges", { min: target.age_min, max: target.age_max })}
          </p>
          {target.verified ? (
            <span className="pill pill--green">{t(language, "profileVerifiedPill")}</span>
          ) : null}
        </div>
      </div>

      {giftLeft > 0 ? (
        <div className="gift-banner">
          <span className="gift-banner__icon">
            <GiftIcon />
          </span>
          <span className="gift-banner__text">
            <strong>{tf(language, giftBannerKey(language, giftLeft), { n: giftLeft })}</strong>
            <span>{tf(language, "giftBannerSub", { name: target.name })}</span>
          </span>
        </div>
      ) : null}

      <div className="write-about">
        <button
          type="button"
          className={`photo-picker${circlePhoto ? " has-photo" : ""}`}
          aria-label={t(language, "writePickPhoto")}
          onClick={() => fileRef.current?.click()}
        >
          <span className="photo-picker__face">
            {circlePhoto ? (
              <img src={circlePhoto} alt="" draggable={false} />
            ) : (
              <span className="photo-picker__icon">
                <CameraIcon />
              </span>
            )}
          </span>
          <span className="photo-picker__plus" aria-hidden>
            +
          </span>
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => {
            onPickPhoto(e.target.files?.[0] ?? null);
            e.target.value = "";
          }}
        />
        <div className="write-about__fields">
          <div className="write-field">
            <label htmlFor="write-name">{t(language, "writeYourName")}</label>
            <input
              id="write-name"
              value={name}
              maxLength={20}
              readOnly={Boolean(sender)}
              onChange={(e) => {
                setName(e.target.value);
                setError(null);
              }}
            />
          </div>
          <div className="write-field write-field--age">
            <label htmlFor="write-age">{t(language, "writeYourAge")}</label>
            <input
              id="write-age"
              inputMode="numeric"
              value={age}
              readOnly={Boolean(sender)}
              onChange={(e) => {
                setAge(e.target.value.replace(/\D/g, "").slice(0, 2));
                setError(null);
              }}
            />
          </div>
        </div>
      </div>
      <p className="write-photo-note">{t(language, "writePhotoNote")}</p>

      <label className="write-adult">
        <input type="checkbox" checked={adult} onChange={(e) => setAdult(e.target.checked)} />
        <span>{t(language, "writeAdult")}</span>
      </label>

      <label className="write-label" htmlFor="write-text">
        {t(language, "writeMessageLabel")}
      </label>
      <div className="field">
        <textarea
          id="write-text"
          rows={5}
          value={text}
          maxLength={1200}
          placeholder={tf(language, "writeMessagePlaceholder", { name: target.name })}
          onChange={(e) => setText(e.target.value)}
        />
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      <button
        type="button"
        className="btn btn--block btn--dark btn--pill"
        disabled={busy}
        onClick={() => void onSubmit()}
      >
        {busy ? t(language, "saving") : t(language, "writeSendMessage")}
      </button>
      {!hasPhoto ? <p className="write-photo-hint">{t(language, "writeAddPhotoHint")}</p> : null}
    </section>
  );
}
