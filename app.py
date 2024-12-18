from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import uuid
from datetime import timedelta
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email
import datetime
import pandas as pd  # Import for handling Excel files
from werkzeug.utils import secure_filename
from gridfs import GridFS
from flask import send_file, abort
from bson import ObjectId

# Flask app initialization
app = Flask(__name__)

# Configuration
app.config['MONGO_URI'] = os.getenv(
    'MONGO_URI',
    "mongodb+srv://projectpro2000jan1:hackathon2024@studentdb.jrm0m.mongodb.net/studentdb?retryWrites=true&w=majority"
)
app.secret_key = os.getenv('SECRET_KEY', "your_secret_key")
mongo = PyMongo(app)

# Static directory for certificates
CERTIFICATE_DIR = os.path.join(app.root_path, 'static', 'certificates')
os.makedirs(CERTIFICATE_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'png'}

# Allowed file extensions for attendance upload
ATTENDANCE_ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

def attendance_allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ATTENDANCE_ALLOWED_EXTENSIONS

# Session timeout
app.permanent_session_lifetime = timedelta(minutes=30)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 MB

# WTForms LoginForm
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def role_required(role):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] != role:
                flash("Unauthorized access", "error")
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

# Initialize GridFS
fs = GridFS(mongo.db)
# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'Student')

        if not (name and email and password):
            flash("All fields are required", "error")
            return redirect(url_for('register'))

        if mongo.db.students.find_one({'email': email}):
            flash('Email already registered', 'error')
            return redirect(url_for('login'))

        hashed_password = generate_password_hash(password)
        new_user = {
            'name': name,
            'email': email,
            'password': hashed_password,
            'role': 'Student'
        }

        try:
            mongo.db.students.insert_one(new_user)
            flash('Registration successful', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error during registration: {e}", 'error')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not (email and password):
            flash("Email and Password are required", "error")
            return redirect(url_for('login'))

        user = mongo.db.students.find_one({'email': email})
        if not user or not check_password_hash(user['password'], password):
            flash('Invalid credentials', 'error')
            return redirect(url_for('login'))

        session['user_id'] = str(user['_id'])
        session['role'] = user['role']
        session.permanent = True

        flash('Login successful!', 'success')

        # Redirect based on role
        if user['role'] == 'Admin':
            return redirect(url_for('admin_dashboard'))
        elif user['role'] == 'Student':
            return redirect(url_for('student_dashboard'))
        else:
            flash('Unknown role. Please contact support.', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please log in to access the dashboard.", "error")
        return redirect(url_for('login'))

    role = session.get('role')
    if role == 'Admin':
        meetings = list(mongo.db.meetings.find())
        return render_template('admin_dashboard.html', meetings=meetings)
    elif role == 'Student':
        student = mongo.db.students.find_one({'_id': ObjectId(session['user_id'])})
        certificates = list(mongo.db.certificates.find({'student_id': session['user_id']}))
        return render_template('student_dashboard.html', student=student, certificates=certificates)

    flash("Invalid role. Please log in again.", "error")
    return redirect(url_for('login'))

@app.route('/student_dashboard')
def student_dashboard():
    if 'user_id' not in session or session.get('role') != 'Student':
        flash("Unauthorized access", "error")
        return redirect(url_for('login'))
    
    student = mongo.db.students.find_one({'_id': ObjectId(session['user_id'])})
    certificates = list(mongo.db.certificates.find({'student_id': session['user_id']}))
    meetings = list(mongo.db.meetings.find())
    notifications = list(mongo.db.notifications.find())
    student_email = session.get('email')

    # Fetch attendance records for the student
    attendance_records = list(mongo.db.attendance.find({'Student Email': student['email']}))

    # Fetch volunteer details for the student
    volunteer_details = list(mongo.db.volunteers.find({"student_email": student_email}))

    # Fetch additional details
    mentor_name = student.get('mentor_name')
    anchor_name = student.get('anchor_name')
    father_name = student.get('father_name')
    mother_name = student.get('mother_name')
    address = student.get('address')
    date_of_birth = student.get('date_of_birth')
    college_name = student.get('college_name')
    cgpa = student.get('cgpa')
    batch = student.get('batch')

    # Convert MongoDB cursor to a list
    for record in attendance_records:
        record['_id'] = str(record['_id'])
        record['Date'] = str(record['Date'])

    #attendance_list = list(attendance_records)
    return render_template(
        'student_dashboard.html',
        student=student,
        certificates=certificates,
        meetings=meetings,
        notifications=notifications,
        attendance_records=attendance_records,
        volunteer_details=volunteer_details,
        mentor_name=mentor_name,
        anchor_name=anchor_name,
        father_name=father_name,
        mother_name=mother_name,
        address=address,
        date_of_birth=date_of_birth,
        college_name=college_name,
        cgpa=cgpa,
        batch=batch
    )

@app.route('/admin_dashboard', methods=['GET', 'POST'])
@role_required('Admin')
def admin_dashboard():
    students = []
    meetings = list(mongo.db.meetings.find())
    notifications = list(mongo.db.notifications.find())  # Fetch notifications

    if request.method == 'POST':
        # Get the search query and filter type from the form
        search_query = request.form.get('search_query', '').strip()
        search_filter = request.form.get('search_filter', 'name')  # Default to 'name'

        if search_query:
            # Define the search condition based on the selected filter
            query_condition = {}
            if search_filter == 'id' and ObjectId.is_valid(search_query):
                query_condition['_id'] = ObjectId(search_query)
            elif search_filter == 'name':
                query_condition['name'] = {"$regex": search_query, "$options": "i"}
            elif search_filter == 'email':
                query_condition['email'] = {"$regex": search_query, "$options": "i"}

            # Search for matching students excluding Admins
            students = list(mongo.db.students.find({
                "$and": [
                    query_condition,
                    {"role": {"$ne": "Admin"}}  # Exclude Admins
                ]
            }))
        else:
            # Fetch all students excluding Admins if no search query is provided
            students = list(mongo.db.students.find({"role": {"$ne": "Admin"}}))
    else:
        # Handle GET requests: Show all students excluding Admins by default
        students = list(mongo.db.students.find({"role": {"$ne": "Admin"}}))

    # Convert ObjectId to string for template rendering
    for student in students:
        student['_id'] = str(student['_id'])
    for meeting in meetings:
        meeting['_id'] = str(meeting['_id'])
    for notification in notifications:
        notification['_id'] = str(notification['_id'])  # Ensure notifications' ObjectId is also converted

    # Render the admin dashboard with students, meetings, and notifications
    return render_template(
        'admin_dashboard.html',
        students=students,
        meetings=meetings,
        notifications=notifications
    )

@app.route('/create_notification', methods=['GET', 'POST'])
@role_required('Admin')
def create_notification():
    if request.method == 'POST':
        title = request.form['title']
        message = request.form['message']
        google_form_link = request.form.get('google_form_link')  # Get the optional Google Form link

        # Store the notification in the database (MongoDB)
        mongo.db.notifications.insert_one({
            'title': title,
            'message': message,
            'google_form_link': google_form_link,  # Store the Google Form link (if provided)
            'date_created': datetime.datetime.now()
        })

        flash('Notification created successfully', 'success')
        return redirect(url_for('admin_dashboard'))  # Redirect back to the admin dashboard

    return render_template('create_notification.html')  # Render the notification creation form

@app.route('/delete_notification/<string:notification_id>', methods=['POST'])
@role_required('Admin')
def delete_notification(notification_id):
    try:
        # Delete the notification from the database
        mongo.db.notifications.delete_one({'_id': ObjectId(notification_id)})
        flash('Notification deleted successfully', 'success')
    except Exception as e:
        flash(f"Error deleting notification: {e}", 'error')

    return redirect(url_for('admin_dashboard'))

@app.route('/view_student/<student_id>', methods=['GET'])
@role_required('Admin')  # Ensure only Admin can access this route
def view_student(student_id):
    # Fetch the student details using the provided student_id
    student = mongo.db.students.find_one({"_id": ObjectId(student_id)})
    
    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('admin_dashboard'))

    # Fetch certificates for the student
    certificates = list(mongo.db.certificates.find({'student_id': student_id}))
    student_email = session.get('email')
    # Fetch volunteer work for the student volunteer_details = list(mongo.db.volunteers.find({"student_email": student_email}))
    volunteer_details = list(mongo.db.volunteers.find({"student_email": student_email}))
        
    # Fetch attendance records for the student
    attendance_records = list(mongo.db.attendance.find({'Student Email': student['email']}))
    # Fetch additional details
    mentor_name = student.get('mentor_name')
    anchor_name = student.get('anchor_name')
    father_name = student.get('father_name')
    mother_name = student.get('mother_name')
    address = student.get('address')
    date_of_birth = student.get('date_of_birth')
    college_name = student.get('college_name')
    cgpa = student.get('cgpa')
    batch = student.get('batch')
    # Convert MongoDB cursor to a list
    for record in attendance_records:
        record['_id'] = str(record['_id'])
        record['Date'] = str(record['Date'])

    # Render the template
    return render_template(
        'view_student.html',
        student=student,
        certificates=certificates,
        attendance_records=attendance_records,
        volunteer_details=volunteer_details,
        mentor_name=mentor_name,
        anchor_name=anchor_name,
        father_name=father_name,
        mother_name=mother_name,
        address=address,
        date_of_birth=date_of_birth,
        college_name=college_name,
        cgpa=cgpa,
        batch=batch
    )


@app.route('/edit_student/<string:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    if 'user_id' not in session:
        flash("You must log in first", "error")
        return redirect(url_for('login'))

    # Check if the logged-in user is the student or an admin
    if session.get('role') != 'Admin' and session['user_id'] != student_id:
        flash("Unauthorized access", "error")
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        # Fetch updated form data
        update_data = {
            'mentor_name': request.form.get('mentor_name'),
            'anchor_name': request.form.get('anchor_name'),
            'father_name': request.form.get('father_name'),
            'mother_name': request.form.get('mother_name'),
            'address': request.form.get('address'),
            'date_of_birth': request.form.get('date_of_birth'),
            'college_name': request.form.get('college_name'),
            'cgpa': request.form.get('cgpa'),
            'batch': request.form.get('batch'),
        }

        # Handle photo upload
        photo = request.files.get('photo')
        if photo and allowed_file(photo.filename):
            # Save the file in GridFS
            photo_id = fs.put(photo, filename=photo.filename, content_type=photo.content_type)
            update_data['photo_id'] = photo_id  # Store GridFS file ID in MongoDB

        try:
            # Update student details in the database
            mongo.db.students.update_one({'_id': ObjectId(student_id)}, {'$set': update_data})
            flash('Details updated successfully', 'success')
        except Exception as e:
            flash(f"Error updating details: {e}", 'error')

        # Redirect based on role
        return redirect(url_for('dashboard') if session.get('role') == 'Admin' else url_for('student_dashboard'))

    # Fetch the student details
    student = mongo.db.students.find_one({'_id': ObjectId(student_id)})
    if not student:
        flash("Student not found", "error")
        return redirect(url_for('dashboard') if session.get('role') == 'Admin' else url_for('student_dashboard'))

    return render_template('edit_student.html', student=student)


@app.route('/get_photo/<string:photo_id>')
def get_photo(photo_id):
    try:
        # Retrieve the file from GridFS
        file = fs.get(ObjectId(photo_id))
        return file.read(), 200, {
            'Content-Type': file.content_type,
            'Content-Disposition': f'inline; filename="{file.filename}"'
        }
    except Exception as e:
        return f"Error retrieving file: {e}", 404
    
    
@app.route('/create_meeting', methods=['GET', 'POST'])
@role_required('Admin')
def create_meeting():
    if request.method == 'POST':
        meeting_id = request.form['meeting_id']  # Custom ID (if needed)
        zoom_passcode = request.form.get('zoom_passcode')  # Get the Zoom passcode from the form
        title = request.form.get('title')
        date = request.form.get('date')
        time = request.form.get('time')
        zoom_link = request.form.get('zoom_link')  # Optional field for Zoom link

        # Check for required fields
        if not (meeting_id and title and date and time):
            flash('All fields are required', 'error')
            return redirect(url_for('create_meeting'))

        # Check if the meeting ID already exists in the custom field (not ObjectId)
        if mongo.db.meetings.find_one({"meeting_id": meeting_id}):
            flash('Meeting ID already exists', 'error')
            return redirect(url_for('create_meeting'))

        # Generate a new ObjectId (MongoDB automatically generates this if no _id is provided)
        meeting_object_id = ObjectId()  # Generate a new ObjectId

        # Insert the new meeting into the database
        mongo.db.meetings.insert_one({
            "_id": meeting_object_id,  # Use generated ObjectId
            "title": title,
            "meeting_id": meeting_id,  # Custom meeting_id
            "zoom_passcode": zoom_passcode if zoom_passcode else None,  # Store passcode if provided
            "date": date,
            "time": time,
            "zoom_link": zoom_link  # Store the Zoom link if provided
        })

        flash('Meeting created successfully', 'success')
        return redirect(url_for('admin_dashboard'))  # Redirect to admin dashboard

    return render_template('create_meeting.html')  # Render the form for creating a meeting

@app.route('/upload_certificate', methods=['GET', 'POST'])
@role_required('Student')
def upload_certificate():
    if request.method == 'POST':
        file = request.files.get('certificate')
        title = request.form.get('title')  # Get the title from the form

        if file and allowed_file(file.filename):
            try:
                # Save the file in GridFS
                file_id = fs.put(file, filename=file.filename, content_type=file.content_type)

                # Create a new certificate record in the database
                new_certificate = {
                    'student_id': session['user_id'],  # Associate the certificate with the logged-in student
                    'file_id': file_id,  # Reference to the file in GridFS
                    'filename': file.filename,
                    'title': title,  # Save the title
                    'upload_date': datetime.datetime.now()
                }
                mongo.db.certificates.insert_one(new_certificate)

                flash('Certificate uploaded successfully', 'success')

            except Exception as e:
                flash(f"Error uploading certificate: {e}", 'error')

        else:
            flash('Invalid file type', 'error')

        # Redirect back to the student dashboard or certificate page with other details
        return redirect(url_for('student_dashboard')) # or any other page you prefer

    # Fetch the necessary data for the student
    student = mongo.db.students.find_one({"_id": ObjectId(session['user_id'])})
    certificates = mongo.db.certificates.find({'student_id': session['user_id']})
    volunteer_details = mongo.db.volunteers.find({"student_email": student['email']})
    attendance_records = mongo.db.attendance.find({'Student Email': student['email']})

    # Render the template, passing the data
    return render_template(
        'upload_certificate.html',
        student=student,
        certificates=certificates,
        volunteer_details=volunteer_details,
        attendance_records=attendance_records
    )
    
# Delete Meeting
@app.route('/delete_meeting/<string:meeting_id>', methods=['POST'])
@role_required('Admin')
def delete_meeting(meeting_id):
    try:
        # Attempt to delete the meeting by meeting_id
        result = mongo.db.meetings.delete_one({"meeting_id": meeting_id})

        if result.deleted_count > 0:
            flash('Meeting deleted successfully', 'success')
        else:
            flash('Meeting not found', 'warning')
    except Exception as e:
        flash(f"Error deleting meeting: {e}", 'error')

    return redirect(url_for('admin_dashboard'))  # Redirect back to the admin dashboard


# Delete Certificate
@app.route('/delete_certificate/<string:cert_id>', methods=['POST'])
def delete_certificate(cert_id):
    certificate = mongo.db.certificates.find_one({'_id': ObjectId(cert_id)})
    
    # Check if the certificate exists and belongs to the logged-in student
    if certificate and certificate['student_id'] == session['user_id']:
        try:
            # Remove the file from GridFS
            fs.delete(certificate['file_id'])

            # Delete the certificate record from the database
            mongo.db.certificates.delete_one({'_id': ObjectId(cert_id)})

            flash('Certificate deleted successfully', 'success')
        except Exception as e:
            flash(f"Error deleting certificate: {e}", 'error')
    else:
        flash('Unauthorized action', 'error')
    
    return redirect(url_for('student_dashboard'))

@app.route('/certificate/<file_id>')
def get_certificate(file_id):
    # Fetch the certificate file from GridFS using the file_id
    file = fs.get(ObjectId(file_id))
    return send_file(file, mimetype=file.content_type)

# everything is okay below here we are adding the upload attendance routres and also we are adding some codes in student dashboard and admindashboard for attendace 

@app.route('/upload_attendance', methods=['GET', 'POST'])
@role_required('Admin')
def upload_attendance():
    success_message = None
    error_message = None

    if request.method == 'POST':
        file = request.files.get('attendance_file')

        if file and attendance_allowed_file(file.filename):
            try:
                temp_dir = os.path.join(app.root_path, 'temp')
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)

                filename = secure_filename(file.filename)
                temp_path = os.path.join(temp_dir, filename)
                file.save(temp_path)

                try:
                    attendance_df = pd.read_excel(temp_path)
                except Exception as e:
                    error_message = f"Error reading Excel file: {e}"
                    os.remove(temp_path)
                    return render_template('upload_attendance.html', success_message=success_message, error_message=error_message)

                # Check for required columns
                required_columns = ['Student Email', 'Date', 'Duration']
                missing_columns = [col for col in required_columns if col not in attendance_df.columns]
                if missing_columns:
                    error_message = f"Missing required columns: {', '.join(missing_columns)}"
                    os.remove(temp_path)
                    return render_template('upload_attendance.html', success_message=success_message, error_message=error_message)

                # Calculate average duration
                average_duration = attendance_df['Duration'].mean()

                # Prepare records with "Present"/"Absent" status
                attendance_records = []
                for _, row in attendance_df.iterrows():
                    try:
                        record = {
                            "Student Email": row['Student Email'],
                            "Date": pd.to_datetime(row['Date']).strftime('%Y-%m-%d'),
                            "Duration": float(row['Duration']),
                            "Status": "Present" if float(row['Duration'])* 0.9 >= average_duration else "Absent"
                        }
                        attendance_records.append(record)
                    except Exception as e:
                        error_message = f"Invalid data in row: {row}. Error: {e}"
                        os.remove(temp_path)
                        return render_template('upload_attendance.html', success_message=success_message, error_message=error_message)

                # Insert records into MongoDB
                mongo.db.attendance.insert_many(attendance_records)
                os.remove(temp_path)
                success_message = "Attendance uploaded successfully."
            except Exception as e:
                error_message = f"Error uploading attendance: {e}"
        else:
            error_message = 'Invalid file type. Please upload an Excel file.'

    return render_template('upload_attendance.html', success_message=success_message, error_message=error_message)

@app.route('/view_attendance', methods=['GET'])
@role_required('Student')
def view_attendance():
    user_email = session.get('email')  # Ensure email is stored in the session upon login
    if not user_email:
        return redirect(url_for('login'))  # Redirect if not logged in

    attendance_records = list(mongo.db.attendance.find({"Student Email": user_email}))
    return render_template('view_attendance.html', attendance=attendance_records)

@app.route('/update_volunteer/<volunteer_id>', methods=['GET', 'POST'])
def update_volunteer(volunteer_id):
    if 'user_id' not in session or session.get('role') != 'Student':
        flash("Unauthorized access", "error")
        return redirect(url_for('login'))

    volunteer = mongo.db.volunteers.find_one({'_id': ObjectId(volunteer_id)})
    
    if not volunteer:
        flash("Volunteer details not found", "error")
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        volunteer_name = request.form['volunteer_name']
        description = request.form['description']
        hours_worked = float(request.form['hours_worked'])

        mongo.db.volunteers.update_one(
            {'_id': ObjectId(volunteer_id)},
            {'$set': {
                'volunteer_name': volunteer_name,
                'description': description,
                'hours_worked': hours_worked,
                'date_uploaded': datetime.datetime.now()
            }}
        )
        
        flash("Volunteer work updated successfully", "success")
        return redirect(url_for('student_dashboard'))

    return render_template('update_volunteer.html', volunteer=volunteer)

@app.route('/add_volunteer', methods=['GET', 'POST'])
def add_volunteer():
    if 'user_id' not in session or session.get('role') != 'Student':
        flash("Unauthorized access", "error")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        volunteer_name = request.form['volunteer_name']
        description = request.form['description']
        hours_worked = float(request.form['hours_worked'])

        # Insert the volunteer details into the database
        mongo.db.volunteers.insert_one({
            'student_id': ObjectId(session['user_id']),
            'volunteer_name': volunteer_name,
            'description': description,
            'hours_worked': hours_worked,
            'date_uploaded': datetime.datetime.now()
        })
        
        flash("Volunteer work added successfully", "success")
        return redirect(url_for('student_dashboard'))

    return render_template('add_volunteer.html')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
