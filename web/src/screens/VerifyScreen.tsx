import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PhotoGuideSheet } from "../components/PhotoGuideSheet";
import { type Language, type MessageKey, t } from "../i18n/messages";
import { fetchMe, uploadVerificationSelfie } from "../lib/api";

type Props = { language: Language; onRefresh?: () => void };

type CamState = "idle" | "starting" | "live" | "denied";
type RitualPhase = "idle" | "analyzing" | "result";
type VerdictKind = "success" | "soft" | "fail";

const WAIT_PHRASES: MessageKey[] = [
  "verifyWait1",
  "verifyWait2",
  "verifyWait3",
];

const MIN_ANALYZE_MS = 2000;
const PHRASE_MS = 1200;

async function requestCameraStream(): Promise<MediaStream> {
  const media = navigator.mediaDevices;
  if (!media?.getUserMedia) {
    throw new Error("getUserMedia unsupported");
  }
  const attempts: MediaStreamConstraints[] = [
    { audio: false, video: { facingMode: { ideal: "user" }, width: { ideal: 720 }, height: { ideal: 720 } } },
    { audio: false, video: { facingMode: "user" } },
    { audio: false, video: true },
  ];
  let lastError: unknown;
  for (const constraints of attempts) {
    try {
      return await media.getUserMedia(constraints);
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("camera_denied");
}

function captureSelfieJpeg(video: HTMLVideoElement): Promise<Blob | null> {
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  if (!vw || !vh) return Promise.resolve(null);
  const maxSide = 1280;
  const scale = Math.min(1, maxSide / Math.max(vw, vh));
  const w = Math.max(1, Math.round(vw * scale));
  const h = Math.max(1, Math.round(vh * scale));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return Promise.resolve(null);
  ctx.translate(w, 0);
  ctx.scale(-1, 1);
  ctx.drawImage(video, 0, 0, w, h);
  return new Promise((resolve) => canvas.toBlob((b) => resolve(b), "image/jpeg", 0.92));
}

function hapticImpact(style: "light" | "medium" = "light") {
  window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.(style);
}

function hapticNotify(type: "success" | "error" | "warning") {
  window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred?.(type);
}

function humanFailReason(language: Language, raw: string | null | undefined): string {
  const text = (raw || "").toLowerCase();
  if (!text) return t(language, "verifyFailReasonGeneric");
  if (text.includes("different") || text.includes("do not look") || text.includes("not look")) {
    return t(language, "verifyFailReasonMismatch");
  }
  if (text.includes("empty") || text.includes("no face") || text.includes("no person")) {
    return t(language, "verifyFailReasonFace");
  }
  if (text.includes("screen") || text.includes("print")) {
    return t(language, "verifyFailReasonFace");
  }
  return t(language, "verifyFailReasonGeneric");
}

export function VerifyScreen({ language, onRefresh }: Props) {
  const navigate = useNavigate();
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [photoGuideOpen, setPhotoGuideOpen] = useState(false);
  const [camState, setCamState] = useState<CamState>("idle");
  const [ritualPhase, setRitualPhase] = useState<RitualPhase>("idle");
  const [ritualExpanded, setRitualExpanded] = useState(false);
  const [freezeUrl, setFreezeUrl] = useState<string | null>(null);
  const [waitIndex, setWaitIndex] = useState(0);
  const [verdict, setVerdict] = useState<VerdictKind>("success");
  const [verdictTitle, setVerdictTitle] = useState("");
  const [verdictBody, setVerdictBody] = useState("");
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const freezeUrlRef = useRef<string | null>(null);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    const video = videoRef.current;
    if (video) video.srcObject = null;
    setCamState("idle");
  }, []);

  const clearFreeze = useCallback(() => {
    if (freezeUrlRef.current) {
      URL.revokeObjectURL(freezeUrlRef.current);
      freezeUrlRef.current = null;
    }
    setFreezeUrl(null);
  }, []);

  useEffect(() => {
    void fetchMe().then((me) => setStatus(me?.verification_status ?? "none"));
    return () => {
      stopCamera();
      clearFreeze();
    };
  }, [stopCamera, clearFreeze]);

  useEffect(() => {
    if (ritualPhase !== "analyzing") return;
    setWaitIndex(0);
    const id = window.setInterval(() => {
      setWaitIndex((i) => (i + 1) % WAIT_PHRASES.length);
    }, PHRASE_MS);
    return () => window.clearInterval(id);
  }, [ritualPhase]);

  useEffect(() => {
    if (ritualPhase === "idle") {
      setRitualExpanded(false);
      return;
    }
    const id = window.requestAnimationFrame(() => setRitualExpanded(true));
    return () => window.cancelAnimationFrame(id);
  }, [ritualPhase]);

  const startLivePreview = async () => {
    if (camState === "starting" || camState === "live" || ritualPhase !== "idle") return;
    setError(null);
    setCamState("starting");
    try {
      const stream = await requestCameraStream();
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) {
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        setCamState("denied");
        return;
      }
      video.setAttribute("playsinline", "true");
      video.setAttribute("webkit-playsinline", "true");
      video.muted = true;
      video.srcObject = stream;
      await video.play();
      setCamState("live");
    } catch {
      stopCamera();
      setCamState("denied");
      setError(t(language, "verifyCameraDenied"));
    }
  };

  const finishRitual = (kind: VerdictKind, title: string, body: string, nextStatus: string) => {
    setVerdict(kind);
    setVerdictTitle(title);
    setVerdictBody(body);
    setStatus(nextStatus);
    setRitualPhase("result");
    if (kind === "fail") hapticNotify("error");
    else hapticNotify("success");
    onRefresh?.();
  };

  const captureFromPreview = async () => {
    const video = videoRef.current;
    if (!video || camState !== "live" || ritualPhase !== "idle") return;

    const blob = await captureSelfieJpeg(video);
    if (!blob) {
      setError(t(language, "verifyCaptureFailed"));
      return;
    }

    hapticImpact("medium");
    clearFreeze();
    const url = URL.createObjectURL(blob);
    freezeUrlRef.current = url;
    setFreezeUrl(url);
    stopCamera();
    setRitualPhase("analyzing");
    setError(null);

    const started = Date.now();
    try {
      const file = new File([blob], "selfie.jpg", { type: "image/jpeg" });
      const res = await uploadVerificationSelfie(file);
      const elapsed = Date.now() - started;
      if (elapsed < MIN_ANALYZE_MS) {
        await new Promise((r) => setTimeout(r, MIN_ANALYZE_MS - elapsed));
      }

      if (res.verification_status === "verified") {
        finishRitual("success", t(language, "verifyResultSuccessTitle"), t(language, "verifyResultSuccessBody"), "verified");
        return;
      }
      if (res.verification_status === "pending") {
        finishRitual("soft", t(language, "verifyResultSoftTitle"), t(language, "verifyResultSoftBody"), "pending");
        return;
      }
      finishRitual(
        "fail",
        t(language, "verifyResultFailTitle"),
        humanFailReason(language, res.auto_reason),
        "rejected",
      );
    } catch (e) {
      const elapsed = Date.now() - started;
      if (elapsed < MIN_ANALYZE_MS) {
        await new Promise((r) => setTimeout(r, MIN_ANALYZE_MS - elapsed));
      }
      const raw = e instanceof Error ? e.message : "";
      if (raw.includes("group_photo")) {
        setPhotoGuideOpen(true);
        finishRitual("fail", t(language, "verifyResultFailTitle"), t(language, "photoGroupRejected"), "rejected");
      } else if (raw.includes("selfie_no_person") || raw.includes("no_person")) {
        finishRitual("fail", t(language, "verifyResultFailTitle"), t(language, "writeNoPerson"), "rejected");
      } else {
        finishRitual("fail", t(language, "verifyResultFailTitle"), t(language, "verifyCaptureFailed"), status ?? "none");
      }
    }
  };

  const onDone = () => {
    clearFreeze();
    setRitualPhase("idle");
    navigate("/");
  };

  const canCapture = status !== "verified" && status !== "pending" && ritualPhase === "idle";
  const isLive = camState === "live";
  const isStarting = camState === "starting";
  const ritualActive = ritualPhase !== "idle";

  return (
    <section className={`screen screen--milky verify-screen${ritualActive ? " verify-screen--ritual" : ""}`}>
      {!ritualActive ? (
        <>
          <Link to="/" className="work-back" onClick={() => stopCamera()}>
            ← {t(language, "backHome")}
          </Link>
          <h1 className="work-title">{t(language, "verifyTitle")}</h1>
          <p className="work-body verify-screen__lead">{t(language, "verifyHint")}</p>

          {status === "verified" ? <p className="home-meta">{t(language, "verifyOk")}</p> : null}
          {status === "pending" ? <p className="home-meta">{t(language, "verifyPending")}</p> : null}
          {status === "rejected" && !error ? <p className="form-error">{t(language, "verifyRejected")}</p> : null}
        </>
      ) : null}

      {canCapture ? (
        <>
          {!isLive ? (
            <ol className="verify-steps">
              <li>{t(language, "verifyStep1")}</li>
              <li>{t(language, "verifyStep2")}</li>
              <li>{t(language, "verifyStep3")}</li>
            </ol>
          ) : (
            <p className="verify-live-hint">{t(language, "verifyOvalHint")}</p>
          )}

          <div className="verify-camera">
            <div
              className={[
                "verify-camera__frame",
                isLive ? "verify-camera__frame--live" : "",
                isStarting ? "verify-camera__frame--starting" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <video
                ref={videoRef}
                className="verify-camera__video"
                playsInline
                muted
                autoPlay
              />
              <div className="verify-camera__ring" aria-hidden />
              {isStarting ? <span className="verify-camera__pulse" aria-hidden /> : null}
            </div>
          </div>

          {isLive ? (
            <button
              type="button"
              className="btn btn--block btn--dark"
              onClick={() => void captureFromPreview()}
            >
              {t(language, "verifyShoot")}
            </button>
          ) : (
            <button
              type="button"
              className="btn btn--block btn--dark"
              disabled={isStarting}
              onClick={() => void startLivePreview()}
            >
              {isStarting ? t(language, "verifyCameraStarting") : t(language, "verifyOpenCamera")}
            </button>
          )}
        </>
      ) : null}

      {error && !ritualActive ? <p className="form-error">{error}</p> : null}

      {ritualActive ? (
        <div className={`verify-ritual${ritualExpanded ? " verify-ritual--expanded" : ""}`} role="status" aria-live="polite">
          <div className="verify-ritual__scrim" aria-hidden />
          <div className="verify-ritual__stage">
            <div className="verify-ritual__circle">
              {freezeUrl ? <img src={freezeUrl} alt="" className="verify-ritual__photo" /> : null}
              <div className="verify-ritual__veil" aria-hidden />
              {ritualPhase === "analyzing" ? (
                <p key={waitIndex} className="verify-ritual__phrase">
                  {t(language, WAIT_PHRASES[waitIndex])}
                </p>
              ) : null}
              {ritualPhase === "result" ? (
                <div className={`verify-ritual__verdict verify-ritual__verdict--${verdict}`}>
                  <p className="verify-ritual__verdict-title">{verdictTitle}</p>
                  <p className="verify-ritual__verdict-body">{verdictBody}</p>
                </div>
              ) : null}
            </div>
            {ritualPhase === "result" ? (
              <button type="button" className="btn btn--block btn--dark verify-ritual__done" onClick={onDone}>
                {t(language, "verifyDone")}
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      <PhotoGuideSheet
        language={language}
        open={photoGuideOpen}
        onClose={() => setPhotoGuideOpen(false)}
      />
    </section>
  );
}
