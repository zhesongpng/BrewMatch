import { DripIcon } from "@/components/icons";
import SignInFlow from "@/components/SignInFlow";

export default function SignInPage() {
  return (
    <>
      <header className="topbar">
        <div className="title">Sign in</div>
        <div className="brand">
          <DripIcon />
          BrewMatch
        </div>
      </header>

      <main className="app-body">
        <SignInFlow />
      </main>
    </>
  );
}
