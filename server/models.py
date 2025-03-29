from bson import ObjectId
from datetime import datetime

class JobRole:
    """Model for job roles in the system"""
    
    collection_name = "job_roles"
    
    @staticmethod
    def create(db, job_data):
        """Create a new job role"""
        job_data["createdAt"] = datetime.now()
        job_data["updatedAt"] = datetime.now()
        
        # Ensure skills is a list
        if "skills" in job_data and isinstance(job_data["skills"], str):
            job_data["skills"] = [s.strip() for s in job_data["skills"].split(",")]
        
        result = db[JobRole.collection_name].insert_one(job_data)
        return str(result.inserted_id)
    
    @staticmethod
    def get_all(db, limit=None, skip=0):
        """Get all job roles"""
        query = {}
        cursor = db[JobRole.collection_name].find(query).sort("createdAt", -1)
        
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
            
        return list(cursor)
    
    @staticmethod
    def get_by_id(db, job_id):
        """Get a job role by ID"""
        return db[JobRole.collection_name].find_one({"_id": ObjectId(job_id)})
    
    @staticmethod
    def update(db, job_id, job_data):
        """Update a job role"""
        job_data["updatedAt"] = datetime.now()
        
        # Ensure skills is a list
        if "skills" in job_data and isinstance(job_data["skills"], str):
            job_data["skills"] = [s.strip() for s in job_data["skills"].split(",")]
        
        result = db[JobRole.collection_name].update_one(
            {"_id": ObjectId(job_id)},
            {"$set": job_data}
        )
        return result.modified_count > 0
    
    @staticmethod
    def delete(db, job_id):
        """Delete a job role"""
        result = db[JobRole.collection_name].delete_one({"_id": ObjectId(job_id)})
        return result.deleted_count > 0
    
    @staticmethod
    def count(db):
        """Count total job roles"""
        return db[JobRole.collection_name].count_documents({})


class ResumeResult:
    """Model for resume screening results"""
    
    collection_name = "resume_results"
    
    @staticmethod
    def create(db, result_data):
        """Create a new resume result"""
        result_data["createdAt"] = datetime.now()
        result_data["updatedAt"] = datetime.now()
        
        result = db[ResumeResult.collection_name].insert_one(result_data)
        return str(result.inserted_id)
    
    @staticmethod
    def create_many(db, results):
        """Create multiple resume results"""
        for result in results:
            result["createdAt"] = datetime.now()
            result["updatedAt"] = datetime.now()
        
        result = db[ResumeResult.collection_name].insert_many(results)
        return [str(id) for id in result.inserted_ids]
    
    @staticmethod
    def get_all(db, filters=None, sort_by="score", sort_order=-1, page=1, limit=10):
        """Get all resume results with filtering and pagination"""
        query = filters or {}
        
        # Convert string IDs to ObjectId
        if "jobId" in query and query["jobId"]:
            query["jobId"] = ObjectId(query["jobId"])
        
        # Handle search
        if "search" in query and query["search"]:
            search_term = query.pop("search")
            query["$or"] = [
                {"name": {"$regex": search_term, "$options": "i"}},
                {"email": {"$regex": search_term, "$options": "i"}}
            ]
        
        # Determine sort field and order
        sort_field = sort_by
        sort_direction = 1 if sort_order == "asc" else -1
        
        # Count total results for pagination
        total = db[ResumeResult.collection_name].count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * limit
        cursor = db[ResumeResult.collection_name].find(query).sort(sort_field, sort_direction).skip(skip).limit(limit)
        
        return list(cursor), total
    
    @staticmethod
    def get_by_id(db, result_id):
        """Get a resume result by ID"""
        return db[ResumeResult.collection_name].find_one({"_id": ObjectId(result_id)})
    
    @staticmethod
    def get_by_batch(db, batch_id):
        """Get resume results by batch ID"""
        return list(db[ResumeResult.collection_name].find({"batchId": batch_id}))
    
    @staticmethod
    def count(db):
        """Count total resume results"""
        return db[ResumeResult.collection_name].count_documents({})
    
    @staticmethod
    def count_processed(db):
        """Count processed resume results"""
        return db[ResumeResult.collection_name].count_documents({"processed": True})
    
    @staticmethod
    def get_average_score(db):
        """Get average score of all resumes"""
        pipeline = [
            {"$match": {"score": {"$exists": True}}},
            {"$group": {"_id": None, "avgScore": {"$avg": "$score"}}}
        ]
        result = list(db[ResumeResult.collection_name].aggregate(pipeline))
        return result[0]["avgScore"] if result else 0

