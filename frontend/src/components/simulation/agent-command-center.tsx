"use client";
import { useEffect, useState } from "react";
import { ArrowRight, Bot, ChartColumn, CircleCheck, Clock, Cog, Database, Hourglass, RotateCcw, ShieldCheck, Sparkles, TriangleAlert, Workflow, Zap } from "lucide-react";
import type { AgentName } from "@/types/solar";
import type { CommandCenterAgent, CommandCenterView } from "@/lib/command-center";
import "./command-center.css";

const icons: Record<AgentName, typeof Database> = { data: Database, modeling: ChartColumn, optimization: Cog, manager: ShieldCheck };
const STEP_MS = 2400;
type Phase = "done" | "active" | "waiting";

/**
 * Presents the recorded agent run. The server-rendered and resting state is always the recorded outcome;
 * The analysis button walks through the same loaded stages for presentation only.
 */
export function AgentCommandCenter({ view }: { view: CommandCenterView }) {
  // null = resting on the recorded outcome; 0..3 = index of the agent highlighted during the presentation.
  const [step, setStep] = useState<number | null>(null);
  useEffect(() => {
    if (step === null) return;
    const timer = setTimeout(() => setStep(step >= view.agents.length - 1 ? null : step + 1), STEP_MS);
    return () => clearTimeout(timer);
  }, [step, view.agents.length]);
  const [played, setPlayed] = useState(false);
  const replaying = step !== null;
  const phaseOf = (index: number): Phase => !replaying || index < step ? "done" : index === step ? "active" : "waiting";
  const progress = replaying ? step / (view.agents.length - 1) : 1;

  return <section className="acc" aria-label="AI Agent Command Center" data-replaying={replaying}>
    <header className="acc-header">
      <h2><Workflow size={22} aria-hidden="true"/>AI Agent Command Center</h2>
      <p>Agent decision flow for the recorded optimization cycle.</p>
      <span className="acc-mode">{replaying ? "ANALYZING LOADED RESULTS" : view.isMock ? "MOCK FIXTURE · RECORDED RUN" : "RECORDED RUN"}</span>
      <button type="button" className="acc-replay" onClick={() => { if (!replaying) { setStep(0); setPlayed(true); } }} disabled={replaying} aria-disabled={replaying}><RotateCcw size={13} aria-hidden="true"/>{replaying ? "Analyzing…" : played ? "Run Again" : "Run AI Analysis"}</button>
      <p className="acc-live" role="status">{replaying ? `Analyzing loaded results: ${view.agents[step].title}` : played ? "Analysis complete. Showing the recorded outcome." : ""}</p>
    </header>
    <div className="acc-body">
      <div className="acc-flow">
        <ol className="acc-agents">{view.agents.map((agent, index) => <AgentCard key={agent.agent} agent={agent} index={index} phase={phaseOf(index)} last={index === view.agents.length - 1}/>)}</ol>
        <ol className="acc-track" aria-hidden="true" style={{ "--acc-progress": progress } as React.CSSProperties}>{view.agents.map((agent, index) => {
          const phase = phaseOf(index);
          return <li key={agent.agent} data-phase={phase} data-status={agent.status}><span className="acc-node" aria-hidden="true">{phase === "done" && agent.status === "COMPLETED" && <CircleCheck size={18}/>}</span>{phase === "active" ? agent.replayLabel : agent.milestone}</li>;
        })}</ol>
        {view.hasReasoning && <section className="acc-reasoning" aria-label="Agent reasoning">
          <h3><Sparkles size={15} aria-hidden="true"/>Agent reasoning<small>Written by an LLM from each agent&apos;s recorded tool results. The figures and the decision come from the tools, not the LLM.</small></h3>
          <ol>{view.agents.map((agent, index) => agent.reasoning && <li key={agent.agent} data-phase={phaseOf(index)}>
            <strong>{agent.title}</strong><p>{phaseOf(index) === "done" ? agent.reasoning : phaseOf(index) === "active" ? "Reasoning…" : "Waiting for the previous agent."}</p>
          </li>)}</ol>
        </section>}
      </div>
      <aside className="acc-summary" aria-label="Cycle summary">
        <div><ChartColumn size={24} aria-hidden="true"/><span>Current cycle</span><strong>{view.cycle}</strong><small>{view.action}</small></div>
        <div data-tone="gain"><Zap size={24} aria-hidden="true"/><span>Estimated gain</span><strong>{view.gain}</strong></div>
        <div data-tone="pending"><Clock size={24} aria-hidden="true"/><span>Execution status</span><strong>{replaying ? "Analyzing…" : view.execution.status}</strong><p>{view.execution.note}</p></div>
      </aside>
    </div>
  </section>;
}

function AgentCard({ agent, index, phase, last }: { agent: CommandCenterAgent; index: number; phase: Phase; last: boolean }) {
  const Icon = icons[agent.agent];
  const badge = phase === "active" ? agent.replayLabel : phase === "waiting" ? "WAITING" : agent.status;
  const BodyIcon = phase === "waiting" ? Hourglass : phase === "active" ? Bot : agent.status === "COMPLETED" ? CircleCheck : TriangleAlert;
  return <li className="acc-agent" data-phase={phase} data-status={agent.status}>
    <div className="acc-agent-top">
      <span className="acc-agent-icon"><Icon size={24} aria-hidden="true"/></span>
      <div><h3>{index + 1}. {agent.title}</h3><p>{agent.role}</p></div>
      <span className="acc-badge">{phase === "done" && agent.status === "COMPLETED" && <CircleCheck size={11} aria-hidden="true"/>}{badge}</span>
    </div>
    <div className="acc-agent-body"><BodyIcon size={20} aria-hidden="true"/><p>{phase === "waiting" ? "Waiting for the previous agent." : agent.headline}</p></div>
    <ul className="acc-agent-lines">{agent.lines.map(line => <li key={line}>{line}</li>)}</ul>
    {!last && <ArrowRight className="acc-arrow" size={20} aria-hidden="true"/>}
  </li>;
}
