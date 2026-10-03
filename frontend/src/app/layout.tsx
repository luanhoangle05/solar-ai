import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "SolarAI",
  description: "AI-Powered Solar Farm Optimization",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
