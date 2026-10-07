/**
 * Background photo pool from TechnicalSpecification/MiniApp_Reference/Background_Photo/.
 */
export const backgroundAssets = {
  bg_spb_winter: "/backgrounds/bg_spb_winter.jpg",
  bg_rome_night: "/backgrounds/bg_rome_night.jpg",
  bg_positano_run: "/backgrounds/bg_positano_run.jpg",
  bg_couple_silhouette: "/backgrounds/bg_couple_silhouette.jpg",
  bg_italy_coast: "/backgrounds/bg_italy_coast.jpg",
  bg_spb_bridge: "/backgrounds/bg_spb_bridge.jpg",
} as const;

export type BackgroundKey = keyof typeof backgroundAssets;

/** Loading / splash uses the final composed poster, not the raw pool. */
export const loadingPoster = "/Loading_Photo.jpg";

export const dreamLocationAssets = {
  positano: "/dreams/positano.jpg",
  rome: "/dreams/rome.jpg",
  milan: "/dreams/milan.jpg",
  other: "/dreams/other.jpg",
} as const;

export type DreamLocationKey = keyof typeof dreamLocationAssets;

export const profileIntroAssets = {
  ru: "/photos/profile_intro_ru.jpg",
  it: "/photos/profile_intro_it.jpg",
} as const;

export const homeAssets = {
  letters: "/photos/home_letters.jpg",
  create: "/photos/home_create.jpg",
} as const;

/** Guide media by app language. Filenames keep historical gender labels. */
export const guideAssets = {
  ru: { pdf: "/guide/guide_women.pdf", audio: "/guide/guide_women.ogg" },
  it: { pdf: "/guide/guide_men.pdf", audio: "/guide/guide_men.ogg" },
} as const;
