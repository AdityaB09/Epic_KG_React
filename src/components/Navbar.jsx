export default function Navbar({
  searchValue,
  onSearchChange,
  onSearchFocus,
  onToggleSidebar,
  alertCount = 0,
  activePage,
  onPageChange
}) {
  return (
    <header className="navbar">
      <div className="nav-left">
        <button className="icon-btn" onClick={onToggleSidebar} aria-label="Toggle patient directory">
          ☰
        </button>

        <label className="global-search">
          <span>⌕</span>
          <input
            value={searchValue}
            onFocus={onSearchFocus}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search patients, appointments etc"
          />
          <kbd>⌘K</kbd>
        </label>
      </div>

    <nav className="nav-links" aria-label="Main navigation">
  <button
    className={activePage === "physiology" ? "active" : ""}
    onClick={() => onPageChange("physiology")}
  >
    Dashboard
  </button>

  <button
    className={activePage === "dashboard" ? "active" : ""}
    onClick={() => onPageChange("dashboard")}
  >
    Patient Home
  </button>

  <button
    className={activePage === "monitor" ? "active" : ""}
    onClick={() => onPageChange("monitor")}
  >
    Multi Monitor
  </button>

  <button>Team</button>
  <button>Calendar</button>
</nav>

      <div className="nav-profile">
        <button className="icon-btn notification-btn" aria-label="Notifications">
          ♡
          {alertCount > 0 && <span className="alert-badge">{alertCount}</span>}
        </button>

        <div className="doctor-avatar">DC</div>

        <div className="doctor-meta">
          <strong>Dr Cook</strong>
          <span>Staff Admin</span>
        </div>

        <span>⌄</span>
      </div>
    </header>
  );
}