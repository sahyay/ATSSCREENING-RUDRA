from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import json
from datetime import datetime
import uuid
import routes
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Custom JSON encoder to handle ObjectId and datetime
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Initialize Flask app
app = Flask(__name__)
app.json_encoder = MongoJSONEncoder  # Set the custom encoder
CORS(app)  # Enable CORS for all routes

# MongoDB connection
mongo_uri = os.getenv("MONGODB_URI", "mongodb+srv://sahilphadke77:SAHIL1612@clusterforats.kr4ntak.mongodb.net/ats_database?retryWrites=true&w=majority&appName=CLUSTERFORATS")
try:
    client = MongoClient(mongo_uri)
    # Test the connection
    client.admin.command('ping')
    logger.info("Successfully connected to MongoDB")
    db = client.get_database()
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {str(e)}")
    db = None

# Make the database instance available to routes
app.config["db"] = db

# Register routes
app.register_blueprint(routes.bp)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)

