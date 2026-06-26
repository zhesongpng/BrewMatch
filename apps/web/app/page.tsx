import Link from "next/link";
import { BookIcon, CupIcon, DripIcon } from "@/components/icons";

export default function HomePage() {
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
        <section className="hub-lead">
          <h2 className="scr">What are you up to?</h2>
          <p className="sub">
            Starting fresh or fixing a cup — pick where you are and BrewMatch
            takes it from there.
          </p>
        </section>

        <Link href="/recipes" className="choice primary">
          <span className="ic">
            <BookIcon />
          </span>
          <span className="ct">
            <span className="cs">Brewing new beans?</span>
            <span className="cm">Get a recipe</span>
          </span>
          <span className="chev">›</span>
        </Link>

        <Link href="/diagnose" className="choice">
          <span className="ic">
            <CupIcon />
          </span>
          <span className="ct">
            <span className="cs">Last brew tasted off?</span>
            <span className="cm">Fix it</span>
          </span>
          <span className="chev">›</span>
        </Link>
      </main>
    </>
  );
}
