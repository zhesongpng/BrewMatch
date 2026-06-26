import Link from "next/link";
import { BookIcon, DripIcon, PourOverIcon } from "@/components/icons";
import DiagnoseFlags from "@/components/DiagnoseFlags";

export default function DiagnosePage() {
  return (
    <>
      <header className="topbar">
        <div className="title">Good morning</div>
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

        <Link href="/recipes" className="btn ghost">
          <BookIcon />
          Get a recipe for new beans
        </Link>
      </main>
    </>
  );
}
