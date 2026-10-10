import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { guideAssets, guidePhotos } from "../assets/backgrounds";
import { COVER_QUESTIONS, type Language, type MessageKey, tf, t } from "../i18n/messages";
import {
  deleteGreetingVideo,
  deleteProfilePhoto,
  fetchProfile,
  mediaUrl,
  patchGender,
  submitProfile,
  updateProfile,
  uploadGreetingVideo,
  uploadProfilePhoto,
  type MeUser,
  type Profile,
  type ProfileUpdatePayload,
} from "../lib/api";
import { ProfileIntroScreen } from "./ProfileIntroScreen";

const TOTAL_STEPS = 12;
// Gender gate and guide are numbered before the 12 questions in the progress counter.
const INTRO_SCREENS = 2;
const DISPLAY_TOTAL = TOTAL_STEPS + INTRO_SCREENS;
const VIDEO_STEP = 9;
const MAX_VIDEO_BYTES = 50 * 1024 * 1024;
const REQUIRED_PHOTOS = 3;

type Phase = "loading" | "intro" | "gate" | "guide" | "steps" | "done";

type Props = {
  language: Language;
  me: MeUser | null;
  onMeRefresh: () => Promise<void>;
};

/** First incomplete wizard step from saved draft (1–12). */
function resumeStepFromProfile(p: Profile): number {
  if (!p.name.trim()) return 1;
  if (!p.age || p.age < 18) return 2;
  if (!p.height_cm || p.height_cm < 140) return 3;
  if (!p.country.trim() || !p.city.trim()) return 4;
  if (!p.profession.trim()) return 5;
  // Step 6 has DB defaults; if about is empty, re-show family then bio.
  if (!p.about.trim()) return 6;
  if (!p.desired_partner.trim()) return 8;
  if (!p.cover_question_id || !p.cover_answer?.trim()) return p.greeting_video_url ? 10 : VIDEO_STEP;
  if ((p.photos?.length ?? 0) !== REQUIRED_PHOTOS) return 11;
  return 12;
}

function profileHasDraftProgress(p: Profile): boolean {
  return Boolean(
    p.name.trim() ||
      (p.age && p.age >= 18) ||
      (p.height_cm && p.height_cm >= 140) ||
      p.country.trim() ||
      p.city.trim() ||
      p.profession.trim() ||
      p.about.trim() ||
      p.desired_partner.trim() ||
      p.greeting_video_url ||
      p.cover_question_id ||
      p.cover_answer?.trim() ||
      (p.photos?.length ?? 0) > 0,
  );
}

function WizardChrome({
  language,
  step,
  onBack,
  children,
  footer,
}: {
  language: Language;
  step: number;
  onBack: () => void;
  children: ReactNode;
  footer: ReactNode;
}) {
  const pct = Math.round((step / DISPLAY_TOTAL) * 100);
  return (
    <section className="wizard screen">
      <div className="wizard__top">
        <button type="button" className="wizard__back" onClick={onBack} aria-label={t(language, "back")}>
          ‹
        </button>
        <div className="wizard__progress" aria-hidden>
          <div className="wizard__progress-bar" style={{ width: `${pct}%` }} />
        </div>
        <span className="wizard__step-num">
          {tf(language, "stepOf", { current: step, total: DISPLAY_TOTAL })}
        </span>
      </div>
      <div className="wizard__body">{children}</div>
      <div className="wizard__footer">{footer}</div>
    </section>
  );
}

export function ProfileWizard({ language, me, onMeRefresh }: Props) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [step, setStep] = useState(1);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [gender, setGender] = useState<"male" | "female" | null>(
    me?.gender === "male" || me?.gender === "female" ? me.gender : null,
  );
  const [ageOk, setAgeOk] = useState(Boolean(me?.gender));
  const [consent, setConsent] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const videoInputRef = useRef<HTMLInputElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [videoProgress, setVideoProgress] = useState<number | null>(null);

  useEffect(() => {
    void (async () => {
      const p = await fetchProfile();
      if (!p) {
        setPhase("intro");
        return;
      }
      setProfile(p);
      if (p.gender === "male" || p.gender === "female") setGender(p.gender);
      if (p.personal_data_agreement) {
        setConsent(true);
        setAgeOk(true);
      }
      if (
        p.status === "new" ||
        p.status === "approved" ||
        p.status === "awaiting_payment" ||
        p.status === "queued" ||
        p.status === "published"
      ) {
        setPhase("done");
      } else if (profileHasDraftProgress(p)) {
        setStep(resumeStepFromProfile(p));
        setPhase("steps");
      } else if (p.gender === "male" || p.gender === "female") {
        setAgeOk(true);
        setPhase("guide");
      } else {
        setPhase("intro");
      }
    })();
  }, []);

  const draft = useMemo(
    () => ({
      name: profile?.name ?? "",
      age: profile?.age && profile.age >= 18 ? String(profile.age) : "",
      height_cm: profile?.height_cm && profile.height_cm >= 140 ? String(profile.height_cm) : "",
      country: profile?.country ?? "",
      city: profile?.city ?? "",
      profession: profile?.profession ?? "",
      marital_status: (profile?.marital_status as "single" | "divorced") || "single",
      has_children: profile?.has_children ?? false,
      wants_children: (profile?.wants_children as "yes" | "no" | "unsure") || "unsure",
      about: profile?.about ?? "",
      hobbies: profile?.hobbies ?? "",
      desired_partner: profile?.desired_partner ?? "",
      age_min: profile?.age_min ? String(profile.age_min) : "18",
      age_max: profile?.age_max ? String(profile.age_max) : "99",
      cover_question_id: profile?.cover_question_id ?? null,
      cover_answer: profile?.cover_answer ?? "",
      telegram_username: profile?.telegram_username ?? me?.username ?? "",
    }),
    [profile, me],
  );

  const [form, setForm] = useState(draft);
  useEffect(() => {
    setForm(draft);
  }, [draft]);

  const save = async (payload: ProfileUpdatePayload) => {
    setBusy(true);
    setError(null);
    const updated = await updateProfile(payload);
    setBusy(false);
    if (!updated) {
      setError(t(language, "errorGeneric"));
      return false;
    }
    setProfile(updated);
    return true;
  };

  const goNext = () => setStep((s) => Math.min(TOTAL_STEPS, s + 1));
  const goBack = () => {
    if (step <= 1) {
      setPhase("guide");
      return;
    }
    setStep((s) => s - 1);
  };

  const validateAndAdvance = async () => {
    setError(null);
    switch (step) {
      case 1: {
        if (!form.name.trim()) return setError(t(language, "fieldRequired"));
        if (!(await save({ name: form.name.trim() }))) return;
        break;
      }
      case 2: {
        const age = Number(form.age);
        if (!Number.isFinite(age) || age < 18 || age > 99) {
          return setError(t(language, "ageSoftWarn"));
        }
        if (!(await save({ age }))) return;
        break;
      }
      case 3: {
        const height = Number(form.height_cm);
        if (!Number.isFinite(height) || height < 140 || height > 210) {
          return setError(t(language, "fieldRequired"));
        }
        if (!(await save({ height_cm: height }))) return;
        break;
      }
      case 4: {
        if (!form.country.trim() || !form.city.trim()) return setError(t(language, "fieldRequired"));
        if (!(await save({ country: form.country.trim(), city: form.city.trim() }))) return;
        break;
      }
      case 5: {
        if (!form.profession.trim()) return setError(t(language, "fieldRequired"));
        if (!(await save({ profession: form.profession.trim() }))) return;
        break;
      }
      case 6: {
        if (
          !(await save({
            marital_status: form.marital_status,
            has_children: form.has_children,
            wants_children: form.wants_children,
          }))
        )
          return;
        break;
      }
      case 7: {
        if (!form.about.trim()) return setError(t(language, "fieldRequired"));
        if (!(await save({ about: form.about.trim(), hobbies: form.hobbies.trim() }))) return;
        break;
      }
      case 8: {
        const ageMin = Number(form.age_min);
        const ageMax = Number(form.age_max);
        if (!form.desired_partner.trim()) return setError(t(language, "fieldRequired"));
        if (!Number.isFinite(ageMin) || !Number.isFinite(ageMax) || ageMin > ageMax) {
          return setError(t(language, "fieldRequired"));
        }
        if (
          !(await save({
            desired_partner: form.desired_partner.trim(),
            age_min: ageMin,
            age_max: ageMax,
          }))
        )
          return;
        break;
      }
      case VIDEO_STEP: {
        if (videoProgress !== null) return;
        break;
      }
      case 10: {
        const answer = form.cover_answer.trim();
        if (!form.cover_question_id || !answer || answer.length > 70) {
          return setError(t(language, "fieldRequired"));
        }
        if (!(await save({ cover_question_id: form.cover_question_id, cover_answer: answer })))
          return;
        break;
      }
      case 11: {
        if ((profile?.photos.length ?? 0) !== REQUIRED_PHOTOS) {
          return setError(t(language, "qPhotosHint"));
        }
        break;
      }
      case 12: {
        if (!consent) return setError(t(language, "fieldRequired"));
        const username = form.telegram_username.trim().replace(/^@/, "");
        if (!username) return setError(t(language, "fieldRequired"));
        if (
          !(await save({
            telegram_username: username,
            personal_data_agreement: true,
            gender: gender ?? undefined,
          }))
        )
          return;
        setBusy(true);
        const submitted = await submitProfile();
        setBusy(false);
        if (!submitted) {
          setError(t(language, "errorGeneric"));
          return;
        }
        setProfile(submitted);
        await onMeRefresh();
        setPhase("done");
        return;
      }
      default:
        break;
    }
    goNext();
  };

  const onUpload = async (files: File[]) => {
    if (!files.length) return;
    setBusy(true);
    setError(null);
    let latest = profile;
    for (const file of files.slice(0, REQUIRED_PHOTOS)) {
      if ((latest?.photos.length ?? 0) >= REQUIRED_PHOTOS) break;
      const updated = await uploadProfilePhoto(file);
      if (!updated) {
        setError(t(language, "errorGeneric"));
        break;
      }
      latest = updated;
      setProfile(updated);
    }
    // Refresh from server in case response was partial
    const refreshed = await fetchProfile();
    if (refreshed) setProfile(refreshed);
    setBusy(false);
  };

  const onVideoPicked = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    if (file.size > MAX_VIDEO_BYTES) {
      setError(t(language, "videoTooLarge"));
      return;
    }
    setVideoProgress(0);
    const result = await uploadGreetingVideo(file, setVideoProgress);
    setVideoProgress(null);
    if (result.ok) {
      setProfile(result.profile);
    } else {
      setError(t(language, result.reason === "too_large" ? "videoTooLarge" : "errorGeneric"));
    }
  };

  const onVideoRemove = async () => {
    setError(null);
    setBusy(true);
    const updated = await deleteGreetingVideo();
    setBusy(false);
    if (updated) setProfile(updated);
    else setError(t(language, "errorGeneric"));
  };

  const upcomingStep = profile ? resumeStepFromProfile(profile) : 1;

  if (phase === "loading") {
    return <section className="wizard screen" aria-busy="true" />;
  }

  if (phase === "intro") {
    return (
      <ProfileIntroScreen
        language={language}
        onStart={() => setPhase(gender && ageOk ? "guide" : "gate")}
      />
    );
  }

  if (phase === "gate") {
    return (
      <WizardChrome
        language={language}
        step={1}
        onBack={() => setPhase("intro")}
        footer={
          <button
            type="button"
            className="btn btn--dark btn--block"
            disabled={!gender || !ageOk || busy}
            onClick={async () => {
              if (!gender) return;
              setError(null);
              setBusy(true);
              const patched = await patchGender(gender);
              if (!patched) {
                setBusy(false);
                setError(t(language, "errorGeneric"));
                return;
              }
              const saved = await save({ gender });
              setBusy(false);
              if (!saved) return;
              await onMeRefresh();
              setError(null);
              setPhase("guide");
            }}
          >
            {t(language, "continue")}
          </button>
        }
      >
        <h2 className="wizard-title">{t(language, "genderTitle")}</h2>
        <div className="choice-row" style={{ marginBottom: 20 }}>
          <button
            type="button"
            className={`choice-pill${gender === "female" ? " is-active" : ""}`}
            onClick={() => setGender("female")}
          >
            {t(language, "genderFemale")}
          </button>
          <button
            type="button"
            className={`choice-pill${gender === "male" ? " is-active" : ""}`}
            onClick={() => setGender("male")}
          >
            {t(language, "genderMale")}
          </button>
        </div>
        <label className="checkbox-row">
          <input type="checkbox" checked={ageOk} onChange={(e) => setAgeOk(e.target.checked)} />
          <span>
            <strong>{t(language, "ageConsentTitle")}</strong>
            <br />
            {t(language, "ageConsentHint")}
          </span>
        </label>
        {error ? <p className="error-text">{error}</p> : null}
      </WizardChrome>
    );
  }

  if (phase === "guide") {
    const assets = guideAssets[language];
    return (
      <WizardChrome
        language={language}
        step={2}
        onBack={() => {
          setAudioPlaying(false);
          setPhase("gate");
        }}
        footer={
          <button
            type="button"
            className="btn btn--dark btn--block"
            onClick={() => {
              setAudioPlaying(false);
              setError(null);
              setStep(upcomingStep);
              setPhase("steps");
            }}
          >
            {t(language, "guideSkip")}
          </button>
        }
      >
        <h2 className="wizard-title">{t(language, "guideTitle")}</h2>
        <p className="wizard-hint">{t(language, "guideBody")}</p>
        <div className="guide-tiles">
          <button
            type="button"
            className={`guide-tile${audioPlaying ? " guide-tile--active" : ""}`}
            onClick={() => {
              const audio = audioRef.current;
              if (!audio) return;
              if (audio.paused) void audio.play();
              else audio.pause();
            }}
          >
            <img className="guide-tile__img guide-tile__img--listen" src={guidePhotos.listen} alt="" />
            <span className="guide-tile__badge" aria-hidden>
              {audioPlaying ? "❚❚" : "▶"}
            </span>
            <span className="guide-tile__label">{t(language, "guideListen")}</span>
          </button>
          <a className="guide-tile" href={assets.pdf} target="_blank" rel="noreferrer">
            <img className="guide-tile__img guide-tile__img--read" src={guidePhotos.read} alt="" />
            <span className="guide-tile__badge" aria-hidden>
              PDF
            </span>
            <span className="guide-tile__label">{t(language, "guideRead")}</span>
          </a>
        </div>
        <audio
          ref={audioRef}
          src={assets.audio}
          preload="none"
          onPlay={() => setAudioPlaying(true)}
          onPause={() => setAudioPlaying(false)}
          onEnded={() => setAudioPlaying(false)}
        />
      </WizardChrome>
    );
  }

  if (phase === "done") {
    const status = profile?.status;
    const [titleKey, bodyKey]: [MessageKey, MessageKey] =
      status === "published"
        ? ["donePublishedTitle", "donePublishedBody"]
        : status === "queued"
          ? ["doneQueuedTitle", "doneQueuedBody"]
          : status === "approved" || status === "awaiting_payment"
            ? ["doneApprovedTitle", "doneApprovedBody"]
            : ["submittedTitle", "submittedBody"];
    const postUrl = profile?.channel_post_url;
    const openPost = () => {
      if (!postUrl) return;
      const tg = window.Telegram?.WebApp;
      if (tg?.openTelegramLink) tg.openTelegramLink(postUrl);
      else window.open(postUrl, "_blank", "noopener");
    };
    const photos = profile?.photos ?? [];
    const cover = profile?.cover_question_id ? COVER_QUESTIONS[profile.cover_question_id] : null;
    const wantsKey: MessageKey =
      profile?.wants_children === "yes" ? "yes" : profile?.wants_children === "no" ? "no" : "unsure";
    return (
      <section className="screen screen--milky">
        <h1 className="wizard-title">{t(language, "myProfileTitle")}</h1>

        <div className="my-profile-status">
          <strong>{t(language, titleKey)}</strong>
          <p>{t(language, bodyKey)}</p>
          {postUrl ? (
            <button type="button" className="btn btn--dark btn--block" onClick={openPost}>
              {t(language, "myProfileOpenPost")}
            </button>
          ) : null}
        </div>

        {profile ? (
          <article className="my-profile-card">
            {photos[0] ? <img className="my-profile-card__hero" src={mediaUrl(photos[0].url)} alt="" /> : null}
            {photos.length > 1 ? (
              <div className="my-profile-card__thumbs">
                {photos.slice(1).map((p) => (
                  <img key={p.id} src={mediaUrl(p.url)} alt="" />
                ))}
              </div>
            ) : null}
            <div className="my-profile-card__body">
              <h2>
                {profile.name}, {profile.age} {t(language, "myProfileYears")}
              </h2>
              <p className="my-profile-card__meta">
                {profile.city}, {profile.country} · {profile.profession}
              </p>
              <p className="my-profile-card__meta">
                {profile.height_cm} {language === "it" ? "cm" : "см"} ·{" "}
                {t(language, profile.marital_status === "divorced" ? "maritalDivorced" : "maritalSingle")} ·{" "}
                {t(language, "myProfileChildren")}: {t(language, profile.has_children ? "yes" : "no")} ·{" "}
                {t(language, "myProfileWantsChildren")}: {t(language, wantsKey)}
              </p>
              {profile.greeting_video_url ? (
                <>
                  <h3>{t(language, "myProfileVideo")}</h3>
                  <video
                    className="greeting-video"
                    src={mediaUrl(profile.greeting_video_url)}
                    controls
                    playsInline
                    preload="metadata"
                  />
                </>
              ) : null}

              <h3>{t(language, "myProfileAbout")}</h3>
              <p>{profile.about}</p>
              {profile.hobbies ? (
                <>
                  <h3>{t(language, "myProfileHobbies")}</h3>
                  <p>{profile.hobbies}</p>
                </>
              ) : null}
              <h3>{t(language, "myProfileLookingFor")}</h3>
              <p>{profile.desired_partner}</p>
              {cover && profile.cover_answer ? (
                <>
                  <h3>{t(language, "myProfileCover")}</h3>
                  <p>
                    <em>{cover[language]}</em>
                    <br />
                    {profile.cover_answer}
                  </p>
                </>
              ) : null}
            </div>
          </article>
        ) : null}

        <Link to="/" className="btn btn--block my-profile-home">
          {t(language, "toHome")}
        </Link>
      </section>
    );
  }

  const hasVideo = Boolean(profile?.greeting_video_url);
  const nextLabel = busy
    ? t(language, "saving")
    : step === 12
      ? t(language, "submit")
      : step === VIDEO_STEP && !hasVideo
        ? t(language, "skip")
        : t(language, "next");
  const nextBtn = (
    <button
      type="button"
      className="btn btn--dark btn--block"
      disabled={busy || videoProgress !== null}
      onClick={() => void validateAndAdvance()}
    >
      {nextLabel}
    </button>
  );

  return (
    <WizardChrome language={language} step={step + INTRO_SCREENS} onBack={goBack} footer={nextBtn}>
      {error ? <p className="error-text">{error}</p> : null}

      {step === 1 && (
        <>
          <h2 className="wizard-title">{t(language, "qName")}</h2>
          <div className="field">
            <input
              value={form.name}
              maxLength={40}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              autoFocus
            />
          </div>
        </>
      )}

      {step === 2 && (
        <>
          <h2 className="wizard-title">{t(language, "qAge")}</h2>
          <div className="field">
            <input
              inputMode="numeric"
              value={form.age}
              onChange={(e) => setForm((f) => ({ ...f, age: e.target.value.replace(/\D/g, "") }))}
              autoFocus
            />
          </div>
        </>
      )}

      {step === 3 && (
        <>
          <h2 className="wizard-title">{t(language, "qHeight")}</h2>
          <div className="field">
            <input
              inputMode="numeric"
              value={form.height_cm}
              onChange={(e) => setForm((f) => ({ ...f, height_cm: e.target.value.replace(/\D/g, "") }))}
              autoFocus
            />
          </div>
        </>
      )}

      {step === 4 && (
        <>
          <h2 className="wizard-title">{t(language, "qCity")}</h2>
          <div className="field">
            <label>{t(language, "qCountry")}</label>
            <input value={form.country} onChange={(e) => setForm((f) => ({ ...f, country: e.target.value }))} />
          </div>
          <div className="field">
            <label>{t(language, "qCity")}</label>
            <input value={form.city} onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))} />
          </div>
        </>
      )}

      {step === 5 && (
        <>
          <h2 className="wizard-title">{t(language, "qProfession")}</h2>
          <div className="field">
            <input
              value={form.profession}
              onChange={(e) => setForm((f) => ({ ...f, profession: e.target.value }))}
              autoFocus
            />
          </div>
        </>
      )}

      {step === 6 && (
        <>
          <h2 className="wizard-title">{t(language, "qMarital")}</h2>
          <div className="choice-row" style={{ marginBottom: 18 }}>
            {(["single", "divorced"] as const).map((value) => (
              <button
                key={value}
                type="button"
                className={`choice-pill${form.marital_status === value ? " is-active" : ""}`}
                onClick={() => setForm((f) => ({ ...f, marital_status: value }))}
              >
                {t(language, value === "single" ? "maritalSingle" : "maritalDivorced")}
              </button>
            ))}
          </div>
          <p className="wizard-hint" style={{ marginBottom: 8 }}>
            {t(language, "qHasChildren")}
          </p>
          <div className="choice-row" style={{ marginBottom: 18 }}>
            <button
              type="button"
              className={`choice-pill${form.has_children ? " is-active" : ""}`}
              onClick={() => setForm((f) => ({ ...f, has_children: true }))}
            >
              {t(language, "yes")}
            </button>
            <button
              type="button"
              className={`choice-pill${!form.has_children ? " is-active" : ""}`}
              onClick={() => setForm((f) => ({ ...f, has_children: false }))}
            >
              {t(language, "no")}
            </button>
          </div>
          <p className="wizard-hint" style={{ marginBottom: 8 }}>
            {t(language, "qWantsChildren")}
          </p>
          <div className="choice-row">
            {(["yes", "no", "unsure"] as const).map((value) => (
              <button
                key={value}
                type="button"
                className={`choice-pill${form.wants_children === value ? " is-active" : ""}`}
                onClick={() => setForm((f) => ({ ...f, wants_children: value }))}
              >
                {t(language, value === "yes" ? "yes" : value === "no" ? "no" : "unsure")}
              </button>
            ))}
          </div>
        </>
      )}

      {step === 7 && (
        <>
          <h2 className="wizard-title">{t(language, "qAbout")}</h2>
          <p className="wizard-hint">{t(language, "qAboutHint")}</p>
          <div className="field">
            <textarea
              value={form.about}
              maxLength={1200}
              onChange={(e) => setForm((f) => ({ ...f, about: e.target.value }))}
            />
          </div>
          <div className="field">
            <label>{t(language, "qHobbies")}</label>
            <input
              value={form.hobbies}
              maxLength={300}
              onChange={(e) => setForm((f) => ({ ...f, hobbies: e.target.value }))}
            />
          </div>
        </>
      )}

      {step === 8 && (
        <>
          <h2 className="wizard-title">{t(language, "qDesired")}</h2>
          <p className="wizard-hint">{t(language, "qDesiredHint")}</p>
          <div className="field">
            <textarea
              value={form.desired_partner}
              maxLength={800}
              onChange={(e) => setForm((f) => ({ ...f, desired_partner: e.target.value }))}
            />
          </div>
          <div className="field-row">
            <div className="field">
              <label>{t(language, "qAgeMin")}</label>
              <input
                inputMode="numeric"
                value={form.age_min}
                onChange={(e) => setForm((f) => ({ ...f, age_min: e.target.value.replace(/\D/g, "") }))}
              />
            </div>
            <div className="field">
              <label>{t(language, "qAgeMax")}</label>
              <input
                inputMode="numeric"
                value={form.age_max}
                onChange={(e) => setForm((f) => ({ ...f, age_max: e.target.value.replace(/\D/g, "") }))}
              />
            </div>
          </div>
        </>
      )}

      {step === VIDEO_STEP && (
        <>
          <h2 className="wizard-title">{t(language, "qVideo")}</h2>
          <p className="wizard-hint">{t(language, "qVideoHint")}</p>
          {profile?.greeting_video_url && videoProgress === null ? (
            <video
              key={profile.greeting_video_url}
              className="greeting-video"
              src={mediaUrl(profile.greeting_video_url)}
              controls
              playsInline
              preload="metadata"
            />
          ) : null}
          {videoProgress !== null ? (
            <div className="greeting-video-progress" role="status">
              <div className="greeting-video-progress__bar" style={{ width: `${videoProgress}%` }} />
              <span>
                {videoProgress < 100
                  ? tf(language, "videoUploading", { percent: videoProgress })
                  : t(language, "videoProcessing")}
              </span>
            </div>
          ) : (
            <div className="greeting-video-actions">
              <button
                type="button"
                className="btn btn--cream btn--block"
                disabled={busy}
                onClick={() => videoInputRef.current?.click()}
              >
                {t(language, hasVideo ? "videoReplace" : "videoAdd")}
              </button>
              {hasVideo ? (
                <button
                  type="button"
                  className="btn btn--ghost btn--block greeting-video-remove"
                  disabled={busy}
                  onClick={() => void onVideoRemove()}
                >
                  {t(language, "videoRemove")}
                </button>
              ) : null}
            </div>
          )}
          <p className="chars-meta">{t(language, "videoLimitHint")}</p>
          <input
            ref={videoInputRef}
            type="file"
            accept="video/*"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              void onVideoPicked(file);
            }}
          />
        </>
      )}

      {step === 10 && (
        <>
          <h2 className="wizard-title">{t(language, "qCover")}</h2>
          <p className="wizard-hint">{t(language, "qCoverPick")}</p>
          <div className="cover-list">
            {Object.entries(COVER_QUESTIONS).map(([id, texts]) => {
              const num = Number(id);
              return (
                <button
                  key={id}
                  type="button"
                  className={`cover-item${form.cover_question_id === num ? " is-active" : ""}`}
                  onClick={() => setForm((f) => ({ ...f, cover_question_id: num }))}
                >
                  {texts[language]}
                </button>
              );
            })}
          </div>
          <div className="field">
            <label>{t(language, "qCoverAnswer")}</label>
            <input
              value={form.cover_answer}
              maxLength={70}
              onChange={(e) => setForm((f) => ({ ...f, cover_answer: e.target.value }))}
            />
            <div className="chars-meta">
              {tf(language, "charsLeft", { n: 70 - form.cover_answer.length })}
            </div>
          </div>
        </>
      )}

      {step === 11 && (
        <>
          <h2 className="wizard-title">{t(language, "qPhotos")}</h2>
          <p className="wizard-hint">{t(language, "qPhotosHint")}</p>
          <div className="photo-grid">
            {profile?.photos.map((photo) => (
              <div key={photo.id} className="photo-thumb">
                <img src={mediaUrl(photo.url)} alt="" />
                <button
                  type="button"
                  className="photo-thumb__remove"
                  aria-label={t(language, "removePhoto")}
                  onClick={() =>
                    void (async () => {
                      setBusy(true);
                      const updated = await deleteProfilePhoto(photo.id);
                      setBusy(false);
                      if (updated) setProfile(updated);
                    })()
                  }
                >
                  ×
                </button>
              </div>
            ))}
            {(profile?.photos.length ?? 0) < REQUIRED_PHOTOS ? (
              <button type="button" className="photo-add" onClick={() => fileRef.current?.click()}>
                {t(language, "addPhoto")}
              </button>
            ) : null}
          </div>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/*"
            multiple
            hidden
            onChange={(e) => {
              const files = e.target.files ? Array.from(e.target.files) : [];
              e.target.value = "";
              void onUpload(files);
            }}
          />
        </>
      )}

      {step === 12 && (
        <>
          <h2 className="wizard-title">{t(language, "qConsentTitle")}</h2>
          <div className="consent-box">{t(language, "consentShort")}</div>
          <div className="field">
            <label>{t(language, "qUsername")}</label>
            <input
              value={form.telegram_username}
              placeholder="@username"
              onChange={(e) => setForm((f) => ({ ...f, telegram_username: e.target.value }))}
            />
            <span className="wizard-hint" style={{ margin: 0 }}>
              {t(language, "qUsernameHint")}
            </span>
          </div>
          <label className="checkbox-row">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span>{t(language, "consentAgree")}</span>
          </label>
        </>
      )}
    </WizardChrome>
  );
}
