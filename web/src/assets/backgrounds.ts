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

/** Home screen photo tiles (web/public/photos/home_v2_*). */
export const homeAssets = {
  catalog: "/photos/home_v2_catalog_spb_bridge.jpg",
  messages: "/photos/home_v2_messages_rooftop.jpg",
  likes: "/photos/home_v2_likes_rome_kiss.jpg",
  profile: "/photos/home_v2_profile_positano.jpg",
  credits: "/photos/home_v2_credits_snow.jpg",
  referral: "/photos/home_v2_referral_winter_kiss.jpg",
  travel: "/photos/home_v2_travel_arches.jpg",
  // legacy aliases used by older screens
  matches: "/photos/home_v2_catalog_spb_bridge.jpg",
  letters: "/photos/home_v2_messages_rooftop.jpg",
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
