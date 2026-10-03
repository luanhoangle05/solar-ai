import { describe, expect, it } from "vitest";
import { isActiveRoute, navigation } from "./navigation";
import { getZoneColor, zoneColors } from "./zones";
import { dataStatusVariants } from "./status";
import { dataStatusSchema } from "../schemas/frontend-data";
import { loadFrontendData } from "../lib/frontend-data.server";
describe("application navigation", () => {
  it("has unique paths and the intended primary routes", () => {
    expect(new Set(navigation.map(item => item.href)).size).toBe(navigation.length);
    expect(navigation.filter(item => item.primary).map(item => item.href)).toEqual(["/", "/simulation", "/optimization", "/analytics"]);
  });
  it.each([
    ["/", "/", true], ["/farm", "/", false],
    ["/optimization/candidates", "/optimization", true],
    ["/farm/zone-01", "/farm", true], ["/farmland", "/farm", false],
    ["/optimization-old", "/optimization", false], ["/weather", "/farm", false],
  ])("matches %s against %s as %s", (pathname, href, expected) => {
    expect(isActiveRoute(pathname, href)).toBe(expected);
  });
});
describe("semantic presentation", () => {
  it("covers all canonical fixture zones without embedding farm counts", async () => {
    const data = await loadFrontendData();
    expect(Object.keys(zoneColors)).toEqual(["zone-01", "zone-02", "zone-03", "zone-04"]);
    expect(data.farm_status.zones.every(zone => zone.zone_id in zoneColors)).toBe(true);
    expect(new Set(Object.values(zoneColors)).size).toBe(4);
    expect(getZoneColor("future-zone")).toBe("var(--muted-foreground)");
  });
  it("covers every contract data status and distinguishes invalid data", () => {
    expect(Object.keys(dataStatusVariants)).toEqual(dataStatusSchema.options);
    expect(dataStatusVariants).toEqual({VALID:"success", DEGRADED:"warning", STALE:"warning", INVALID:"danger"});
  });
});
