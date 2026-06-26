import { DripIcon } from "@/components/icons";
import RecipesFlow from "@/components/RecipesFlow";

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

      <RecipesFlow />
    </>
  );
}
