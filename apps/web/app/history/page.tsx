import { ChartIcon, DripIcon } from "@/components/icons";

export default function HistoryPage() {
  return (
    <>
      <header className="topbar">
        <div className="title">Your coffee</div>
        <div className="brand">
          <DripIcon />
          BrewMatch
        </div>
      </header>

      <main className="app-body">
        <div className="empty">
          <span className="icn">
            <ChartIcon />
          </span>
          <h3>Your history starts here</h3>
          <p>
            Every brew you log will show up here, newest first — along with what
            BrewMatch has learned about your taste. Brew logging comes next.
          </p>
        </div>
      </main>
    </>
  );
}
