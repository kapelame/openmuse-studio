import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OpenMuse Studio",
  description: "An open-source AI music workspace.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
