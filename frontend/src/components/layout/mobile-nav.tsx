"use client";
import { useEffect, useRef, useState } from "react";
import { Menu, X } from "lucide-react";
import { navigation } from "@/config/navigation";
import { NavLink } from "./nav-link";
import { Button } from "@/components/ui/button";
export function MobileNav() {
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  function close() { dialog.current?.close(); }
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const media = window.matchMedia("(min-width: 768px)");
    const onResize = () => { if (media.matches) dialog.current?.close(); };
    media.addEventListener("change", onResize);
    return () => { document.body.style.overflow = previous; media.removeEventListener("change", onResize); };
  }, [open]);
  return <div className="mobile-navigation">
    <Button ref={trigger} variant="secondary" size="icon" aria-label="Open navigation" aria-expanded={open} aria-controls="mobile-navigation" onClick={() => { dialog.current?.showModal(); setOpen(true); }}><Menu size={20} /></Button>
    <dialog ref={dialog} id="mobile-navigation" className="mobile-drawer" aria-labelledby="navigation-title" onClose={() => { setOpen(false); trigger.current?.focus(); }} onClick={event => { if (event.target === event.currentTarget) close(); }}>
      <div className="drawer-content"><div className="flex items-center justify-between border-b border-border pb-4"><h2 id="navigation-title" className="text-lg font-semibold">SolarAI navigation</h2><Button autoFocus variant="secondary" size="icon" aria-label="Close navigation" onClick={close}><X size={20} /></Button></div>
      <nav aria-label="Mobile navigation" className="mt-4">{navigation.map(({href,label,icon: Icon}) => <NavLink key={href} href={href} onClick={close}><Icon size={19} aria-hidden="true" />{label}</NavLink>)}</nav></div>
    </dialog>
  </div>;
}
