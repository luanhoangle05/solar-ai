import { navigation } from "@/config/navigation";
import { NavLink } from "./nav-link";
export function PrimaryNav() {
  return <nav aria-label="Primary navigation" className="primary-nav">{navigation.filter(item => item.primary).map(({href, label, icon: Icon}) => <NavLink key={href} href={href}><Icon size={16} aria-hidden="true" /><span>{label}</span></NavLink>)}</nav>;
}
