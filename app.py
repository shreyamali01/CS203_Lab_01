import json
import os
from flask import Flask, render_template, request, redirect, url_for,g, flash
import logging
from opentelemetry import trace 
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from pythonjsonlogger import jsonlogger
from opentelemetry.sdk.resources import Resource
import time
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Flask App Initialization
app = Flask(__name__)
app.secret_key = 'secret'
COURSE_FILE = 'course_catalog.json'
TELEMETRY_DATA = 'telemetry.json'

# Setting up JSON logging format
logger = logging.getLogger()
logHandler = logging.StreamHandler()

logFormatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
logHandler.setFormatter(logFormatter)
logHandler = logging.FileHandler('app.log')
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)

# Setting up TracerProvider and Adding Jaeger exporter
trace.set_tracer_provider(TracerProvider(resource=Resource.create({"service.name": "myflask"})))
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)

span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
FlaskInstrumentor().instrument_app(app)

# Getting a Tracer Instance
tracer = trace.get_tracer("flask-app","1.0.0")

telemetry_data = {
    "total_route_request_count": {
        "/": 0,
        "/catalog": 0,
        "/course/<code>": 0,
        "/add-course": 0,
    },
    "processing_time": {
        "/": 0.0,
        "/catalog": 0.0,
        "/course/<code>": 0.0,
        "/add-course": 0.0,
    },
    "error_count": {
        "missing_fields": 0,
        "duplicate_course_code": 0,
    }
}


# Utility Functions
def load_courses():
    """Load courses from the JSON file."""
    if not os.path.exists(COURSE_FILE):
        return []  # Return an empty list if the file doesn't exist
    with open(COURSE_FILE, 'r') as file:
        return json.load(file)


def save_courses(data):
    """Save new course data to the JSON file."""
    courses = load_courses()  # Load existing courses
    courses.append(data)  # Append the new course
    with open(COURSE_FILE, 'w') as file:
        json.dump(courses, file, indent=4)

def save_telemetry_data():
    """Save telemetry data to a file."""
    with open(TELEMETRY_DATA, 'w') as file:
        json.dump(telemetry_data, file, indent=4)


# Routes
@app.route('/')
def index():
    start_time = time.time()
    with tracer.start_as_current_span("index"):
        span = trace.get_current_span()
        span.set_attribute("user.ip", request.remote_addr)
        span.set_attribute("http.method", request.method)
        telemetry_data["total_route_request_count"]["/"] += 1
        response = render_template('index.html')
    
    #tracking processing time
    processing_time = time.time() - start_time
    telemetry_data["processing_time"]["/"] += processing_time
    save_telemetry_data()

    return response

@app.route('/catalog')
def course_catalog():
    start_time = time.time()
    with tracer.start_as_current_span("course_catalog"):
        #adding metadata to the spans
        span = trace.get_current_span()
        span.set_attribute("user.ip", request.remote_addr)
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.status_code", 200)

        #debugging
        #print(f"Created span for /catalog: {span}.")
        telemetry_data["total_route_request_count"]["/catalog"] += 1
        #span for loading courses
        with tracer.start_as_current_span("load_courses"):
            courses = load_courses()

        response = render_template('course_catalog.html', courses=courses)
    
    processing_time = time.time() - start_time
    telemetry_data["processing_time"]["/catalog"] += processing_time
    save_telemetry_data()

    return response
        



@app.route('/course/<code>')
def course_details(code):
    start_time = time.time()
    with tracer.start_as_current_span("course_details"):
        #adding metadata to the span
        span = trace.get_current_span()
        span.set_attribute("user.ip", request.remote_addr)
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.status_code", 200)
        telemetry_data["total_route_request_count"]["/course/<code>"] += 1
        courses = load_courses()
        course = next((course for course in courses if course['code'] == code), None)
    
        if not course:
            flash(f"No course found with code '{code}'.", "error")
            processing_time = time.time() - start_time
            telemetry_data["processing_time"]["/course/<code>"] += processing_time
            save_telemetry_data()
            return redirect(url_for('course_catalog'))
        response = render_template('course_details.html', course=course)
    
    processing_time = time.time() - start_time
    telemetry_data["processing_time"]["/course/<code>"] += processing_time
    save_telemetry_data()

    return response


#route to add a new course
@app.route('/add-course', methods=['GET', 'POST'])
def add_course():
    start_time = time.time()
    with tracer.start_as_current_span("add_course"):
        #adding metadata to the span
        span = trace.get_current_span()
        span.set_attribute("user.ip", request.remote_addr)
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.status_code", 200)
        telemetry_data["total_route_request_count"]["/add-course"] += 1

        if request.method == 'POST':
            #extracting the form data
            course_code = request.form.get('code')
            course_name = request.form.get('name')
            instructor = request.form.get('instructor')
            semester = request.form.get('semester')
            schedule = request.form.get('schedule', '')
            classroom = request.form.get('classroom', '')
            prerequisites = request.form.get('prerequisites', '')
            grading = request.form.get('grading', '')
            description = request.form.get('description', '')

            #storing current form data
            form_data = {
                'code': course_code,
                'name': course_name,
                'instructor': instructor,
                'semester': semester,
                'schedule': schedule,
                'classroom': classroom,
                'prerequisites': prerequisites,
                'grading': grading,
                'description': description
            }

            
            #validating required fields
            if not course_code or not course_name or not instructor or not semester or not schedule:
                missing_fields = []
                if not course_code:
                    missing_fields.append("course code")
                if not course_name:
                    missing_fields.append("course name")
                if not instructor:
                    missing_fields.append("instructor")
                if not semester:
                    missing_fields.append("semester")
                if not schedule:
                    missing_fields.append("schedule")
        
                #subsequent error message
                missing_fields_str = ", ".join(missing_fields)
                logging.error(f"Failed to add course: Missing required fields - {missing_fields_str}")
                flash(f"Please provide the following required fields: {missing_fields_str}.", "error")
                telemetry_data["error_count"]["missing_fields"] += 1
                processing_time = time.time() - start_time
                telemetry_data["processing_time"]["/add-course"] += processing_time
                save_telemetry_data()
                return render_template('add_course.html', form_data=form_data)
            
            courses = load_courses()

            if any(course['code'].lower() == course_code.lower() for course in courses):
                logging.error(f"Duplicate course code: {course_code}")
                flash("Course code already exists. Please use a unique code.", "error")
                telemetry_data["error_count"]["duplicate_course_code"] += 1
                processing_time = time.time() - start_time
                telemetry_data["processing_time"]["/add-course"] += processing_time
                save_telemetry_data()
                return render_template('add_course.html', form_data=form_data)

            # Save the course
            #span for saving the courses
            with tracer.start_as_current_span("save_course"):
                save_courses({
                    'code': course_code,
                    'name': course_name,
                    'instructor': instructor,
                    'semester': semester,  
                    'schedule':schedule,
                    'classroom':classroom,
                    'prerequisites':prerequisites,
                    'grading':grading,
                    'description':description
                })

            logging.info(f"Course added successfully: {course_code} - {course_name} by {instructor} for {semester}")
            flash("Course added successfully!", "success")
            processing_time = time.time() - start_time
            telemetry_data["processing_time"]["/add-course"] += processing_time
            save_telemetry_data()
            return redirect(url_for('course_catalog'))

        # Render the form template for GET requests
        response = render_template('add_course.html', form_data = {})
    processing_time = time.time() - start_time
    telemetry_data["processing_time"]["/add-course"] += processing_time
    save_telemetry_data()
    return response


if __name__ == '__main__':
    app.run(debug=True,port=5001)