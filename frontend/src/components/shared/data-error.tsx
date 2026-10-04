import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
export function DataError({ message, details }: { message: string; details?: string }) {
  return <Card role="alert" className="border-danger/40"><CardHeader><CardTitle className="text-danger">Unable to load SolarAI data</CardTitle></CardHeader><CardContent><p className="text-sm">{message}</p>{process.env.NODE_ENV === "development" && details && <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words text-xs text-muted-foreground">{details}</pre>}</CardContent></Card>;
}
