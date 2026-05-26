import { Link, Outlet, useMatches } from "react-router-dom";

export default function Layout() {
  const matches = useMatches();
  const last = matches[matches.length - 1];
  const path = last?.pathname || "/";
  return (
    <div className="app-shell">
      <div className="topbar">
        <div className="row" style={{ gap: 18 }}>
          <h1>
            <Link to="/" style={{ color: "var(--text)" }}>
              CNC Image Converter
            </Link>
          </h1>
          <span className="crumbs">{path === "/" ? "" : path}</span>
        </div>
        <nav>
          <Link to="/">Gallery</Link>
          <Link to="/settings">Settings</Link>
        </nav>
      </div>
      <div className="main">
        <Outlet />
      </div>
    </div>
  );
}
