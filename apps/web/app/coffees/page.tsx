import { BeanIcon, DripIcon } from "@/components/icons";

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
        <div className="empty">
          <span className="icn">
            <BeanIcon />
          </span>
          <h3>No bags yet</h3>
          <p>
            This is where every open bag will live, with how much is left and
            what&apos;s running low. Adding bags comes in the next build.
          </p>
        </div>
      </main>
    </>
  );
}
