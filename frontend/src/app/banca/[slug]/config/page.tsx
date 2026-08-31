import { ConfigPage } from "@/components/ConfigPage";

export const metadata = { title: "Configurações — Bet Board" };

export default async function Config({ params }: PageProps<"/banca/[slug]/config">) {
  const { slug } = await params;
  return <ConfigPage slug={slug} />;
}
