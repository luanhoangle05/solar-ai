import { PanelsTopLeft } from "lucide-react";
import { FeaturePlaceholder } from "@/components/shared/feature-placeholder";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataError } from "@/components/shared/data-error";
import { loadFrontendDataResult } from "@/lib/frontend-data.server";
import { getZoneColor } from "@/config/zones";
export const metadata = { title: "Farm & Zones | SolarAI" };
export default async function Page() {
  const result = await loadFrontendDataResult();
  if (!result.ok) return <DataError message={result.error.message} details={result.error.details} />;
  const farm = result.data.farm_status;
  return <FeaturePlaceholder icon={PanelsTopLeft} title="Farm & Zones" description="Inspect the solar farm by zone and row." planned="The interactive farm visualization will be added in a future phase."><Card><CardHeader><CardTitle>Farm contract summary</CardTitle><p className="text-sm text-muted-foreground">{farm.total_panels.toLocaleString("en-US")} panels · {farm.rows.length} rows · {farm.zones.length} zones</p></CardHeader><CardContent><dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{farm.zones.map(zone => <div key={zone.zone_id} className="rounded-lg border border-border bg-background p-3"><dt className="flex items-center gap-2 text-sm"><span className="size-2 rounded-full" style={{background:getZoneColor(zone.zone_id)}} aria-hidden="true" />{zone.zone_id}</dt><dd className="mt-2 text-lg font-semibold">{zone.panel_count} panels<span className="mt-1 block text-xs font-normal text-muted-foreground">{zone.row_ids.length} rows</span></dd></div>)}</dl></CardContent></Card></FeaturePlaceholder>;
}
