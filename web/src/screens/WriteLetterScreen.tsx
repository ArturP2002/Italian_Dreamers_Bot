import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { type Language, t, tf } from "../i18n/messages";
import {
  createLetter,
  fetchWriteTarget,
  mediaUrl,
  type WriteTarget,
} from "../lib/api";

type Props = { language: Language };

export function WriteLetterScreen({ language }: Props) {
  const { profileId } = useParams();
  const navigate = useNavigate();
  const id = Number(profileId);
  const [target, setTarget] = useState<WriteTarget | null>(null);
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [photoPreview, setPhotoPreview] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    void fetchWriteTarget(id).then(setTarget);
  }, [id]);

  useEffect(() => {
    if (!photo) {
      setPhotoPreview(null);
      return;
    }
    const url = URL.createObjectURL(photo);
    setPhotoPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  const sender = target?.sender ?? null;
  const senderPhoto = photoPreview ?? (sender?.photo_url ? mediaUrl(sender.photo_url) : null);

  const onSubmit = async () => {
    setError(null);
    const ageNum = Number(age);
    if (!sender) {
      if (!name.trim()) {
        setError(t(language, "fieldRequired"));
        return;
      }
      if (!Number.isFinite(ageNum) || ageNum < 18) {
        setError(t(language, "writeAgeWarn"));
        return;
      }
    }
    if (text.trim().length < 10) {
      setError(t(language, "fieldRequired"));
      return;
    }
    setBusy(true);
    try {
      const created = await createLetter({
        profileId: id,
        text: text.trim(),
        senderName: sender ? undefined : name.trim(),
        senderAge: sender ? undefined : ageNum,
        photo,
      });
      navigate(`/inbox/${created.id}`, { replace: true });
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
        if (raw.includes("duplicate")) code = "duplicate";
        else if (raw.includes("contact_forbidden")) code = "contact_forbidden";
        else if (raw.includes("soft_banned")) code = "soft_banned";
        else if (raw.includes("pending_limit")) code = "pending_limit";
      }

      const textByCode: Record<string, string> = {
        duplicate: t(language, "letterDuplicate"),
        contact_forbidden: t(language, "contactForbidden"),
        soft_banned: t(language, "letterSoftBanned"),
        pending_limit: t(language, "letterPendingLimit"),
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
        <Link to="/" className="work-back">
          ← {t(language, "backHome")}
        </Link>
        <p className="home-meta">{t(language, "saving")}</p>
      </section>
    );
  }

  return (
    <section className="screen screen--milky">
      <Link to="/" className="work-back">
        ← {t(language, "backHome")}
      </Link>
      <h1 className="work-title">{t(language, "writeTitle")}</h1>
      <p className="work-body">{tf(language, "letterTo", { name: target.name })}</p>
      <p className="home-meta">{t(language, "writeHint")}</p>

      <div className="write-target">
        {target.photo_url ? (
          <img src={mediaUrl(target.photo_url)} alt="" className="write-target__photo" />
        ) : null}
        <div>
          <strong>
            {target.name}, {target.age}
          </strong>
          <p>{target.city}</p>
        </div>
      </div>

      {sender ? (
        <>
          <label className="wizard-hint">{t(language, "writeFrom")}</label>
          <div className="write-target write-target--sender">
            {senderPhoto ? <img src={senderPhoto} alt="" className="write-target__photo" /> : null}
            <div>
              <strong>
                {sender.name}, {sender.age}
              </strong>
              {sender.city ? <p>{sender.city}</p> : null}
              <p className="write-target__note">
                {t(language, sender.source === "profile" ? "writeFromProfile" : "writeFromSaved")}
              </p>
            </div>
          </div>
        </>
      ) : (
        <>
          <label className="wizard-hint">{t(language, "writeName")}</label>
          <div className="field">
            <input value={name} maxLength={20} onChange={(e) => setName(e.target.value)} />
          </div>

          <label className="wizard-hint">{t(language, "writeAge")}</label>
          <div className="field">
            <input
              type="number"
              min={18}
              max={99}
              value={age}
              onChange={(e) => setAge(e.target.value)}
            />
          </div>
        </>
      )}

      <label className="wizard-hint">{t(language, "writePhoto")}</label>
      {sender?.photo_url ? <p className="write-target__note">{t(language, "writePhotoOptional")}</p> : null}
      <div className="field">
        <input
          type="file"
          accept="image/*"
          onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
        />
      </div>

      <label className="wizard-hint">{t(language, "writeText")}</label>
      <div className="field">
        <textarea
          rows={6}
          value={text}
          maxLength={1200}
          onChange={(e) => setText(e.target.value)}
        />
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      <button
        type="button"
        className="btn btn--block btn--dark"
        disabled={busy}
        onClick={() => void onSubmit()}
      >
        {busy ? t(language, "saving") : t(language, "writeSend")}
      </button>
    </section>
  );
}
