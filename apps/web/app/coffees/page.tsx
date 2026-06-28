import { DripIcon } from "@/components/icons";
import CoffeesFlow from "@/components/CoffeesFlow";

export default function CoffeesPage() {
  return (
    <>
      <header className="topbar">
        <div className="title">Your coffees</div>
        <div className="brand">
          <DripIcon />
          BrewMatch
        </div>
      </header>

      <main className="app-body">
        <CoffeesFlow />
      </main>
    </>
  );
}
