export type Tone = "neutral" | "info" | "success" | "warning" | "danger";
export type Size = "sm" | "md" | "lg";

export function classes(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}
