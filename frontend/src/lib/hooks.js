import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function useConfig() {
  const [config, setConfig] = useState(null);
  useEffect(() => {
    api.get("/public/config").then((r) => setConfig(r.data)).catch(() => {});
  }, []);
  return config;
}

export function useFetch(url, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get(url);
      setData(r.data);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, ...deps]);
  return { data, loading, reload: load, setData };
}
