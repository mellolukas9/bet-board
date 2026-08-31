import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PublicBankrollPage } from "@/components/PublicBankrollPage";
import { ApiError, getPublicBankroll } from "@/lib/api";
import { formatPercent, formatUnitsSigned } from "@/lib/bets";
import type { PublicBankroll } from "@/types/api";

// Os resultados mudam a cada tip marcada; cachear a página entregaria número
// velho para quem abre o link logo depois de um green.
export const dynamic = "force-dynamic";

async function buscar(slug: string): Promise<PublicBankroll | null> {
  try {
    return await getPublicBankroll(slug);
  } catch (e) {
    // 404 é banca inexistente **ou** banca privada — a rota pública não
    // distingue os dois de propósito
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function generateMetadata({
  params,
}: PageProps<"/b/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const banca = await buscar(slug);

  if (banca === null) return { title: "Banca não encontrada" };

  // o link é compartilhado em grupo de mensagem: a prévia já mostra o resultado
  const resumo = `${formatUnitsSigned(banca.stats.profit_units)} · ROI ${formatPercent(
    banca.stats.roi,
  )} · ${banca.stats.bets} apostas`;

  return {
    title: `${banca.name} — resultados`,
    description: banca.description ?? resumo,
    openGraph: { title: banca.name, description: resumo },
  };
}

export default async function Publica({ params }: PageProps<"/b/[slug]">) {
  const { slug } = await params;
  const banca = await buscar(slug);

  if (banca === null) notFound();

  return <PublicBankrollPage banca={banca} />;
}
