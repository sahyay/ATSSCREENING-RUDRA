"use client"

import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import "./Dashboard.css"

const Dashboard = () => {
  const [stats, setStats] = useState({
    totalJobs: 0,
    totalResumes: 0,
    processedResumes: 0,
    averageScore: 0,
  })
  const [recentJobs, setRecentJobs] = useState([])
  const [recentResults, setRecentResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const statsResponse = await fetch("http://localhost:5000/api/stats")
        const jobsResponse = await fetch("http://localhost:5000/api/jobs?limit=5")
        const resultsResponse = await fetch("http://localhost:5000/api/results?limit=5")

        if (!statsResponse.ok || !jobsResponse.ok || !resultsResponse.ok) {
          throw new Error("Failed to fetch dashboard data")
        }

        const statsData = await statsResponse.json()
        const jobsData = await jobsResponse.json()
        const resultsData = await resultsResponse.json()

        setStats(statsData)
        setRecentJobs(jobsData.jobs || [])
        setRecentResults(resultsData.results || [])
        setLoading(false)
      } catch (err) {
        console.error("Error fetching dashboard data:", err)
        setError("Failed to load dashboard data. Please try again later.")
        setLoading(false)
      }
    }

    fetchDashboardData()
  }, [])

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="dashboard">
        <div className="alert alert-danger">{error}</div>
        <div className="card">
          <h2>Welcome to ATS Resume Screening System</h2>
          <p>This system helps you manage job roles and screen resumes efficiently.</p>
          <div className="dashboard-actions">
            <Link to="/job-roles" className="btn">
              Manage Job Roles
            </Link>
            <Link to="/upload" className="btn">
              Upload Resumes
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard">
      <h1>Dashboard</h1>

      <div className="stats-container">
        <div className="stat-card">
          <h3>Job Roles</h3>
          <p className="stat-value">{stats.totalJobs}</p>
          <Link to="/job-roles" className="stat-link">
            View All
          </Link>
        </div>
        <div className="stat-card">
          <h3>Total Resumes</h3>
          <p className="stat-value">{stats.totalResumes}</p>
          <Link to="/results" className="stat-link">
            View All
          </Link>
        </div>
        <div className="stat-card">
          <h3>Processed</h3>
          <p className="stat-value">{stats.processedResumes}</p>
        </div>
        <div className="stat-card">
          <h3>Avg. Score</h3>
          <p className="stat-value">{stats.averageScore.toFixed(1)}</p>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="card">
          <div className="card-header">
            <h2>Recent Job Roles</h2>
            <Link to="/job-roles" className="view-all">
              View All
            </Link>
          </div>
          {recentJobs.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Department</th>
                  <th>Date Added</th>
                </tr>
              </thead>
              <tbody>
                {recentJobs.map((job) => (
                  <tr key={job._id}>
                    <td>{job.title}</td>
                    <td>{job.department}</td>
                    <td>{new Date(job.createdAt).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="no-data">No job roles added yet.</p>
          )}
          <div className="card-footer">
            <Link to="/job-roles" className="btn">
              Add New Job Role
            </Link>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h2>Recent Results</h2>
            <Link to="/results" className="view-all">
              View All
            </Link>
          </div>
          {recentResults.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Job Role</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                {recentResults.map((result) => (
                  <tr key={result._id}>
                    <td>{result.name}</td>
                    <td>{result.jobTitle}</td>
                    <td>
                      <span
                        className={`score-badge ${
                          result.score >= 70 ? "score-high" : result.score >= 40 ? "score-medium" : "score-low"
                        }`}
                      >
                        {result.score}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="no-data">No resume results yet.</p>
          )}
          <div className="card-footer">
            <Link to="/upload" className="btn">
              Upload Resumes
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard

