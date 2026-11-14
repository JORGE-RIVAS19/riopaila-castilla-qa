import { useCallback, useState } from "react";

/** Paneles plegables que el navegador recuerda (preferencia de cada persona; si no hay storage, solo en memoria). */
export function usePanel(nombre: string, abiertoPorDefecto: boolean): [boolean, () => void] {
  const key = `riopaila.panel.${nombre}`;
  const [abierto, setAbierto] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem(key);
      return v === null ? abiertoPorDefecto : v === "1";
    } catch {
      return abiertoPorDefecto;
    }
  });
  const alternar = useCallback(() => {
    setAbierto((a) => {
      try {
        localStorage.setItem(key, a ? "0" : "1");
      } catch {
        /* sin almacenamiento: queda solo en memoria */
      }
      return !a;
    });
  }, [key]);
  return [abierto, alternar];
}
