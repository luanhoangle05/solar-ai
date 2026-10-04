import { beforeAll, describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { loadFrontendData } from "./frontend-data.server";
import { FarmZones } from "../components/farm/farm-zones";
import type { FrontendData } from "../types/solar";

let data: FrontendData;
beforeAll(async () => { data = await loadFrontendData(); });
describe("shared farm overview", () => {
  it("presents every loaded row and supplied zone count without mutation", () => {
    const before = structuredClone(data);
    const html = renderToStaticMarkup(<FarmZones mode="overview" farm={data.farm_status} targetId={data.metadata.control_target_id}/>);
    for (const row of data.farm_status.rows) expect(html).toContain(`${row.row_id}, Zone`);
    for (const zone of data.farm_status.zones) expect(html).toContain(`${zone.row_ids.length} rows, ${zone.panel_count} panels`);
    expect(data).toEqual(before);
  });
  it("moves the target indicator to its actual zone rather than the first zone", () => {
    const html = renderToStaticMarkup(<FarmZones mode="overview" farm={data.farm_status} targetId="row-049"/>);
    expect(html).toContain('aria-label="Open Farm to inspect Zone 4: 12 rows, 240 panels, contains control target"');
    expect(html).not.toContain('aria-label="Open Farm to inspect Zone 1: 13 rows, 260 panels, contains control target"');
    expect(html).toContain("row-049, Zone 4, 20 panels, 0°, STOWED, recorded action STOW, control target");
  });
  it("offers navigation only, with no inspection controls or WebGL", () => {
    const html = renderToStaticMarkup(<FarmZones mode="overview" farm={data.farm_status} targetId={null}/>);
    expect(html.match(/href="\/farm"/g)).toHaveLength(data.farm_status.zones.length);
    expect(html).not.toMatch(/<(button|input|select|canvas)\b/);
    expect(html).not.toContain(", contains control target");
  });
});
