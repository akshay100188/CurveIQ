import "./globals.css";
import Link from "next/link";

export const metadata = {
  title: "CurveIQ — yield-curve analytics",
  description:
    "Descriptive, retrospective yield-curve analytics over US and Indian government rates.",
};

function Nav() {
  return (
    <header className="border-b border-edge/60">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="font-semibold tracking-tight">
          Curve<span className="text-accent">IQ</span>
        </Link>
        <nav className="flex gap-6 text-sm text-muted">
          <Link href="/us" className="hover:text-white">US</Link>
          <Link href="/in" className="hover:text-white">India</Link>
          <a
            href="https://github.com/akshay100188/CurveIQ"
            className="hover:text-white"
          >
            About
          </a>
        </nav>
      </div>
    </header>
  );
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
        <footer className="mx-auto max-w-6xl px-6 py-10 text-xs text-muted">
          Descriptive and retrospective only — never advice or a forecast. Data:
          FRED, OECD, RBI, NSE, S&amp;P (see provenance per series).
        </footer>
      </body>
    </html>
  );
}
