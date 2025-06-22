from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import os  # ✅ required for os.getenv
from time import time
from functools import wraps


app = Flask(__name__)

# Configuration
CONFIG = {
    "ALLOWED_ORIGINS": [
        "https://gpa-vec-cys27.netlify.app",
        os.getenv("DEV_ORIGIN", "http://localhost:3000")  # Allow local dev origin
    ],
    "RATE_LIMIT_WINDOW": 60,  # 60 seconds
    "RATE_LIMIT_MAX_REQUESTS": 10,  # Max 10 requests per minute per IP
    "MAX_COURSES": 50,  # Prevent excessively large course lists
    "MAX_CREDITS": 10.0,  # Reasonable max credits per course
    "GRADE_POINTS": {
        "O": 10.0, "A+": 9.0, "A": 8.0, "B+": 7.0, "B": 6.0, "C": 5.0,
        "RA": 0.0, "W": 0.0
    }
}

# CORS setup
CORS(
    app,
    origins=CONFIG["ALLOWED_ORIGINS"],
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "OPTIONS"]
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting variables (Note: In-memory storage may not persist in serverless environments like AWS Lambda.
# Consider using Redis/DynamoDB or API Gateway throttling for production.)
request_counts = {}

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        current_time = int(time())
        
        # Clean up old timestamps
        if client_ip in request_counts:
            request_counts[client_ip] = [
                t for t in request_counts[client_ip] if current_time - t < CONFIG["RATE_LIMIT_WINDOW"]
            ]
        else:
            request_counts[client_ip] = []
        
        # Check rate limit
        if len(request_counts[client_ip]) >= CONFIG["RATE_LIMIT_MAX_REQUESTS"]:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return jsonify({"error": "Too many requests. Please wait a moment."}), 429
        
        request_counts[client_ip].append(current_time)
        return f(*args, **kwargs)
    
    return decorated_function

def calculate_gpa(courses):
    total_points = 0
    total_credits = 0
    
    for i, course in enumerate(courses):
        grade = course.get("grade", "").upper().strip()
        try:
            credits = float(course.get("credits", 0))
            if credits <= 0 or credits > CONFIG["MAX_CREDITS"]:
                logger.warning(f"Invalid credits {credits} at course index {i}")
                continue
        except (ValueError, TypeError):
            logger.error(f"Non-numeric credits at course index {i}")
            continue
        
        if grade not in CONFIG["GRADE_POINTS"]:
            logger.warning(f"Invalid grade {grade} at course index {i}")
            continue
        
        total_points += CONFIG["GRADE_POINTS"][grade] * credits
        total_credits += credits
    
    if total_credits == 0:
        return 0.0
    return round(total_points / total_credits, 2)

@app.route('/calculate-gpa', methods=['POST', 'OPTIONS'])
@rate_limit
def gpa_calculator():
    try:
        data = request.get_json()
        if not data or "courses" not in data or not isinstance(data["courses"], list):
            logger.error("Invalid request: missing or invalid courses")
            return jsonify({"error": "Please provide a valid list of courses"}), 400

        courses = data["courses"]
        if not courses:
            logger.warning("Empty courses list received")
            return jsonify({"error": "Courses list cannot be empty"}), 400
        if len(courses) > CONFIG["MAX_COURSES"]:
            logger.warning(f"Too many courses: {len(courses)} exceeds limit {CONFIG['MAX_COURSES']}")
            return jsonify({"error": f"Maximum {CONFIG['MAX_COURSES']} courses allowed"}), 400

        # Check for unselected or invalid grades
        for i, course in enumerate(courses):
            grade = course.get("grade", "").strip().upper()
            if not grade or grade == "SELECT":
                logger.warning(f"Unselected or empty grade at course index {i}")
                return jsonify({"error": f"Please select a valid grade for course {i + 1}"}), 400
            if grade not in CONFIG["GRADE_POINTS"]:
                logger.warning(f"Invalid grade {grade} at course index {i}")
                return jsonify({"error": f"Invalid grade '{grade}' for course {i + 1}"}), 400
            try:
                credits = float(course.get("credits", 0))
                if credits <= 0:
                    logger.warning(f"Non-positive credits {credits} at course index {i}")
                    return jsonify({"error": f"Credits for course {i + 1} must be positive"}), 400
                if credits > CONFIG["MAX_CREDITS"]:
                    logger.warning(f"Credits {credits} exceed max {CONFIG['MAX_CREDITS']} at course index {i}")
                    return jsonify({"error": f"Credits for course {i + 1} cannot exceed {CONFIG['MAX_CREDITS']}"}), 400
            except (ValueError, TypeError):
                logger.error(f"Invalid credits format at course index {i}")
                return jsonify({"error": f"Invalid credits for course {i + 1}"}), 400

        gpa = calculate_gpa(courses)
        total_credits = sum(float(course.get("credits", 0)) for course in courses 
                           if course.get("grade", "").upper() in CONFIG["GRADE_POINTS"])
        
        logger.info(f"GPA calculated: {gpa}, Total Credits: {total_credits}, IP: {request.remote_addr}")
        return jsonify({
            "gpa": gpa,
            "total_credits": total_credits
        })
    except Exception as e:
        logger.error(f"Unexpected error in gpa_calculator: {str(e)}")
        return jsonify({"error": "Internal server error. Please try again later."}), 500

@app.route('/warmup', methods=['GET'])
@rate_limit  # Apply rate limiting to prevent abuse
def warmup():
    logger.info("API warmup request received")
    return jsonify({"message": "API is awake!"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

# Serverless handler for platforms like AWS Lambda
def handler(event, context):
    return handle_request(app, event, context)
