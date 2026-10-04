import { navigation } from "@/config/navigation";
import { NavLink } from "./nav-link";
export function Sidebar() {
  return <aside className="sidebar"><nav aria-label="Sidebar navigation">{navigation.map(({href, label, icon: Icon}) => <NavLink key={href} href={href} title={label} aria-label={label}><Icon size={19} aria-hidden="true" /><span className="sidebar-label">{label}</span></NavLink>)}</nav><p className="sidebar-caption">Solar farm optimization</p></aside>;
}
