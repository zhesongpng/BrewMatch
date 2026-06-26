import { DripIcon } from "@/components/icons";
import HistoryFlow from "@/components/HistoryFlow";

export default function HistoryPage() {
  return (
    <>
      <header className="topbar">
        <div className="title">Your history</div>
        <div className="brand">
          <DripIcon />
          BrewMatch
        </div>
      </header>

      <main className="app-body">
        <HistoryFlow />
      </main>
    </>
  );
}
