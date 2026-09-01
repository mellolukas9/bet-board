import { AppShell } from "@/components/AppShell";

/**
 * A moldura das três telas da banca, montada **uma vez**.
 *
 * Ela vive aqui, e não dentro de cada página, para sobreviver à navegação: como
 * `layout`, o Next a mantém montada ao trocar de seção. Antes cada tela trazia
 * a sua, e ir da Banca para Tips apagava a lateral e o topo para redesenhá-los
 * idênticos — de quebra, refazendo o `GET /auth/me` a cada clique.
 */
export default async function BancaLayout({
  params,
  children,
}: LayoutProps<"/banca/[slug]">) {
  const { slug } = await params;
  return <AppShell slug={slug}>{children}</AppShell>;
}
