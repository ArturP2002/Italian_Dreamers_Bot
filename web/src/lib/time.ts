/** Must match APP_TIMEZONE on the backend. */
export const APP_TIME_ZONE = "Europe/Rome";

/** ISO timestamp → "YYYY-MM-DDTHH:MM" wall-clock value in APP_TIME_ZONE for <input type="datetime-local">. */
export function toAppZoneInputValue(iso: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: APP_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "00";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}
