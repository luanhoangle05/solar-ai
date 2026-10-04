import { beforeAll, describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import Dashboard from "../app/(dashboard)/page";
let html: string;
beforeAll(async () => { html = renderToStaticMarkup(await Dashboard()); });
describe("Dashboard small cleanup", () => {
  it("starts directly with the layout without the page heading or badge", () => {
    expect(html).not.toMatch(/<h1\b|operator-heading|Solar farm overview and AI recommendation|Demo Data/);
    expect(html).toContain('class="operator-grid"');
  });
  it("omits the Control Target card while preserving farm target context", () => {
    expect(html).not.toContain('class="operator-target operator-card"');
    expect(html).not.toMatch(/<h2[^>]*>Control Target<\/h2>/);
    expect(html).toContain("row-001");
  });
  it("offers user-started analysis without Replay wording", () => {
    expect(html).toContain("Run AI Analysis");
    expect(html).not.toContain("Run Again");
    expect(html).not.toMatch(/replay/i);
  });
});
