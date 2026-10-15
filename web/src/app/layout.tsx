import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Script from "next/script";

import { SiteHeader } from "@/components/site-header";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Tennis Edge",
  description:
    "Can a model beat the tennis betting market? Elo, a point-level Markov model and LightGBM, tested honestly against bookmaker odds.",
};

// Runs before paint so the saved theme (or the OS setting) applies without a flash.
const themeScript = `(function(){try{var t=localStorage.getItem("theme");var d=t?t==="dark":matchMedia("(prefers-color-scheme: dark)").matches;document.documentElement.classList.toggle("dark",d);}catch(e){document.documentElement.classList.add("dark");}})();`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <Script id="theme" strategy="beforeInteractive">{themeScript}</Script>
        <TooltipProvider delay={150}>
          <SiteHeader />
          <main className="flex-1">{children}</main>
          <footer className="border-t mt-24">
            <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8 text-sm text-muted-foreground flex flex-col sm:flex-row gap-2 justify-between">
              <p>
                Built by Sammy Cohen ·{" "}
                <a className="underline underline-offset-4 hover:text-foreground" href="https://github.com/sammydcohen/tennis-edge">
                  Source on GitHub
                </a>
              </p>
              <p>
                Match data: Jeff Sackmann (CC BY-NC-SA) · Odds: tennis-data.co.uk, Kaggle, Flashscore ·
                For analysis only
              </p>
            </div>
          </footer>
        </TooltipProvider>
      </body>
    </html>
  );
}
