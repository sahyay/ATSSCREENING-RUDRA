"use client"

import { useState, useEffect } from "react"
import "./JobRoles.css"

const JobRoles = () => {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    title: "",
    department: "",
    location: "",
    description: "",
    requirements: "",
    skills: "",
  })
  const [editingId, setEditingId] = useState(null)
  const [alert, setAlert] = useState({ show: false, type: "", message: "" })

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
      setLoading(false)
    } catch (err) {
      console.error("Error fetching jobs:", err)
      setError("Failed to load job roles. Please try again later.")
      setLoading(false)
    }
  }

  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData({
      ...formData,
      [name]: value,
    })
  }

  const resetForm = () => {
    setFormData({
      title: "",
      department: "",
      location: "",
      description: "",
      requirements: "",
      skills: "",
    })
    setEditingId(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    // Convert skills string to array
    const jobData = {
      ...formData,
      skills: formData.skills.split(",").map((skill) => skill.trim()),
    }

    try {
      const url = editingId ? `http://localhost:5000/api/jobs/${editingId}` : "http://localhost:5000/api/jobs"

      const method = editingId ? "PUT" : "POST"

      const response = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(jobData),
      })

      if (!response.ok) {
        throw new Error("Failed to save job role")
      }

      setAlert({
        show: true,
        type: "success",
        message: editingId ? "Job role updated successfully!" : "Job role added successfully!",
      })

      resetForm()
      setShowForm(false)
      fetchJobs()

      // Hide alert after 3 seconds
      setTimeout(() => {
        setAlert({ show: false, type: "", message: "" })
      }, 3000)
    } catch (err) {
      console.error("Error saving job:", err)
      setAlert({
        show: true,
        type: "danger",
        message: "Failed to save job role. Please try again.",
      })
    }
  }

  const handleEdit = (job) => {
    setFormData({
      title: job.title,
      department: job.department,
      location: job.location,
      description: job.description,
      requirements: job.requirements,
      skills: job.skills.join(", "),
    })
    setEditingId(job._id)
    setShowForm(true)
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this job role?")) {
      return
    }

    try {
      const response = await fetch(`http://localhost:5000/api/jobs/${id}`, {
        method: "DELETE",
      })

      if (!response.ok) {
        throw new Error("Failed to delete job role")
      }

      setAlert({
        show: true,
        type: "success",
        message: "Job role deleted successfully!",
      })

      fetchJobs()

      setTimeout(() => {
        setAlert({ show: false, type: "", message: "" })
      }, 3000)
    } catch (err) {
      console.error("Error deleting job:", err)
      setAlert({
        show: true,
        type: "danger",
        message: "Failed to delete job role. Please try again.",
      })
    }
  }

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
      </div>
    )
  }

  return (
    <div className="job-roles">
      <div className="page-header">
        <h1>Job Roles</h1>
        <button
          className="btn"
          onClick={() => {
            resetForm()
            setShowForm(!showForm)
          }}
        >
          {showForm ? "Cancel" : "Add New Job Role"}
        </button>
      </div>

      {alert.show && <div className={`alert alert-${alert.type}`}>{alert.message}</div>}

      {showForm && (
        <div className="card job-form-card">
          <h2>{editingId ? "Edit Job Role" : "Add New Job Role"}</h2>
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="title" className="form-label">
                  Job Title*
                </label>
                <input
                  type="text"
                  id="title"
                  name="title"
                  className="form-control"
                  value={formData.title}
                  onChange={handleInputChange}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="department" className="form-label">
                  Department*
                </label>
                <input
                  type="text"
                  id="department"
                  name="department"
                  className="form-control"
                  value={formData.department}
                  onChange={handleInputChange}
                  required
                />
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="location" className="form-label">
                Location
              </label>
              <input
                type="text"
                id="location"
                name="location"
                className="form-control"
                value={formData.location}
                onChange={handleInputChange}
              />
            </div>

            <div className="form-group">
              <label htmlFor="description" className="form-label">
                Job Description*
              </label>
              <textarea
                id="description"
                name="description"
                className="form-control"
                value={formData.description}
                onChange={handleInputChange}
                rows="4"
                required
              ></textarea>
            </div>

            <div className="form-group">
              <label htmlFor="requirements" className="form-label">
                Requirements*
              </label>
              <textarea
                id="requirements"
                name="requirements"
                className="form-control"
                value={formData.requirements}
                onChange={handleInputChange}
                rows="4"
                required
              ></textarea>
            </div>

            <div className="form-group">
              <label htmlFor="skills" className="form-label">
                Required Skills* (comma separated)
              </label>
              <input
                type="text"
                id="skills"
                name="skills"
                className="form-control"
                value={formData.skills}
                onChange={handleInputChange}
                placeholder="Python, Machine Learning, Data Analysis"
                required
              />
            </div>

            <div className="form-actions">
              <button type="submit" className="btn">
                {editingId ? "Update Job Role" : "Add Job Role"}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  resetForm()
                  setShowForm(false)
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {error ? (
        <div className="alert alert-danger">{error}</div>
      ) : jobs.length === 0 ? (
        <div className="card">
          <p className="no-data">No job roles added yet. Add your first job role to get started.</p>
        </div>
      ) : (
        <div className="jobs-list">
          {jobs.map((job) => (
            <div className="job-card" key={job._id}>
              <div className="job-header">
                <h2>{job.title}</h2>
                <div className="job-actions">
                  <button className="btn btn-secondary btn-sm" onClick={() => handleEdit(job)}>
                    Edit
                  </button>
                  <button className="btn btn-danger btn-sm" onClick={() => handleDelete(job._id)}>
                    Delete
                  </button>
                </div>
              </div>
              <div className="job-meta">
                <span className="job-department">{job.department}</span>
                {job.location && <span className="job-location">{job.location}</span>}
              </div>
              <div className="job-description">
                <h3>Description</h3>
                <p>{job.description}</p>
              </div>
              <div className="job-requirements">
                <h3>Requirements</h3>
                <p>{job.requirements}</p>
              </div>
              <div className="job-skills">
                <h3>Required Skills</h3>
                <div className="skills-list">
                  {job.skills.map((skill, index) => (
                    <span key={index} className="skill-tag">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default JobRoles

