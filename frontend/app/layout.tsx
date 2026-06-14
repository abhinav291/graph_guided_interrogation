import type { Metadata } from "next";
import LlmDisclaimer from "@/components/LlmDisclaimer";
import "./globals.css";

export const metadata: Metadata = {
  title: "Socratic Graph Learning",
  description: "Multi-layered Socratic graph learning platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col">
        <div className="flex min-h-0 flex-1 flex-col">{children}</div>
        <LlmDisclaimer />
      </body>
    </html>
  );
}
