import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Bet Board",
  description: "Painel de administração de grupos de tips esportivas",
};

/**
 * O painel é operado do celular — o link da aposta na Bet365 só existe lá.
 *
 * A `themeColor` pinta a barra do navegador da mesma cor do topo da tela; sem
 * ela o Chrome do Android desenha uma faixa clara em cima de um painel escuro.
 */
export const viewport: Viewport = {
  themeColor: "#0d1322",
  colorScheme: "dark",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="pt-BR"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full">{children}</body>
    </html>
  );
}
