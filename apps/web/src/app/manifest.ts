import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Consensus Signal Research",
    short_name: "Consensus",
    description: "Coverage-aware stock search, rankings, and chart research for US and Korea.",
    start_url: "/app/rankings",
    display: "standalone",
    background_color: "#0f1218",
    theme_color: "#d4a951",
    icons: [
      {
        src: "/favicon.ico",
        sizes: "48x48",
        type: "image/x-icon",
      },
    ],
  };
}
