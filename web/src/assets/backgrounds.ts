/**
 * Background photo pool from TechnicalSpecification/MiniApp_Reference/Background_Photo/.
 */
export const backgroundAssets = {
  bg_spb_kazan_couple: "/backgrounds/bg_spb_kazan_couple.jpg",
} as const;

export type BackgroundKey = keyof typeof backgroundAssets;

/** Loading / splash uses the final composed poster, not the raw pool. */
export const loadingPoster = "/Loading_Photo.jpg";

export const profileIntroAssets = {
  ru: "/photos/profile_intro_ru.jpg",
  it: "/photos/profile_intro_it.jpg",
} as const;

export const profileIntroPhotos = {
  top: "/photos/intro_top_spb_rooftop.jpg",
  bottom: "/photos/intro_bottom_rome_sunset_couple.jpg",
} as const;

export const homeAssets = {
  matches: "/photos/home_matches_spb_winter_couple.jpg",
  profile: "/photos/home_profile_rome_night_couple.jpg",
  credits: "/photos/home_credits_snow_girl.jpg",
} as const;

/** Guide media by app language. Filenames keep historical gender labels. */
export const guideAssets = {
  ru: { pdf: "/guide/guide_women.pdf", audio: "/guide/guide_women.ogg" },
  it: { pdf: "/guide/guide_men.pdf", audio: "/guide/guide_men.ogg" },
} as const;

export const introVideo = {
  ru: { src: "/intro/intro_ru.mp4", poster: "/intro/intro_ru_poster.jpg" },
  it: { src: "/intro/intro_it.mp4", poster: "/intro/intro_it_poster.jpg" },
} as const;

export const wizardStepPhotos = {
  city: "/photos/step_city_positano_run.jpg",
  profession: "/photos/step_profession_spb_bridge_couple.jpg",
} as const;

export const guidePhotos = {
  listen: "/photos/guide_listen_spb_kazan_couple.jpg",
  read: "/photos/guide_read_rome_sunset_kiss.jpg",
} as const;
