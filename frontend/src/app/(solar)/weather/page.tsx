import { CloudSun } from "lucide-react";
import { FeaturePlaceholder } from "@/components/shared/feature-placeholder";
export const metadata = { title: "Weather | SolarAI" };
export default function Page() { return <FeaturePlaceholder icon={CloudSun} title="Weather" description="Inspect environmental inputs used by SolarAI." planned="Environmental input panels will be added in a future phase. Current contract-backed weather is available on the Dashboard." />; }
