import Link from "next/link";
import { DripIcon, PourOverIcon } from "@/components/icons";
import DiagnoseFlags from "@/components/DiagnoseFlags";

export default function DiagnosePage() {
  return (
    <>
      <header className="topbar">
        <Link href="/" className="back" aria-label="Back to home">
          ‹
        </Link>
        <div className="title">Fix a brew</div>
        <div className="brand">
          <DripIcon />
          BrewMatch
        </div>
      </header>

      <main className="app-body">
        <div className="hero-art">
          <PourOverIcon />
        </div>

        <DiagnoseFlags />
      </main>
    </>
  );
}
