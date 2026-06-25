import Link from "next/link";
import {
  AstringentIcon,
  BitterIcon,
  BookIcon,
  DripIcon,
  PourOverIcon,
  SourIcon,
  WeakIcon,
} from "@/components/icons";

const FLAGS = [
  { Icon: SourIcon, title: "Too sour", desc: "Sharp, tangy, empty finish" },
  { Icon: BitterIcon, title: "Too bitter", desc: "Harsh, drying aftertaste" },
  { Icon: WeakIcon, title: "Too weak", desc: "Watery, thin, not enough" },
  { Icon: AstringentIcon, title: "Astringent", desc: "Mouth-puckering, dry" },
];

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

        <section className="card">
          <div className="eyebrow">How did it taste?</div>
          <h2 className="scr">What went wrong?</h2>
          <p className="sub">
            Tap what you noticed. We&apos;ll tell you why — and exactly what to
            change next time.
          </p>

          {FLAGS.map(({ Icon, title, desc }) => (
            <div className="flag" key={title}>
              <div className="dot">
                <Icon />
              </div>
              <div>
                <div className="t">{title}</div>
                <div className="d">{desc}</div>
              </div>
              <div className="chev">›</div>
            </div>
          ))}
        </section>

        <Link href="/recipes" className="btn ghost">
          <BookIcon />
          Get a recipe for new beans
        </Link>
      </main>
    </>
  );
}
