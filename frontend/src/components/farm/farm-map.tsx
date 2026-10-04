import { Crosshair, PanelsTopLeft } from "lucide-react";

import { FarmZones } from "./farm-zones";
import type { FarmStatus } from "@/types/solar";
import { FarmPanel } from "./farm-panel";

export function FarmMap({ farm, targetId, selectedZone, selectedRow, onZone, onRow }: {
  farm: FarmStatus; targetId: string; selectedZone: string | null; selectedRow: string | null;
  onZone: (id:string) => void; onRow: (id:string) => void;
}) {
  return <FarmPanel title="Farm Explorer" icon={PanelsTopLeft} className="fx-map" meta={<span className="fx-note">2D SCHEMATIC · NOT GEOGRAPHIC</span>}>
    <div className="fx-canvas"><div className="fx-canvas-caption"><span>ZONE / ROW INSPECTION</span><span>Layout illustrative · membership exact</span></div>
      <FarmZones mode="inspection" farm={farm} targetId={targetId} selectedZone={selectedZone} selectedRow={selectedRow} onZone={onZone} onRow={onRow}/>
      <div className="fx-map-key"><span><Crosshair size={14} aria-hidden="true"/>TARGET · fixed pipeline scope</span><span><i aria-hidden="true"/>SELECTED · inspection only</span></div>
    </div><p className="fx-map-help">Select a zone or row to inspect. <span className="fx-mobile-help">On mobile, use the row selector or table for exact row inspection.</span> Selection never changes the control target or farm state.</p>
  </FarmPanel>;
}
