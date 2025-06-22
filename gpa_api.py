
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from time import time
from functools import wraps

app = Flask(__name__)
CORS(app, resources={r"/calculate-gpa": {"origins": ["https://gpa-vec-cys27.netlify.app"]}})

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting variables
request_counts = {}
RATE_LIMIT_WINDOW = 60  # 60 seconds
RATE_LIMIT_MAX_REQUESTS = 10  # Max 10 requests per minute per IP

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        current_time = int(time())
        
        # Clean up old timestamps
        if client_ip in request_counts:
            request_counts[client_ip] = [
                t for t in request_counts[client_ip] if current_time - t < RATE_LIMIT_WINDOW
            ]
        else:
            request_counts[client_ip] = []
        
        # Check rate limit
        if len(request_counts[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return jsonify({"error": "Too many requests. Please wait a moment."}), 429
        
        request_counts[client_ip].append(current_time)
        return f(*args, **kwargs)
    
    return decorated_function

def calculate_gpa(courses):
    grade_points = {
        "O": 10.0, "A+": 9.0, "A": 8.0, "B+": 7.0, "B": 6.0, "C": 5.0,
        "RA": 0.0, "W": 0.0
    }
    total_points = 0
    total_credits = 0
    
    for course in courses:
        grade = course.get("grade", "").upper()
        try:
            credits = float(course.get("credits", 0))
            if credits <= 0:
                continue
        except (ValueError, TypeError):
            logger.error(f"Invalid credits for course: {course}")
            continue
        
        if grade not in grade_points:
            logger.warning(f"Invalid grade {grade} for course: {course}")
            continue
        
        total_points += grade_points[grade] * credits
        total_credits += credits
    
    if total_credits == 0:
        return 0.0
    return round(total_points / total_credits, 2)

@app.route('/calculate-gpa', methods=['POST'])
@rate_limit
def gpa_calculator():
    try:
        data = request.get_json()
        if not data or "courses" not in data or not isinstance(data["courses"], list):
            logger.error("Invalid request data: missing or invalid courses")
            return jsonify({"error": "Please provide a valid list of courses"}), 400
        
        courses = data["courses"]
        if not courses:
            logger.warning("Empty courses list received")
            return jsonify({"error": "Courses list cannot be empty"}), 400
        
        gpa = calculate_gpa(courses)
        total_credits = sum(float(course.get("credits", 0)) for course in courses 
                           if course.get("grade", "").upper() in ["O", "A+", "A", "B+", "B", "C", "RA", "W"])
        
        logger.info(f"GPA calculated: {gpa}, Total Credits: {total_credits}")
        return jsonify({
            "gpa": gpa,
            "total_credits": total_credits
        })
    except Exception as e:
        logger.error(f"Error in gpa_calculator: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/warmup', methods=['GET'])
def warmup():
    logger.info("API warmup request received")
    return jsonify({"message": "API is awake!"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

from serverless_wsgi import handle_request

def handler(event, context):
    return handle_request(app, event, context)
