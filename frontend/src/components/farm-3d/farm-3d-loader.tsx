"use client";

import dynamic from "next/dynamic";
import { Component, type ReactNode } from "react";
import type { FarmStatus } from "@/types/solar";

export type Farm3DProps = {
  farm: FarmStatus; targetId: string; selectedRow: string | null; selectedZone: string | null;
  onRow: (id: string) => void; onZone: (id: string) => void; onExit: () => void;
};
const Scene = dynamic(() => import("./farm-3d-scene"), {
  ssr: false,
  loading: () => <div className="f3-loading" role="status">Preparing the 3D farm…</div>,
});

export function SceneUnavailable({ onExit }: { onExit: () => void }) {
  return <div className="f3-loading" role="status"><strong>3D visualization unavailable on this device.</strong><p>Use the 2D farm view instead. Your inspection selection is retained.</p><button type="button" onClick={onExit}>Return to 2D</button></div>;
}
class SceneBoundary extends Component<{ children: ReactNode; onExit: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <SceneUnavailable onExit={this.props.onExit}/> : this.props.children; }
}
export function Farm3DLoader(props: Farm3DProps) {
  if (!props.farm.zones.length || !props.farm.rows.length) {
    return <div className="f3-loading" role="status"><strong>No farm geometry available in this payload.</strong><p>The row table and 2D view remain available for inspection.</p><button type="button" onClick={props.onExit}>Return to 2D</button></div>;
  }
  return <SceneBoundary onExit={props.onExit}><Scene {...props}/></SceneBoundary>;
}
