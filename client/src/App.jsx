import { BrowserRouter as Router, Routes, Route } from "react-router-dom"
import Navbar from "./components/Navbar"
import Dashboard from "./pages/Dashboard"
import JobRoles from "./pages/JobRoles"
import ResumeUpload from "./pages/ResumeUpload"
import Results from "./pages/Results"
import "./App.css"

function App() {
  return (
    <Router>
      <div className="app">
        <Navbar />
        <div className="container">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/job-roles" element={<JobRoles />} />
            <Route path="/upload" element={<ResumeUpload />} />
            <Route path="/results" element={<Results />} />
          </Routes>
        </div>
      </div>
    </Router>
  )
}

export default App

