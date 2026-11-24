import { describe, expect, it } from "vitest";
import { mediaDelMensaje } from "../components/MediaGallery";
import type { ChatMessage } from "../types";

describe("mediaDelMensaje", () => {
  it("junta las imágenes y PDF de las herramientas sin repetir", () => {
    const m: ChatMessage = {
      id: "a",
      role: "assistant",
      content: "",
      tools: [
        { id: "1", name: "buscar_manual", args: {}, status: "success", artifact: { media: [{ tipo: "imagen", url: "/media/manuales/p1.png", pie: "pág. 1" }] } },
        { id: "2", name: "generar_informe_pdf", args: {}, status: "success", artifact: { media: [{ tipo: "documento", url: "/media/informes/i.pdf", pie: "Informe" }, { tipo: "imagen", url: "/media/manuales/p1.png", pie: "pág. 1" }] } },
        { id: "3", name: "buscar_documentos", args: {}, status: "success", artifact: { hits: [] } },
      ],
    };
    expect(mediaDelMensaje(m).map((x) => x.url)).toEqual(["/media/manuales/p1.png", "/media/informes/i.pdf"]);
  });
});
