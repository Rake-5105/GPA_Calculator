from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/calculate-gpa": {"origins": ["https://gpa-vec-cys27.netlify.app"]}})

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
            continue
        
        if grade not in grade_points:
            continue
        
        total_points += grade_points[grade] * credits
        total_credits += credits
    
    if total_credits == 0:
        return 0.0
    return round(total_points / total_credits, 2)

@app.route('/calculate-gpa', methods=['POST'])
def gpa_calculator():
    data = request.get_json()
    if not data or "courses" not in data:
        return jsonify({"error": "Please provide a list of courses"}), 400
    
    courses = data["courses"]
    gpa = calculate_gpa(courses)
    total_credits = sum(float(course.get("credits", 0)) for course in courses if course.get("grade", "").upper() in ["O", "A+", "A", "B+", "B", "C", "RA", "W"])
    
    return jsonify({
        "gpa": gpa,
        "total_credits": total_credits
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

from serverless_wsgi import handle_request

def handler(event, context):
    return handle_request(app, event, context)
