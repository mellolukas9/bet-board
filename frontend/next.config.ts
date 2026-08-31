import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // imagem Docker enxuta: só o servidor e as dependências realmente usadas
  output: "standalone",
};

export default nextConfig;
