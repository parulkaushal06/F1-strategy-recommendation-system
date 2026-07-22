import type { Metadata } from "next";
import { Big_Shoulders, IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const displayFont = Big_Shoulders({
  variable: "--font-display",
  weight: ["600", "700", "800", "900"],
  subsets: ["latin"],
});

const bodyFont = IBM_Plex_Sans({
  variable: "--font-body",
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
});

const monoFont = IBM_Plex_Mono({
  variable: "--font-mono",
  weight: ["400", "500", "600"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "RACECRAFT — F1 Strategy Dashboard",
  description: "Lap-by-lap win probability and strategy recommendations, built on historical F1 data.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${displayFont.variable} ${bodyFont.variable} ${monoFont.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col relative">{children}</body>
    </html>
  );
}
