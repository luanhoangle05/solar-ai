"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Check, RotateCcw, ShieldAlert, ShieldCheck, Sparkles } from "lucide-react";
import { replayStage, type OperatorAnalysis } from "@/lib/operator-dashboard";

export function AiCommandCenter({ analysis }: { analysis: OperatorAnalysis }) {
  // The loaded recommendation stays visible; analysis starts only on user activation.
  const [stage, setStage] = useState(4);
  const [run, setRun] = useState(0);
  useEffect(() => {
    if (run === 0) return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const started = Date.now();
    let timer: ReturnType<typeof setInterval> | undefined;
    function stop() { if (timer) clearInterval(timer); timer = undefined; }
    function tick() { const next = replayStage(Date.now() - started, motion.matches); setStage(next); if (next === 4) stop(); }
    if (!motion.matches && analysis.available && !analysis.blocked && analysis.action !== "STOW") timer = setInterval(tick, 100);
    function preferenceChanged() { if (motion.matches) { stop(); setStage(4); } }
    motion.addEventListener("change", preferenceChanged);
    return () => { stop(); motion.removeEventListener("change", preferenceChanged); };
  }, [run, analysis.available, analysis.blocked, analysis.action]);
  function startAnalysis() {
    if (stage < 4) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setStage(4); setRun(value => value + 1); return; }
    setStage(0); setRun(value => value + 1);
  }
  const active = stage < 4 ? analysis.stages[stage] : null;
  const SafetyIcon = analysis.blocked ? ShieldAlert : ShieldCheck;
  return <section className="operator-ai operator-card" aria-labelledby="ai-heading" data-blocked={analysis.blocked} data-stow={analysis.action === "STOW"}>
    <header className="operator-card-heading"><Sparkles size={19} aria-hidden="true"/><h2 id="ai-heading">AI Agent Command Center</h2></header>
    <div className="ai-body">
      <span className="ai-analysis-label">Analysis of loaded results</span>
      <div className="ai-orb" data-active={!!active} aria-hidden="true"><Sparkles size={34}/>{active && <span className="ai-dots"><i/><i/><i/></span>}</div>
      <div className="ai-stage" aria-live="off">{active ? <><p className="ai-overline">AI Analysis · {stage + 1} of 4</p><h3>{active.title}</h3><p>{active.detail}</p></> : <><p className="ai-overline">{analysis.blocked || analysis.action === "STOW" ? "Safety first" : run === 0 ? "Available AI recommendation" : "AI Analysis complete"}</p><h3>{analysis.title}</h3><p>{analysis.blocked ? "Review the safety conditions before proceeding." : analysis.action === "STOW" ? "Review the protective recommendation below." : analysis.available ? "Your operating recommendation is ready." : "Please explore the available analysis in Simulation."}</p></>}</div>
      <div className="ai-progress" aria-label={active ? `Analysis step ${stage + 1} of 4` : run === 0 ? "Available analysis" : "Analysis complete"}>{analysis.stages.map((item,index) => <span key={index} data-complete={index < stage} data-active={index === stage} data-issue={item.issue} aria-hidden="true">{index < stage && <Check size={11}/>}</span>)}</div>
      <div className="ai-recommendation" data-positive={analysis.positive}>
        {analysis.available || analysis.action === "STOW" ? <><p>{analysis.instruction}</p><strong className="ai-angle">{analysis.angle}</strong><span className="ai-recommendation-only">Recommendation only</span></> : <p>No AI recommendation available</p>}
        {analysis.available && analysis.action !== "STOW" && <dl className="ai-benefits"><div><dt>Expected Gain</dt><dd>{analysis.gain}</dd></div><div><dt>Net Benefit</dt><dd>{analysis.benefit}</dd></div></dl>}
        <div className="ai-safety"><SafetyIcon size={17} aria-hidden="true"/><span>{analysis.blocked ? "Operation blocked" : analysis.action === "STOW" ? "Protective stow recommendation" : analysis.available ? "Safe to proceed" : "Safety checks passed"}</span></div>
        {(analysis.blocked || analysis.action === "STOW") && <p className="ai-safety-reason">{analysis.safetyReason}</p>}
      </div>
      <details className="operator-explanation"><summary>Why this recommendation?</summary><p>{analysis.explanation}</p></details>
      <div className="ai-actions">{analysis.available && !analysis.blocked && analysis.action !== "STOW" && <button type="button" className="operator-analysis-button" onClick={startAnalysis} disabled={stage < 4}><RotateCcw size={14} aria-hidden="true"/>{stage < 4 ? "Analyzing…" : run === 0 ? "Run AI Analysis" : "Run Again"}</button>}<Link className="operator-primary-link" href="/simulation" prefetch={false}>Open AI Simulation <ArrowUpRight size={16} aria-hidden="true"/></Link></div>
    </div>
    <p className="sr-only" role="status">{stage === 4 ? analysis.title : "Presenting the available AI analysis. The recommendation remains available below."}</p>
  </section>;
}
