import { TipsPage } from "@/components/TipsPage";

export const metadata = { title: "Tips — Bet Board" };

export default async function Tips({ params }: PageProps<"/banca/[slug]/tips">) {
  const { slug } = await params;
  return <TipsPage slug={slug} />;
}
