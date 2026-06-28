import { DripIcon } from "@/components/icons";
import ProfileFlow from "@/components/ProfileFlow";

export default function ProfilePage() {
  return (
    <>
      <header className="topbar">
        <div className="title">Your profile</div>
        <div className="brand">
          <DripIcon />
          BrewMatch
        </div>
      </header>

      <main className="app-body">
        <ProfileFlow />
      </main>
    </>
  );
}
