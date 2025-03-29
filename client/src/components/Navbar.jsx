import { Link, useLocation } from "react-router-dom"
import "./Navbar.css"

const Navbar = () => {
  const location = useLocation()

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <Link to="/" className="navbar-logo">
          ATS Resume Screening
        </Link>
        <ul className="nav-menu">
          <li className="nav-item">
            <Link to="/" className={`nav-link ${location.pathname === "/" ? "active" : ""}`}>
              Dashboard
            </Link>
          </li>
          <li className="nav-item">
            <Link to="/job-roles" className={`nav-link ${location.pathname === "/job-roles" ? "active" : ""}`}>
              Job Roles
            </Link>
          </li>
          <li className="nav-item">
            <Link to="/upload" className={`nav-link ${location.pathname === "/upload" ? "active" : ""}`}>
              Upload Resumes
            </Link>
          </li>
          <li className="nav-item">
            <Link to="/results" className={`nav-link ${location.pathname === "/results" ? "active" : ""}`}>
              Results
            </Link>
          </li>
        </ul>
      </div>
    </nav>
  )
}

export default Navbar

