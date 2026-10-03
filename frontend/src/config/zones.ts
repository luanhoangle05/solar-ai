// Visual identity only. Counts and membership always come from FrontendData.
export const zoneColors = {
  "zone-01": "var(--zone-01)",
  "zone-02": "var(--zone-02)",
  "zone-03": "var(--zone-03)",
  "zone-04": "var(--zone-04)",
} as const;
export function getZoneColor(id: string): string {
  return zoneColors[id as keyof typeof zoneColors] ?? "var(--muted-foreground)";
}
