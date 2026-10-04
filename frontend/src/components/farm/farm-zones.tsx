import type { CSSProperties } from "react";
import Link from "next/link";
import { Crosshair, MapPin } from "lucide-react";
import { getZoneColor } from "@/config/zones";
import { rowStatePresentation } from "@/config/row-states";
import { formatZoneName, getZoneRows } from "@/lib/farm";
import { formatAngle } from "@/lib/formatters";
import type { FarmStatus } from "@/types/solar";

type FarmZonesProps = { farm: FarmStatus; targetId: string | null } & (
  | { mode: "overview" }
  | { mode: "inspection" | "operator"; selectedZone: string | null; selectedRow: string | null; onZone: (id: string) => void; onRow: (id: string) => void }
);

/** Shared membership, colors and row rendering; wrappers own presentation and interaction. */
export function FarmZones(props: FarmZonesProps) {
  const { farm, targetId } = props;
  const overview = props.mode !== "inspection";
  if (!farm.zones.length) return <p className={overview ? "dashboard-empty" : "fx-empty"}>No zones available in this payload.</p>;
  return <div className={overview ? "farm-schematic" : "fx-zone-grid"} role="group" aria-label="Farm zone summaries">{farm.zones.map(zone => {
    const rows = getZoneRows(farm, zone);
    const target = targetId !== null && zone.row_ids.includes(targetId);
    const name = formatZoneName(zone.zone_id);
    const label = <><MapPin size={20} aria-hidden="true"/><span><strong>{name}</strong><small>{zone.row_ids.length} rows · {zone.panel_count} panels</small></span>{target && <span className={overview ? "zone-target" : "fx-zone-target"}><Crosshair size={12} aria-hidden="true"/>{overview ? "Control target" : "TARGET"}</span>}</>;
    return <section key={zone.zone_id} className={overview ? "farm-zone" : "fx-zone"} data-target={target} data-selected={props.mode !== "overview" && props.selectedZone === zone.zone_id} style={{ "--zone-color": getZoneColor(zone.zone_id) } as CSSProperties}>
      {!overview && props.mode === "inspection" && <button className="fx-zone-label" type="button" aria-pressed={props.selectedZone === zone.zone_id} aria-label={`Inspect ${name}`} onClick={() => props.onZone(zone.zone_id)}>{label}</button>}
      {!rows.length && <p className={overview ? "dashboard-empty" : "fx-empty"}>No rows available in this zone.</p>}
      <div className={overview ? "zone-arrays" : "fx-array-grid"}>{rows.map(row => {
        const StateIcon = rowStatePresentation[row.current_state].icon;
        const isTarget = row.row_id === targetId;
        const description = `${row.row_id}, ${name}, ${row.panel_count} panels, ${formatAngle(row.angle_deg)}, ${row.current_state}, recorded action ${row.action}, ${isTarget ? "control target" : "not control target"}`;
        if (props.mode === "operator") return <button type="button" key={row.row_id} className="solar-row-motif" data-target={isTarget} data-state={row.current_state} aria-pressed={props.selectedRow === row.row_id} aria-label={`Inspect ${row.row_id}, ${name}, ${row.panel_count} panels, ${formatAngle(row.angle_deg)}, ${row.current_state}${isTarget ? ", control target" : ""}`} title={`${row.row_id} · ${formatAngle(row.angle_deg)} · ${row.current_state}`} onClick={() => props.onRow(row.row_id)}/>;
        if (overview) return <div key={row.row_id} className="solar-row-motif" data-target={isTarget} data-state={row.current_state} title={description}><span className="sr-only">{description}</span></div>;
        return <div className="fx-row-slot" key={row.row_id} style={{ "--state-color": rowStatePresentation[row.current_state].color } as CSSProperties}>
          <button type="button" className="fx-array-row" data-state={row.current_state} data-target={isTarget} aria-pressed={props.selectedRow === row.row_id} aria-label={`Inspect ${description}`} title={description} onClick={() => props.onRow(row.row_id)}><StateIcon size={11} aria-hidden="true"/><span>{row.row_id}</span>{isTarget && <Crosshair size={12} aria-hidden="true"/>}</button>
          <span aria-hidden="true" className="fx-mobile-row" data-state={row.current_state} data-target={isTarget} data-selected={props.selectedRow === row.row_id}><StateIcon size={9}/>{isTarget && <Crosshair size={10}/>}</span>
        </div>;
      })}</div>
      {props.mode === "operator" ? <button type="button" className="zone-label" aria-label={`Inspect ${name}`} aria-pressed={props.selectedZone === zone.zone_id} onClick={() => props.onZone(zone.zone_id)}>{label}</button> : overview ? <Link href="/farm" prefetch={false} className="zone-label" aria-label={`Open Farm to inspect ${name}: ${zone.row_ids.length} rows, ${zone.panel_count} panels${target ? ", contains control target" : ""}`}>{label}</Link> : <p className="fx-zone-foot">{target ? <>Contains control target · {targetId}</> : <>{zone.zone_id} · recorded snapshot</>}</p>}
    </section>;
  })}</div>;
}
