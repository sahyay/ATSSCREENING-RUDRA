"use client"

import { useState, useEffect, useCallback } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import "./Results.css"

const Results = () => {
  const [results, setResults] = useState([])
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedJob, setSelectedJob] = useState("all")
  const [sortBy, setSortBy] = useState("score")
  const [sortOrder, setSortOrder] = useState("desc")
  const [currentPage, setCurrentPage] = useState(1)
  const [resultsPerPage] = useState(10)
  const [searchTerm, setSearchTerm] = useState("")
  const [totalResults, setTotalResults] = useState(0)

  const location = useLocation()
  const navigate = useNavigate()
  const queryParams = new URLSearchParams(location.search)
  const batchId = queryParams.get("batch")

  // Use useCallback to memoize the fetchResults function
  const fetchResults = useCallback(async () => {
    setLoading(true)
    try {
      let url = `http://localhost:5000/api/results?page=${currentPage}&limit=${resultsPerPage}&sort=${sortBy}&order=${sortOrder}`

      if (batchId) {
        url += `&batch=${batchId}`
      }

      if (selectedJob !== "all") {
        url += `&job=${selectedJob}`
      }

      if (searchTerm) {
        url += `&search=${searchTerm}`
      }

      const response = await fetch(url)
      if (!response.ok) {
        throw new Error("Failed to fetch results")
      }

      const data = await response.json()
      setResults(data.results || [])
      setTotalResults(data.total || 0)
      setLoading(false)
    } catch (err) {
      console.error("Error fetching results:", err)
      setError("Failed to load results. Please try again later.")
      setLoading(false)
    }
  }, [batchId, currentPage, resultsPerPage, searchTerm, selectedJob, sortBy, sortOrder])

  // Use useCallback for fetchJobs as well for consistency
  const fetchJobs = useCallback(async () => {
    try {
      const response = await fetch("http://localhost:5000/api/jobs")
      if (!response.ok) {
        throw new Error("Failed to fetch job roles")
      }
      const data = await response.json()
      setJobs(data.jobs || [])
    } catch (err) {
      console.error("Error fetching jobs:", err)
      setError("Failed to load job roles")
    }
  }, [])

  useEffect(() => {
    fetchJobs()
    fetchResults()
  }, [fetchJobs, fetchResults]) // Now we can safely include these as dependencies

  const handleJobChange = (e) => {
    setSelectedJob(e.target.value)
    setCurrentPage(1)
  }

  const handleSortChange = (e) => {
    setSortBy(e.target.value)
    setCurrentPage(1)
  }

  const handleOrderChange = () => {
    setSortOrder(sortOrder === "asc" ? "desc" : "asc")
    setCurrentPage(1)
  }

  const handleSearch = (e) => {
    e.preventDefault()
    setCurrentPage(1)
  }

  const handleSearchInputChange = (e) => {
    setSearchTerm(e.target.value)
  }

  const handlePageChange = (pageNumber) => {
    setCurrentPage(pageNumber)
  }

  const getScoreClass = (score) => {
    if (score >= 70) return "score-high"
    if (score >= 40) return "score-medium"
    return "score-low"
  }

  const totalPages = Math.ceil(totalResults / resultsPerPage)
  const pageNumbers = []

  for (let i = 1; i <= totalPages; i++) {
    pageNumbers.push(i)
  }

  if (loading && results.length === 0) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
      </div>
    )
  }

  return (
    <div className="results-page">
      <h1>Resume Screening Results</h1>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="card filter-card">
        <div className="filters">
          <div className="filter-group">
            <label htmlFor="jobFilter" className="filter-label">
              Job Role
            </label>
            <select id="jobFilter" className="form-control" value={selectedJob} onChange={handleJobChange}>
              <option value="all">All Job Roles</option>
              {jobs.map((job) => (
                <option key={job._id} value={job._id}>
                  {job.title} - {job.department}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label htmlFor="sortBy" className="filter-label">
              Sort By
            </label>
            <select id="sortBy" className="form-control" value={sortBy} onChange={handleSortChange}>
              <option value="score">Score</option>
              <option value="name">Name</option>
              <option value="createdAt">Date</option>
            </select>
            <button
              className="btn-icon"
              onClick={handleOrderChange}
              title={sortOrder === "asc" ? "Ascending" : "Descending"}
            >
              {sortOrder === "asc" ? "↑" : "↓"}
            </button>
          </div>

          <div className="filter-group search-group">
            <form onSubmit={handleSearch}>
              <input
                type="text"
                className="form-control"
                placeholder="Search by name or email"
                value={searchTerm}
                onChange={handleSearchInputChange}
              />
              <button type="submit" className="btn">
                Search
              </button>
            </form>
          </div>
        </div>
      </div>

      {results.length === 0 ? (
        <div className="card">
          <p className="no-data">No results found. Try adjusting your filters or upload some resumes.</p>
          <div className="text-center mt-3">
            <button className="btn" onClick={() => navigate("/upload")}>
              Upload Resumes
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="results-count">
            Showing {results.length} of {totalResults} results
          </div>

          <div className="results-list">
            {results.map((result) => (
              <div key={result._id} className={`result-card ${result.score < 40 ? "rejected" : ""}`}>
                <div className="result-header">
                  <div className="result-name-section">
                    <h2 className="result-name">{result.name}</h2>
                    {result.email && (
                      <a href={`mailto:${result.email}`} className="result-email">
                        {result.email}
                      </a>
                    )}
                  </div>
                  <div className="result-score-section">
                    <div className={`score-badge ${getScoreClass(result.score)}`}>{result.score}</div>
                    <div className="score-label">ATS Score</div>
                  </div>
                </div>

                <div className="result-details">
                  <div className="result-info">
                    <div className="info-item">
                      <span className="info-label">Job Role:</span>
                      <span className="info-value">{result.jobTitle}</span>
                    </div>
                    {result.phone && (
                      <div className="info-item">
                        <span className="info-label">Phone:</span>
                        <span className="info-value">{result.phone}</span>
                      </div>
                    )}
                    {result.college && (
                      <div className="info-item">
                        <span className="info-label">Education:</span>
                        <span className="info-value">{result.college}</span>
                      </div>
                    )}
                    <div className="info-item">
                      <span className="info-label">Date:</span>
                      <span className="info-value">{new Date(result.createdAt).toLocaleDateString()}</span>
                    </div>
                  </div>

                  {result.skills && result.skills.length > 0 && (
                    <div className="result-skills">
                      <h3>Skills</h3>
                      <div className="skills-list">
                        {result.skills.map((skill, index) => (
                          <span
                            key={index}
                            className={`skill-tag ${result.matchedSkills && result.matchedSkills.includes(skill) ? "matched" : ""}`}
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {result.score < 40 && (
                    <div className="rejection-message">
                      <p>This resume doesn't match the job requirements well enough.</p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="pagination-container">
              <ul className="pagination">
                <li>
                  <button onClick={() => handlePageChange(1)} disabled={currentPage === 1}>
                    First
                  </button>
                </li>
                <li>
                  <button onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1}>
                    Prev
                  </button>
                </li>

                {pageNumbers.map((number) => (
                  <li key={number}>
                    <button className={currentPage === number ? "active" : ""} onClick={() => handlePageChange(number)}>
                      {number}
                    </button>
                  </li>
                ))}

                <li>
                  <button onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages}>
                    Next
                  </button>
                </li>
                <li>
                  <button onClick={() => handlePageChange(totalPages)} disabled={currentPage === totalPages}>
                    Last
                  </button>
                </li>
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default Results

