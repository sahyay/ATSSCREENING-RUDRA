"use client"

import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import "./ResumeUpload.css"

const ResumeUpload = () => {
  const [jobs, setJobs] = useState([])
  const [selectedJob, setSelectedJob] = useState("")
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [jobsLoading, setJobsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [dragActive, setDragActive] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    fetchJobs()
  }, [])

  const fetchJobs = async () => {
    try {
      const response = await fetch("http://localhost:5000/api/jobs")
      if (!response.ok) {
        throw new Error("Failed to fetch job roles")
      }
      const data = await response.json()
      setJobs(data.jobs || [])
      setJobsLoading(false)
    } catch (err) {
      console.error("Error fetching jobs:", err)
      setError("Failed to load job roles. Please try again later.")
      setJobsLoading(false)
    }
  }

  const handleFileChange = (e) => {
    const selectedFiles = Array.from(e.target.files)
    if (selectedFiles.length > 0) {
      // Filter for only PDF and DOCX files
      const validFiles = selectedFiles.filter(
        (file) =>
          file.type === "application/pdf" ||
          file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      )

      if (validFiles.length !== selectedFiles.length) {
        setError("Some files were not added. Only PDF and DOCX files are supported.")
        setTimeout(() => setError(null), 5000)
      }

      setFiles((prevFiles) => [...prevFiles, ...validFiles])
    }
  }

  const handleJobChange = (e) => {
    setSelectedJob(e.target.value)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!selectedJob) {
      setError("Please select a job role")
      return
    }

    if (files.length === 0) {
      setError("Please select at least one resume file")
      return
    }

    setLoading(true)
    setError(null)

    const formData = new FormData()
    formData.append("jobId", selectedJob)

    files.forEach((file) => {
      formData.append("resumes", file)
    })

    try {
      // Create a simulated progress update
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval)
            return 90
          }
          return prev + 5
        })
      }, 300)

      const response = await fetch("http://localhost:5000/api/upload", {
        method: "POST",
        body: formData,
      })

      clearInterval(progressInterval)
      setUploadProgress(100)

      if (!response.ok) {
        throw new Error("Failed to upload resumes")
      }

      const data = await response.json()

      // Navigate to results page with the batch ID
      setTimeout(() => {
        navigate(`/results?batch=${data.batchId}`)
      }, 500)
    } catch (err) {
      console.error("Error uploading resumes:", err)
      setError("Failed to upload resumes. Please try again.")
      setLoading(false)
      setUploadProgress(0)
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    const droppedFiles = Array.from(e.dataTransfer.files).filter(
      (file) =>
        file.type === "application/pdf" ||
        file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    if (droppedFiles.length > 0) {
      setFiles((prevFiles) => [...prevFiles, ...droppedFiles])
    } else {
      setError("Only PDF and DOCX files are supported.")
      setTimeout(() => setError(null), 5000)
    }
  }

  const removeFile = (index) => {
    setFiles((prevFiles) => prevFiles.filter((_, i) => i !== index))
  }

  if (jobsLoading) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
      </div>
    )
  }

  return (
    <div className="resume-upload">
      <h1>Upload Resumes</h1>

      {error && <div className="alert alert-danger">{error}</div>}

      {jobs.length === 0 ? (
        <div className="card">
          <p className="no-data">No job roles available. Please add a job role first.</p>
          <div className="text-center mt-3">
            <button className="btn" onClick={() => navigate("/job-roles")}>
              Add Job Role
            </button>
          </div>
        </div>
      ) : (
        <div className="card">
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="jobRole" className="form-label">
                Select Job Role*
              </label>
              <select
                id="jobRole"
                className="form-control"
                value={selectedJob}
                onChange={handleJobChange}
                required
                disabled={loading}
              >
                <option value="">-- Select a job role --</option>
                {jobs.map((job) => (
                  <option key={job._id} value={job._id}>
                    {job.title} - {job.department}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Upload Resumes* (PDF or DOCX)</label>
              <div
                className={`file-drop-area ${dragActive ? "active" : ""}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <div className="file-drop-content">
                  <div className="upload-icon">📄</div>
                  <p>Drag & drop resume files here or click to browse</p>
                  <p className="file-info">Accepted formats: PDF, DOCX</p>
                  <input
                    type="file"
                    id="resumeFiles"
                    className="file-input"
                    onChange={handleFileChange}
                    accept=".pdf,.docx"
                    multiple
                    disabled={loading}
                  />
                  <button
                    type="button"
                    className="btn browse-btn"
                    onClick={() => document.getElementById("resumeFiles").click()}
                    disabled={loading}
                  >
                    Browse Files
                  </button>
                </div>
              </div>
            </div>

            {files.length > 0 && (
              <div className="selected-files">
                <h3>Selected Files ({files.length})</h3>
                <ul className="file-list">
                  {files.map((file, index) => (
                    <li key={index} className="file-item">
                      <span className="file-name">{file.name}</span>
                      <span className="file-size">{(file.size / 1024).toFixed(1)} KB</span>
                      <button
                        type="button"
                        className="remove-file-btn"
                        onClick={() => removeFile(index)}
                        disabled={loading}
                      >
                        ✕
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {loading && (
              <div className="upload-progress">
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${uploadProgress}%` }}></div>
                </div>
                <p className="progress-text">Uploading and processing resumes... {uploadProgress}%</p>
              </div>
            )}

            <div className="form-actions">
              <button type="submit" className="btn" disabled={loading || files.length === 0 || !selectedJob}>
                {loading ? "Processing..." : "Upload & Process Resumes"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

export default ResumeUpload

