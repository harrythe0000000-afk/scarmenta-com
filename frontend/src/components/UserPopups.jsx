import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { api, API } from "@/lib/api";

export const POPUP_SEEN_KEY = "scarmenta_popups_seen";
export const resetPopupSession = () => sessionStorage.removeItem(POPUP_SEEN_KEY);
const seen = () => JSON.parse(sessionStorage.getItem(POPUP_SEEN_KEY) || "[]");

export const bannerImg = (id) => `${API}/banners/image/${id}`;

export const BannerCard = ({ b, onButton }) => (
  <div data-testid="popup-banner-card">
    {b.image_id && <img src={bannerImg(b.image_id)} alt={b.title} data-testid="popup-banner-image" className="max-h-72 w-full rounded-xl object-cover" />}
    <h2 className="mt-4 font-display text-xl font-bold text-white" data-testid="popup-banner-title">{b.title}</h2>
    {b.text && <p className="mt-2 whitespace-pre-line text-sm text-slate-300" data-testid="popup-banner-text">{b.text}</p>}
    {b.button_label && (
      <Button data-testid="popup-banner-button" onClick={onButton} className="mt-5 w-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 font-semibold">
        {b.button_label}
      </Button>
    )}
  </div>
);

export const UserPopups = () => {
  const [queue, setQueue] = useState([]);
  const navigate = useNavigate();
  useEffect(() => {
    api.get("/banners/active").then((r) => {
      const s = seen();
      setQueue(r.data.filter((b) => !s.includes(b.id)));
    }).catch(() => {});
  }, []);
  const current = queue[0];
  const close = () => {
    sessionStorage.setItem(POPUP_SEEN_KEY, JSON.stringify([...seen(), current.id]));
    setQueue((q) => q.slice(1));
  };
  const go = () => {
    const url = current.button_url;
    close();
    if (url.startsWith("/")) navigate(url);
    else window.open(url, "_blank", "noopener");
  };
  if (!current) return null;
  return (
    <Dialog open onOpenChange={(o) => !o && close()}>
      <DialogContent key={current.id} data-testid="popup-banner-dialog" className="max-w-md border-purple-500/20 bg-[#0b0816] text-slate-200">
        <DialogTitle className="sr-only">{current.title}</DialogTitle>
        <DialogDescription className="sr-only">Announcement</DialogDescription>
        <BannerCard b={current} onButton={go} />
      </DialogContent>
    </Dialog>
  );
};
