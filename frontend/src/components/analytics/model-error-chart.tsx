"use client";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ModelMetrics } from "@/types/solar";
import { formatMetric, formatModelName } from "@/lib/formatters";

export function ModelErrorChart({ models }: { models: ModelMetrics[] }) {
  const values = models.filter(model => model.mae !== null && model.rmse !== null).map(model => ({...model,name:formatModelName(model.model)}));
  if (!values.length) return <p className="inspect-empty">No model error metrics available.</p>;
  return <div className="inspect-model-chart" role="group" aria-label="Supplied MAE and RMSE comparison. Exact metrics appear in Model Comparison below."><ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={{width:550,height:245}}><BarChart data={values} margin={{top:10,right:12,bottom:15,left:0}} accessibilityLayer>
    <CartesianGrid stroke="var(--border)" vertical={false}/><XAxis dataKey="name" tick={{fill:"#a5bad0",fontSize:10}} interval={0} tickFormatter={name=>name === "Linear Regression" ? "Linear reg." : name === "Random Forest" ? "Random forest" : name}/><YAxis width={42} tick={{fill:"#a5bad0",fontSize:10}}/>
    <Tooltip content={({active,payload}) => active && payload?.length ? <div className="opt-tooltip"><strong>{payload[0].payload.name}</strong><p>MAE {formatMetric(payload[0].payload.mae)}</p><p>RMSE {formatMetric(payload[0].payload.rmse)}</p></div> : null}/><Legend wrapperStyle={{fontSize:11}}/><Bar dataKey="mae" name="MAE" fill="#168ef1" radius={[3,3,0,0]} isAnimationActive={false}/><Bar dataKey="rmse" name="RMSE" fill="#44d8b0" radius={[3,3,0,0]} isAnimationActive={false}/>
  </BarChart></ResponsiveContainer></div>;
}
