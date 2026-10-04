import type { CSSProperties } from "react";
import { Crosshair, MapPin, PanelsTopLeft } from "lucide-react";
import { getZoneColor } from "@/config/zones";
import { rowStatePresentation } from "@/config/row-states";
import { formatZoneName, getZoneRows } from "@/lib/farm";
import { formatAngle } from "@/lib/formatters";
import type { FarmStatus } from "@/types/solar";
import { FarmPanel } from "./farm-panel";

export function FarmMap({ farm, targetId, selectedZone, selectedRow, onZone, onRow }: {
  farm: FarmStatus; targetId: string; selectedZone: string | null; selectedRow: string | null;
  onZone: (id:string) => void; onRow: (id:string) => void;
}) {
  return <FarmPanel title="Farm Explorer" icon={PanelsTopLeft} className="fx-map" meta={<span className="fx-note">2D SCHEMATIC · NOT GEOGRAPHIC</span>}>
    <div className="fx-canvas"><div className="fx-canvas-caption"><span>ZONE / ROW INSPECTION</span><span>Layout illustrative · membership exact</span></div>
      <div className="fx-zone-grid">{farm.zones.map(zone => {
        const rows = getZoneRows(farm,zone); const target = zone.row_ids.includes(targetId);
        return <section className="fx-zone" key={zone.zone_id} data-selected={selectedZone === zone.zone_id} style={{"--zone-color":getZoneColor(zone.zone_id)} as CSSProperties}>
          <button className="fx-zone-label" type="button" aria-pressed={selectedZone === zone.zone_id} aria-label={`Inspect ${formatZoneName(zone.zone_id)}`} onClick={() => onZone(zone.zone_id)}><MapPin size={20} aria-hidden="true"/><span><strong>{formatZoneName(zone.zone_id)}</strong><small>{zone.row_ids.length} rows · {zone.panel_count} panels</small></span>{target && <span className="fx-zone-target"><Crosshair size={13} aria-hidden="true"/>TARGET</span>}</button>
          <div className="fx-array-grid">{rows.map(row => {
            const StateIcon = rowStatePresentation[row.current_state].icon;
            const isTarget = row.row_id === targetId;
            const label = `${row.row_id}, ${formatZoneName(row.zone_id)}, ${row.panel_count} panels, ${formatAngle(row.angle_deg)}, ${row.current_state}, recorded action ${row.action}, ${isTarget ? "control target" : "not control target"}`;
            return <div className="fx-row-slot" key={row.row_id} style={{"--state-color":rowStatePresentation[row.current_state].color} as CSSProperties}>
              <button type="button" className="fx-array-row" data-state={row.current_state} data-target={isTarget} aria-pressed={selectedRow === row.row_id} aria-label={`Inspect ${label}`} title={label} onClick={() => onRow(row.row_id)}><StateIcon size={11} aria-hidden="true"/><span>{row.row_id}</span>{isTarget && <Crosshair size={12} aria-hidden="true"/>}</button>
              <span aria-hidden="true" className="fx-mobile-row" data-state={row.current_state} data-target={isTarget} data-selected={selectedRow === row.row_id}><StateIcon size={9}/>{isTarget && <Crosshair size={10}/>}</span>
            </div>;
          })}</div><p className="fx-zone-foot">{target ? <>Contains control target · {targetId}</> : <>{zone.zone_id} · recorded snapshot</>}</p>
        </section>;
      })}</div>
      <div className="fx-map-key"><span><Crosshair size={14} aria-hidden="true"/>TARGET · fixed pipeline scope</span><span><i aria-hidden="true"/>SELECTED · inspection only</span></div>
    </div><p className="fx-map-help">Select a zone or row to inspect. <span className="fx-mobile-help">On mobile, use the row selector or table for exact row inspection.</span> Selection never changes the control target or farm state.</p>
  </FarmPanel>;
}
