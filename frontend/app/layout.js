import "./globals.css";
import Link from "next/link";
import { ThemeProvider, ThemeToggle } from "@/components/Theme";

export const metadata = {
  title: "CurveIQ — yield-curve analytics",
  description:
    "Descriptive, retrospective yield-curve analytics over US and Indian government rates.",
};

// Set the dark class before paint for returning dark users (default is light).
const NO_FOUC = `try{if(localStorage.getItem('theme')==='dark')document.documentElement.classList.add('dark')}catch(e){}`;

function Nav() {
  return (
    <header className="border-b border-edge/60">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="font-semibold tracking-tight">
          Curve<span className="text-accent">IQ</span>
        </Link>
        <nav className="flex items-center gap-6 text-sm text-muted">
          <Link href="/us" className="hover:text-fg">US</Link>
          <Link href="/in" className="hover:text-fg">India</Link>
          <Link href="/calculator" className="hover:text-fg">Calculator</Link>
          <a href="https://github.com/akshay100188/CurveIQ" className="hover:text-fg">About</a>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <script dangerouslySetInnerHTML={{ __html: NO_FOUC }} />
        <ThemeProvider>
          <Nav />
          <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
          <footer className="mx-auto max-w-6xl px-6 py-10 text-xs text-muted">
            Descriptive and retrospective only — never advice or a forecast. Data:
            FRED, OECD, RBI, NSE, S&amp;P (see provenance per series).
          </footer>
        </ThemeProvider>
      </body>
    </html>
  );
}
