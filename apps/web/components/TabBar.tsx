"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BeanIcon, BookIcon, ChartIcon, HomeIcon } from "./icons";

const TABS = [
  { href: "/", label: "Home", Icon: HomeIcon },
  { href: "/recipes", label: "Recipes", Icon: BookIcon },
  { href: "/coffees", label: "Coffees", Icon: BeanIcon },
  { href: "/history", label: "History", Icon: ChartIcon },
] as const;

export default function TabBar() {
  const pathname = usePathname();

  return (
    <nav className="tabbar">
      {TABS.map(({ href, label, Icon }) => {
        const active =
          href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link key={href} href={href} className={active ? "on" : undefined}>
            <Icon />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
