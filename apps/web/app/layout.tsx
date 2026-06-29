import type { Metadata, Viewport } from "next";
import "./globals.css";
import TabBar from "@/components/TabBar";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "BrewMatch",
  description:
    "Your pour-over brewing companion — diagnose a brew, get recipes tuned to your beans and taste, and learn as you go.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#fbf8f3",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <div className="app-shell">
            {children}
            <TabBar />
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
