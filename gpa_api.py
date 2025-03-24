from flask import Flask, request, jsonify
from flask_cors import CORS  # Add this line here

app = Flask(__name__)
CORS(app)  # Add this line here, right after app is created

def calculate_gpa(courses):
    # SRM Valliammai grade points
    grade_points = {
        "O": 10.0, "A+": 9.0, "A": 8.0, "B+": 7.0, "B": 6.0, "C": 5.0,
        "RA": 0.0, "W": 0.0
    }
    total_points = 0
    total_credits = 0
    
    for course in courses:
        grade = course.get("grade", "").upper()
        credits = float(course.get("credits", 0))
        if grade in grade_points and credits > 0:
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
    return jsonify({"gpa": gpa})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

from serverless_wsgi import handle_request

def handler(event, context):
    return handle_request(app, event, context)
