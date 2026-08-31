import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /**
   * `standalone` empacota o servidor e só as dependências realmente usadas —
   * é o que o `frontend/Dockerfile` copia para a imagem enxuta.
   *
   * Na Vercel ele é desligado: lá a função serverless é montada a partir do
   * rastreamento de dependências (`.next/*.nft.json`), e o `standalone` só
   * atrapalha esse empacotamento. Foi o que quebrou o build com
   * "ENOENT: .next/next-server.js.nft.json" no `onBuildComplete`.
   *
   * `VERCEL` é definida por ela em todo build.
   */
  output: process.env.VERCEL ? undefined : "standalone",
};

export default nextConfig;
