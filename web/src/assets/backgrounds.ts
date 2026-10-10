/**
 * Background photo pool from TechnicalSpecification/MiniApp_Reference/Background_Photo/.
 */
export const backgroundAssets = {
  bg_positano_run: "/backgrounds/bg_positano_run.jpg",
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
  matches: "/photos/home_matches_rome_night_couple.jpg",
  profile: "/photos/home_profile_spb_winter_couple.jpg",
  credits: "/photos/home_credits_snow_girl.jpg",
} as const;

/** Guide media by app language. Filenames keep historical gender labels. */
export const guideAssets = {
  ru: { pdf: "/guide/guide_women.pdf", audio: "/guide/guide_women.ogg" },
  it: { pdf: "/guide/guide_men.pdf", audio: "/guide/guide_men.ogg" },
} as const;

export const introVideo = {
  poster: "/backgrounds/bg_positano_run.jpg",
  ru: "/intro/intro_ru.mp4",
  it: "/intro/intro_it.mp4",
} as const;

export const guidePhotos = {
  listen: "/photos/guide_listen_spb_kazan_couple.jpg",
  read: "/photos/guide_read_rome_sunset_kiss.jpg",
} as const;
