import { Dashboard } from "@/components/Dashboard";

export default async function Banca({ params }: PageProps<"/banca/[slug]">) {
  const { slug } = await params;
  return <Dashboard slug={slug} />;
}
