import { BookIcon, DripIcon } from "@/components/icons";

export default function RecipesPage() {
  return (
    <>
      <header className="topbar">
        <div className="title">Recipes</div>
        <div className="brand">
          <DripIcon />
          BrewMatch
        </div>
      </header>

      <main className="app-body">
        <div className="empty">
          <span className="icn">
            <BookIcon />
          </span>
          <h3>Recipes are on the way</h3>
          <p>
            Soon this screen will rank pour-over recipes for your beans and
            taste — pulled live from the BrewMatch brain.
          </p>
        </div>
      </main>
    </>
  );
}
