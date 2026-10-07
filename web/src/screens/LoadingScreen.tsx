import loadingPhoto from "../assets/Loading_Photo.jpg";
import type { Language } from "../i18n/messages";
import "./LoadingScreen.css";

type Props = {
  /** First visit: show language enter buttons. Returning: poster only while boot finishes. */
  mode: "choose" | "boot";
  onEnter: (language: Language) => void;
};

export function LoadingScreen({ mode, onEnter }: Props) {
  return (
    <section className="loading-screen screen" aria-label="Italian Dreamers">
      <img
        className="loading-screen__bg"
        src={loadingPhoto}
        alt="San Pietroburgo · Positano — Italian Dreamers"
        decoding="async"
      />
      <div className="loading-screen__veil" aria-hidden />
      {mode === "choose" ? (
        <div className="loading-screen__actions">
          <button type="button" className="btn btn--cream" onClick={() => onEnter("ru")}>
            Войти
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => onEnter("it")}>
            Entra
          </button>
        </div>
      ) : (
        <div className="loading-screen__boot" aria-hidden />
      )}
    </section>
  );
}
