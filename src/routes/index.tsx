import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Sticker Magique — Bot Telegram" },
      { name: "description", content: "Bot Telegram français pour créer des stickers, les exporter vers WhatsApp et générer des thèmes Android à partir de photos." },
      { property: "og:title", content: "Sticker Magique — Bot Telegram" },
      { property: "og:description", content: "Création de stickers, export WhatsApp et thèmes Telegram Android assortis à vos photos." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Index,
});

// IMPORTANT: Replace this placeholder. See ./README.md for routing conventions.
function Index() {
  return (
    <div
      className="flex min-h-screen items-center justify-center"
      style={{ backgroundColor: "#fcfbf8" }}
    >
      <img
        data-lovable-blank-page-placeholder="REMOVE_THIS"
        src="https://cdn.gpteng.co/blank-app-v1.svg"
        alt="Your app will live here!"
      />
    </div>
  );
}
