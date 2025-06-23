# --- START OF FILE app.py ---

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from werkzeug.security import generate_password_hash, check_password_hash
import os
import random
import string
from functools import wraps
import sqlite3
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, TextAreaField, RadioField, BooleanField, PasswordField, SubmitField, SelectMultipleField
from wtforms.validators import DataRequired, Email, Optional, NumberRange, EqualTo
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename
import json

import google.generativeai as genai
from gemini_api import generate_gemini_response

# Import db and models from database.py
from database import db, User, HealthReview, Activity, Appointment, PillReminder, BloodDonor, Insurance, ChatHistory, UserHealthDetail, Notification, BloodRequest, ResourceSuggestion, BackupData

from twilio.rest import Client

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

genai.configure(api_key=GOOGLE_API_KEY)

model = genai.GenerativeModel(
    model_name='gemini-1.5-flash-latest'
)

# Ensure instance folder exists before setting DB URI
if not os.path.exists(app.instance_path):
    os.makedirs(app.instance_path)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'healthcare.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# FIX: This function now works because the medical_id column exists.
def generate_medical_id():
    while True:
        medical_id = 'MID' + ''.join(random.choices(string.digits, k=9))
        if not User.query.filter_by(medical_id=medical_id).first():
            return medical_id

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        username = request.form['username']
        email = request.form['email']
        age = request.form['age']
        phone_number = request.form['phone_number']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('register'))
        hashed_pw = generate_password_hash(password)
        medical_id = generate_medical_id()
        new_user = User(medical_id=medical_id, username=username, full_name=full_name, email=email, age=age, phone_number=phone_number, password=hashed_pw, is_admin=False)
        db.session.add(new_user)
        db.session.commit()
        session['is_new_user'] = True
        flash(f'Registration successful! Your Medical ID is {medical_id}. Please log in.')
        # FIX: Redirect to login page on success instead of back to register.
        return redirect(url_for('login'))
    return render_template('register.html')

# NOTE: The redundant /signup route has been removed to simplify the app.

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('You need to be logged in to view this page.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            if user.blocked:
                flash('Your account has been blocked. Contact admin.')
                return redirect(url_for('login'))
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin  # Use the is_admin field from database
            # If just registered, keep is_new_user; else, set to False
            if 'is_new_user' not in session:
                session['is_new_user'] = False
            flash(f'Welcome, {user.username}!')
            # Log login activity
            activity = Activity(user_id=user.id, action='Logged in')
            db.session.add(activity)
            db.session.commit()
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/home')
@login_required
def home():
    notifications = Notification.query.filter_by(user_id=session['user_id'], is_read=False).order_by(Notification.timestamp.desc()).all()
    # Determine welcome message
    username = session.get('username', 'User')
    if session.get('is_new_user', False):
        welcome_message = f"Welcome, {username}!"
        session['is_new_user'] = False  # Show only once
    else:
        welcome_message = f"Welcome back, {username}!"
    return render_template('home.html', welcome_message=welcome_message, notifications=notifications)

# FIX: Added the missing route for admin registration.
@app.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('admin_register'))
        
        hashed_pw = generate_password_hash(password)
        medical_id = generate_medical_id() # All users need a medical ID.
        new_admin = User(
            medical_id=medical_id,
            username=username, 
            password=hashed_pw, 
            is_admin=True
        )
        db.session.add(new_admin)
        db.session.commit()
        flash('Admin account created successfully. Please log in.')
        return redirect(url_for('login'))
    return render_template('admin_register.html')

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    print(f"[DEBUG] Admin dashboard accessed by user_id: {session.get('user_id')}")
    # Check if current user is an admin
    current_user = User.query.get(session['user_id'])
    print(f"[DEBUG] Current user: {current_user}")
    print(f"[DEBUG] User is_admin: {current_user.is_admin if current_user else None}")
    
    if not current_user or not current_user.is_admin:
        print(f"[DEBUG] Access denied - redirecting to home")
        flash('Admin access required.')
        return redirect(url_for('home'))
    
    print(f"[DEBUG] Access granted - rendering admin dashboard")
    users = User.query.all()
    activities = Activity.query.order_by(Activity.timestamp.desc()).limit(50).all()
    total_users = User.query.count()
    # Gather recent activities for each user
    user_activities = {}
    for user in users:
        user_activities[user.id] = Activity.query.filter_by(user_id=user.id).order_by(Activity.timestamp.desc()).all()
    return render_template('admin.html', users=users, activities=activities, total_users=total_users, user_activities=user_activities)

@app.route('/symptom_checker', methods=['GET', 'POST'])
@login_required
def symptom_checker():
    result = None
    valid_symptoms = [
        'Fever', 'Cough', 'Headache', 'Fatigue', 'Sore throat', 'Shortness of breath',
        'Nausea', 'Vomiting', 'Diarrhea', 'Muscle pain', 'Chest pain', 'Rash', 'Dizziness', 'Loss of taste', 'Loss of smell',
        'Stomach ache', 'Chills'
    ]
    if request.method == 'POST':
        selected = request.form.getlist('common_symptoms')
        extra = request.form.get('extra_symptoms', '').strip()
        all_symptoms = selected.copy()
        if extra:
            extra_symptoms = [s.strip().capitalize() for s in extra.split(',') if s.strip()]
            all_symptoms.extend(extra_symptoms)
        non_medical = [s for s in all_symptoms if s.capitalize() not in valid_symptoms]
        if non_medical:
            result = "<div class='error'>Non-medical input. We can't give you information about this. You can ask further details about medical related symptoms.</div>"
            return render_template('symptom_checker.html', result=result)
        symptoms = ', '.join(all_symptoms)
        prompt = f"""
        Given the following symptoms: {symptoms}
        1. Predict the most likely disease or condition.
        2. List the risk factors.
        3. Suggest medical cures.
        4. Suggest home remedies.
        Respond in HTML format for direct rendering.remove the ```html and ``` tag from the response.
        """
        try:
            result = generate_gemini_response(prompt)
            
            # Log activity
            activity = Activity(user_id=session['user_id'], action=f'Used symptom checker for: {symptoms}')
            db.session.add(activity)
            db.session.commit()
        except Exception as e:
            result = f"<div class='error'>Error: {str(e)}</div>"
    return render_template('symptom_checker.html', result=result)

@app.route('/chat_assistant', methods=['GET', 'POST'])
@login_required
def chat_assistant():
    if request.method == 'POST':
        original_message = request.form.get('message')
        if not original_message:
            return jsonify({'response': 'Please enter a message.'})

        processed_message = original_message.lower().strip()

        # Basic conversational canned responses for exact matches
        canned_responses = {
            "hello": "Hello! How can I assist you with your health today?",
            "hi": "Hi there! What health questions do you have?",
            "hey": "Hey! I'm here to help with your health inquiries.",
            "good morning": "Good morning! How can I help you today?",
            "good afternoon": "Good afternoon! What can I help you with?",
            "good evening": "Good evening! How can I assist you?",
            "bye": "Goodbye! Take care of your health.",
            "goodbye": "Goodbye! Take care of your health.",
            "thanks": "You're welcome! Is there anything else I can help you with?",
            "thank you": "You're welcome! Is there anything else I can help you with?"
        }

        if processed_message in canned_responses:
            response = canned_responses[processed_message]
            # Save this simple interaction to chat history
            chat = ChatHistory(user_id=session['user_id'], message=original_message, response=response)
            db.session.add(chat)
            db.session.commit()
            return jsonify({'response': response})

        # If not a canned response, check for health keywords
        health_keywords = [
            'health', 'doctor', 'medicine', 'symptom', 'disease', 'treatment', 'pain', 'illness', 'hospital',
            'fever', 'cough', 'headache', 'bmi', 'blood', 'pressure', 'diabetes', 'mental', 'anxiety', 'stress',
            'nutrition', 'diet', 'exercise', 'fitness', 'injury', 'infection', 'vaccine', 'pill', 'reminder', 'insurance',
            'appointment', 'review', 'wellness', 'clinic', 'therapy', 'support', 'medical', 'consult', 'prescription', 'pharmacy'
        ]
        
        if any(keyword in processed_message for keyword in health_keywords):
            prompt = f"You are a helpful AI health assistant. User says: {original_message}"
            response = generate_gemini_response(prompt)
            # Save to history and log activity
            chat = ChatHistory(user_id=session['user_id'], message=original_message, response=response)
            db.session.add(chat)
            activity = Activity(user_id=session['user_id'], action=f'Used AI health chat: {original_message[:50]}...')
            db.session.add(activity)
            db.session.commit()
            return jsonify({'response': response})
        
        # If no health keywords, provide the default "non-health" response
        response = "I'm designed to focus on health-related topics. Please ask me about symptoms, treatments, wellness, or other medical subjects."
        return jsonify({'response': f"<div class='error'>{response}</div>"})

    # GET request logic
    chat_history = ChatHistory.query.filter_by(user_id=session['user_id']).order_by(ChatHistory.timestamp.desc()).limit(20).all()
    return render_template('chat_assistant.html', chat_history=chat_history)

@app.route('/get_conversation/<int:latest_chat_id>')
@login_required
def get_conversation(latest_chat_id):
    # First, validate the requested chat ID belongs to the user
    latest_chat = ChatHistory.query.get_or_404(latest_chat_id)
    if latest_chat.user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    # Fetch all chats for the user up to the timestamp of the selected chat
    all_chats = ChatHistory.query.filter(
        ChatHistory.user_id == session['user_id'],
        ChatHistory.timestamp <= latest_chat.timestamp
    ).order_by(ChatHistory.timestamp.asc()).all()
    
    # Serialize the data
    conversation = []
    for chat in all_chats:
        conversation.append({
            'message': chat.message,
            'response': chat.response
        })
        
    return jsonify({'success': True, 'conversation': conversation})

@app.route('/clear_chat_history', methods=['POST'])
@login_required
def clear_chat_history():
    try:
        ChatHistory.query.filter_by(user_id=session['user_id']).delete()
        db.session.commit()
        flash('Chat history cleared successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing chat history: {e}', 'danger')
    return redirect(url_for('chat_assistant'))

@app.route('/bmi_calculator', methods=['GET', 'POST'])
@login_required
def bmi_calculator():
    bmi = None
    diet_recommendation = None
    next_page = request.args.get('next')
    if request.method == 'POST':
        try:
            weight = float(request.form.get('weight'))
            height = float(request.form.get('height')) / 100  # convert cm to meters
            bmi = round(weight / (height * height), 2)
            session['user_bmi'] = bmi
            # Get diet recommendation from Gemini
            prompt = f"""
            Based on a BMI of {bmi}, provide personalized diet recommendations to improve health.
            Include:
            1. What this BMI means for health
            2. Specific diet recommendations
            3. Foods to include and avoid
            4. General health tips
            Respond in HTML format for direct rendering.
            """
            diet_recommendation = generate_gemini_response(prompt)
            # Store in HealthReview
            review = HealthReview(user_id=session['user_id'], feature='BMI', status='Calculated', percentage=bmi)
            db.session.add(review)
            db.session.commit()
            # Fix: preserve next_page after POST
            next_page = request.form.get('next') or next_page
            if next_page:
                return redirect(url_for(next_page))
        except Exception as e:
            bmi = 'Invalid input'
            diet_recommendation = f"<div class='error'>Error calculating BMI: {str(e)}</div>"
        # Fix: preserve next_page after POST for template rendering
        next_page = request.form.get('next') or next_page
    return render_template('bmi_calculator.html', bmi=bmi, diet_recommendation=diet_recommendation, next_page=next_page)

@app.route('/appointments', methods=['GET', 'POST'])
@login_required
def appointments():
    if request.method == 'POST':
        doctor = request.form.get('doctor')
        department = request.form.get('department')
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        reason = request.form.get('reason')
        reminder_hours = request.form.get('reminder_hours')

        if date_str and time_str and doctor and department:
            try:
                appointment_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                reminder_hours = int(reminder_hours) if reminder_hours else None
                
                appt = Appointment(
                    user_id=session['user_id'],
                    appointment_datetime=appointment_datetime,
                    reason=reason,
                    doctor=doctor,
                    department=department,
                    reminder_hours=reminder_hours
                )
                db.session.add(appt)
                
                notif_msg = f"Appointment booked with Dr. {doctor} ({department}) on {appointment_datetime.strftime('%Y-%m-%d at %H:%M')}."
                notif = Notification(user_id=session['user_id'], message=notif_msg)
                db.session.add(notif)
                db.session.commit()
                flash('Appointment booked!')
                # Send SMS
                user = User.query.get(session['user_id'])
                if user.phone_number:
                    phone = user.phone_number
                    if not phone.startswith('+'):
                        phone = '+91' + phone
                    send_sms(phone, notif_msg)
            except (ValueError, TypeError) as e:
                flash(f'Invalid data provided: {e}', 'danger')

    future_appts = Appointment.query.filter(
        Appointment.user_id == session['user_id'],
        Appointment.appointment_datetime > datetime.now()
    ).order_by(Appointment.appointment_datetime.asc()).all()

    return render_template('appointments.html', appointments=future_appts)

@app.route('/pill_reminder', methods=['GET', 'POST'])
@login_required
def pill_reminder():
    if request.method == 'POST':
        pill_name = request.form.get('pill_name')
        dosage = request.form.get('dosage')
        time_str = request.form.get('time')
        if pill_name and dosage and time_str:
            try:
                reminder_time = datetime.strptime(time_str, '%H:%M').time()
                reminder = PillReminder(
                    user_id=session['user_id'],
                    pill_name=pill_name,
                    dosage=dosage,
                    reminder_time=reminder_time
                )
                db.session.add(reminder)
                
                notif_msg = f"Pill Reminder: Take {pill_name} ({dosage}) at {time_str}."
                notif = Notification(user_id=session['user_id'], message=notif_msg)
                db.session.add(notif)
                db.session.commit()
                flash('Pill reminder added!')
                # Send SMS
                user = User.query.get(session['user_id'])
                if user.phone_number:
                    phone = user.phone_number
                    if not phone.startswith('+'):
                        phone = '+91' + phone
                    send_sms(phone, notif_msg)
            except (ValueError, TypeError) as e:
                flash(f'Invalid time format: {e}', 'danger')

    now_time = datetime.now().time()
    # Filter reminders to show only those for the current or future time
    reminders = PillReminder.query.filter(
        PillReminder.user_id == session['user_id'],
        PillReminder.reminder_time >= now_time
    ).order_by(PillReminder.reminder_time.asc()).all()
    
    return render_template('pill_reminder.html', reminders=reminders)

@app.route('/blood_donation', methods=['GET', 'POST'])
@login_required
def blood_donation():
    donor_success = None
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        # New fields
        name = request.form.get('name', '').strip()
        age = request.form.get('age', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        # Update user profile if provided
        updated = False
        if name:
            user.full_name = name
            updated = True
        if age:
            try:
                user.age = int(age)
                updated = True
            except ValueError:
                pass
        if phone_number:
            user.phone_number = phone_number
            updated = True
        if updated:
            db.session.commit()
        blood_group = request.form.get('blood_group')
        last_donation_str = request.form.get('last_donation')
        if blood_group:
            try:
                last_donation = datetime.strptime(last_donation_str, '%Y-%m-%d').date() if last_donation_str else None
                donor = BloodDonor(
                    user_id=session['user_id'],
                    blood_group=blood_group,
                    last_donation=last_donation
                )
                db.session.add(donor)
                db.session.commit()
                donor_success = 'Blood donor info saved!'
            except (ValueError, TypeError) as e:
                flash(f'Invalid date format for last donation: {e}', 'danger')
    donors = BloodDonor.query.all()
    return render_template('blood_donation.html', donors=donors, donor_success=donor_success)

@app.route('/blood_request', methods=['GET', 'POST'])
@login_required
def blood_request():
    request_success = None
    accept_success = None
    if request.method == 'POST':
        if 'accept_request_id' in request.form:
            # Accept a donation for a request
            request_id = request.form.get('accept_request_id')
            req = BloodRequest.query.get(request_id)
            if req:
                req.accepted_by = session['user_id']
                db.session.commit()
                accept_success = 'You have accepted to donate for this request!'
        elif 'accept_donor_id' in request.form:
            # Accept a specific donor for a request
            request_id = request.form.get('request_id')
            donor_id = request.form.get('accept_donor_id')
            req = BloodRequest.query.get(request_id)
            donor = BloodDonor.query.get(donor_id)
            if req and donor:
                req.accepted_by = donor.user_id
                db.session.commit()
                accept_success = f'You have accepted donation from {donor.user.full_name}!'
        else:
            blood_group = request.form.get('request_blood_group')
            units_needed = request.form.get('units_needed')
            reason = request.form.get('reason')
            contact_info = request.form.get('contact_info')
            if blood_group and units_needed:
                blood_request = BloodRequest(user_id=session['user_id'], blood_group=blood_group, units_needed=units_needed, reason=reason, contact_info=contact_info)
                db.session.add(blood_request)
                db.session.commit()
                request_success = 'Blood request submitted!'
    
    requests = BloodRequest.query.order_by(BloodRequest.timestamp.desc()).all()
    
    # For each request, find matching donors with user details
    donors_by_group = {}
    for req in requests:
        # Get donors with their user information
        donors = db.session.query(BloodDonor, User).join(User, BloodDonor.user_id == User.id).filter(
            BloodDonor.blood_group == req.blood_group
        ).all()
        donors_by_group[req.id] = donors
    
    return render_template('blood_request.html', requests=requests, donors_by_group=donors_by_group, request_success=request_success, accept_success=accept_success)

@app.route('/mental_health', methods=['GET', 'POST'])
@login_required
def mental_health():
    response = None
    if request.method == 'POST':
        message = request.form.get('message')
        if message:
            prompt = f"You are a mental health support assistant. User says: {message}"
            response = generate_gemini_response(prompt)
            
            # Log activity
            activity = Activity(user_id=session['user_id'], action=f'Used mental health support: {message[:50]}{"..." if len(message) > 50 else ""}')
            db.session.add(activity)
            db.session.commit()
    return render_template('mental_health.html', response=response)

@app.route('/insurance', methods=['GET', 'POST'])
@login_required
def insurance():
    if request.method == 'POST':
        provider = request.form.get('provider')
        policy_number = request.form.get('policy_number')
        valid_until_str = request.form.get('valid_until')
        insurance_type = request.form.get('insurance_type') or 'Health'
        
        if provider and policy_number and insurance_type:
            try:
                valid_until = datetime.strptime(valid_until_str, '%Y-%m-%d').date() if valid_until_str else None
                ins = Insurance(
                    user_id=session['user_id'],
                    provider=provider,
                    policy_number=policy_number,
                    valid_until=valid_until,
                    type=insurance_type
                )
                db.session.add(ins)
                db.session.commit()
                flash('Insurance info saved!')
            except (ValueError, TypeError) as e:
                flash(f'Invalid date format for "valid until": {e}', 'danger')

    insurances = Insurance.query.filter_by(user_id=session['user_id']).all()
    return render_template('insurance.html', insurances=insurances)

# Dummy user settings (replace with DB in production)
dummy_settings = {
    'name': 'John Doe',
    'age': 30,
    'gender': 'Male',
    'email': 'john@example.com',
    'height': 175,
    'weight': 70,
    'bmi_goal': 22,
    'medical_history': '',
    'activity_level': 'Moderate',
    'theme': 'light',
    'meal_reminders': True,
    'workout_alerts': False,
    'health_check': True,
    'language': 'English',
    'units': 'Metric',
    'diet_pref': 'None',
    'calorie_goal': 2000,
    'allergies': '',
    'exercise_types': ['Yoga'],
    'workout_duration': '30 min',
    'intensity': 'Medium',
    'conditions': ['Diabetes'],
    'shap_lime': False,
    'model_confidence': False,
    'voice_assistant': False,
}

class SettingsForm(FlaskForm):
    # User Profile
    name = StringField('Name', validators=[DataRequired()])
    age = IntegerField('Age', validators=[DataRequired(), NumberRange(min=0, max=120)])
    gender = SelectField('Gender', choices=[('Male','Male'),('Female','Female'),('Other','Other')])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone_number = StringField('Phone Number', validators=[DataRequired()])
    height = IntegerField('Height (cm)', validators=[Optional()])
    weight = IntegerField('Weight (kg)', validators=[Optional()])
    bmi_goal = IntegerField('BMI Goal', validators=[Optional()])
    medical_history = TextAreaField('Medical History', validators=[Optional()])
    activity_level = SelectField('Activity Level', choices=[('Sedentary','Sedentary'),('Light','Light'),('Moderate','Moderate'),('Active','Active'),('Very Active','Very Active')])
    # AI Personalization
    diet_pref = SelectField('Dietary Preference', choices=[('None','None'),('Vegetarian','Vegetarian'),('Vegan','Vegan'),('Keto','Keto'),('Paleo','Paleo')])
    calorie_goal = IntegerField('Calorie Goal', validators=[Optional()])
    allergies = TextAreaField('Allergies', validators=[Optional()])
    exercise_types = SelectMultipleField('Preferred Exercise Types', choices=[('Yoga','Yoga'),('Cardio','Cardio'),('Strength','Strength')])
    workout_duration = SelectField('Workout Duration', choices=[('15 min','15 min'),('30 min','30 min'),('45 min','45 min'),('60 min','60 min')])
    intensity = SelectField('Intensity', choices=[('Low','Low'),('Medium','Medium'),('High','High')])
    # Health Conditions
    conditions = SelectMultipleField('Health Conditions', choices=[('Diabetes','Diabetes'),('Hypertension','Hypertension'),('PCOS','PCOS')])
    # Privacy & Security
    current_password = PasswordField('Current Password', validators=[Optional()])
    new_password = PasswordField('New Password', validators=[Optional()])
    confirm_password = PasswordField('Confirm New Password', validators=[Optional(), EqualTo('new_password', message='Passwords must match')])
    # Support & Feedback
    feedback = TextAreaField('Feedback', validators=[Optional()])
    # Actions
    download_data = SubmitField('Download Health Data')
    clear_history = SubmitField('Clear History')
    delete_account = BooleanField('Delete my account (this cannot be undone)')
    submit = SubmitField('Save Settings')

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings_page():
    user = User.query.get(session['user_id'])
    
    # Get or create health details
    health = UserHealthDetail.query.filter_by(user_id=user.id).first()
    if not health:
        health = UserHealthDetail(user_id=user.id)
        db.session.add(health)
        db.session.commit()
    
    # Ensure profile_pics folder exists
    upload_folder = os.path.join(app.static_folder, 'profile_pics')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    if request.method == 'POST':
        # Update user fields directly from form data
        user.full_name = request.form.get('name', user.full_name)
        user.email = request.form.get('email', user.email)
        user.age = request.form.get('age', user.age)
        user.gender = request.form.get('gender', user.gender)
        user.phone_number = request.form.get('phone_number', user.phone_number)
        
        # Update health details
        health.height_cm = request.form.get('height') or None
        health.weight_kg = request.form.get('weight') or None
        health.allergies = request.form.get('allergies') or None
        health.chronic_conditions = request.form.get('medical_history') or None
        
        # Profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                user.profile_picture = f'profile_pics/{filename}'
    
        db.session.commit()
    
        # Log activity
        activity = Activity(user_id=session['user_id'], action='Updated settings')
        db.session.add(activity)
        db.session.commit()
        
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings_page'))
    
    # Handle profile picture display
    profile_picture = user.profile_picture if user.profile_picture and os.path.exists(os.path.join(app.static_folder, user.profile_picture)) else 'profile_placeholder.svg'
    
    # Create form with current user data
    form = SettingsForm()
    form.name.data = user.full_name
    form.email.data = user.email
    form.age.data = user.age
    form.gender.data = user.gender
    form.phone_number = getattr(form, 'phone_number', None) or type('obj', (), {})() # ensure attribute exists
    form.phone_number.data = user.phone_number
    form.height.data = health.height_cm
    form.weight.data = health.weight_kg
    form.allergies.data = health.allergies
    form.medical_history.data = health.chronic_conditions
    
    return render_template('settings.html', form=form, profile_picture=profile_picture)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('login'))

@app.route('/check_user_adilhasan')
def check_user_adilhasan():
    conn = sqlite3.connect('instance/healthcare.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username=?", ('adilhasan',))
    user = cursor.fetchone()
    conn.close()
    if user:
        return jsonify({'exists': True, 'user': user})
    else:
        return jsonify({'exists': False})

@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    # Check if current user is an admin
    current_user = User.query.get(session['user_id'])
    if not current_user or not current_user.is_admin:
        return redirect(url_for('home'))
    
    user = User.query.get_or_404(user_id)
    health = UserHealthDetail.query.filter_by(user_id=user.id).first()
    if not health:
        health = UserHealthDetail(user_id=user.id)
        db.session.add(health)
        db.session.commit()
    
    # Get user activities for display
    user_activities = Activity.query.filter_by(user_id=user.id).order_by(Activity.timestamp.desc()).limit(20).all()
    
    # Get user appointments for display - FIXED
    user_appointments = Appointment.query.filter_by(user_id=user.id).order_by(Appointment.appointment_datetime.desc()).all()
    
    if request.method == 'POST':
        # Update user fields
        user.full_name = request.form['full_name']
        user.email = request.form['email']
        user.age = request.form['age']
        user.phone_number = request.form['phone_number']
        user.gender = request.form.get('gender', user.gender)
        
        # Profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename:
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(app.static_folder, 'profile_pics')
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                user.profile_picture = f'profile_pics/{filename}'
        
        # Health details
        health.height_cm = request.form.get('height_cm') or None
        health.weight_kg = request.form.get('weight_kg') or None
        health.blood_group = request.form.get('blood_group') or None
        health.allergies = request.form.get('allergies') or None
        health.chronic_conditions = request.form.get('chronic_conditions') or None
        health.medications = request.form.get('medications') or None
        
        db.session.commit()
        
        # Log activity
        activity = Activity(user_id=user.id, action=f'Profile updated by admin')
        db.session.add(activity)
        db.session.commit()
        
        flash('User updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    profile_picture = user.profile_picture if user.profile_picture and os.path.exists(os.path.join(app.static_folder, user.profile_picture)) else 'profile_placeholder.svg'
    return render_template('edit_user.html', user=user, health=health, user_activities=user_activities, user_appointments=user_appointments, profile_picture=profile_picture)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    print(f"[DEBUG] Delete user route accessed by user_id: {session.get('user_id')}")
    
    # Check if current user is an admin
    current_user = User.query.get(session['user_id'])
    print(f"[DEBUG] Current user: {current_user}")
    print(f"[DEBUG] User is_admin: {current_user.is_admin if current_user else None}")
    
    if not current_user or not current_user.is_admin:
        print(f"[DEBUG] Access denied - user is not admin")
        return jsonify({'success': False, 'message': 'Admin access required.'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        print(f"[DEBUG] Target user to delete: {user}")
        
        # Prevent deleting the main admin (adilhasan)
        if user.username == 'adilhasan':
            print(f"[DEBUG] Cannot delete main admin account")
            return jsonify({'success': False, 'message': 'Cannot delete the main admin account.'}), 400
        
        # Prevent deleting yourself
        if user.id == session['user_id']:
            print(f"[DEBUG] Cannot delete yourself")
            return jsonify({'success': False, 'message': 'Cannot delete your own account.'}), 400
        
        username = user.username
        
        # Delete related data first to avoid foreign key constraints
        print(f"[DEBUG] Deleting related data for user {username}")
        
        # Delete activities
        Activity.query.filter_by(user_id=user_id).delete()
        print(f"[DEBUG] Deleted activities")
        
        # Delete appointments
        Appointment.query.filter_by(user_id=user_id).delete()
        print(f"[DEBUG] Deleted appointments")
        
        # Delete pill reminders
        PillReminder.query.filter_by(user_id=user_id).delete()
        print(f"[DEBUG] Deleted pill reminders")
        
        # Delete blood donations
        BloodDonor.query.filter_by(user_id=user_id).delete()
        print(f"[DEBUG] Deleted blood donations")
        
        # Delete insurances
        Insurance.query.filter_by(user_id=user_id).delete()
        print(f"[DEBUG] Deleted insurances")
        
        # Delete chat history
        ChatHistory.query.filter_by(user_id=user_id).delete()
        print(f"[DEBUG] Deleted chat history")
        
        # Delete notifications
        Notification.query.filter_by(user_id=user_id).delete()
        print(f"[DEBUG] Deleted notifications")
        
        # Delete blood requests
        BloodRequest.query.filter_by(user_id=user_id).delete()
        print(f"[DEBUG] Deleted blood requests")
        
        # Delete health reviews
        HealthReview.query.filter_by(user_id=user_id).delete()
        print(f"[DEBUG] Deleted health reviews")
        
        # Delete health details
        UserHealthDetail.query.filter_by(user_id=user_id).delete()
        print(f"[DEBUG] Deleted health details")
        
        # Delete backup data
        BackupData.query.filter_by(user_id=user_id).delete()
        print(f"[DEBUG] Deleted backup data")
        
        # Finally delete the user
        db.session.delete(user)
        db.session.commit()
        print(f"[DEBUG] User {username} deleted successfully")
        
        # Log the activity
        activity = Activity(user_id=session['user_id'], action=f'Deleted user: {username}')
        db.session.add(activity)
        db.session.commit()
        print(f"[DEBUG] Activity logged")
        
        return jsonify({'success': True, 'message': f'Successfully deleted user {username}.'})
    
    except Exception as e:
        print(f"[DEBUG] Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting user: {str(e)}'}), 500

@app.route('/admin/block_user/<int:user_id>', methods=['POST'])
@login_required
def block_user(user_id):
    # Check if current user is an admin
    current_user = User.query.get(session['user_id'])
    if not current_user or not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required.'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        
        # Prevent blocking the main admin (adilhasan)
        if user.username == 'adilhasan':
            return jsonify({'success': False, 'message': 'Cannot modify the main admin account.'}), 400
        
        user.blocked = not user.blocked
        action = 'blocked' if user.blocked else 'unblocked'
        db.session.commit()
        
        # Log the activity
        activity = Activity(user_id=user.id, action=f'{action.capitalize()} by {session["username"]}')
        db.session.add(activity)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Successfully {action} {user.username}.'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error toggling user block status: {str(e)}'}), 500

@app.route('/admin/promote_user/<int:user_id>', methods=['POST'])
@login_required
def promote_user(user_id):
    # Check if current user is an admin
    current_user = User.query.get(session['user_id'])
    if not current_user or not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required.'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        
        # Prevent promoting the main admin (adilhasan)
        if user.username == 'adilhasan':
            return jsonify({'success': False, 'message': 'Cannot modify the main admin account.'}), 400
        
        # Check if user is already an admin
        if user.is_admin:
            return jsonify({'success': False, 'message': 'User is already an admin.'}), 400
        
        # Promote user to admin
        user.is_admin = True
        db.session.commit()
        
        # Log the activity
        activity = Activity(user_id=user.id, action=f'Promoted to admin by {session["username"]}')
        db.session.add(activity)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Successfully promoted {user.username} to admin.'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error promoting user: {str(e)}'}), 500

@app.route('/admin/demote_user/<int:user_id>', methods=['POST'])
@login_required
def demote_user(user_id):
    # Check if current user is an admin
    current_user = User.query.get(session['user_id'])
    if not current_user or not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required.'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        
        # Prevent demoting the main admin (adilhasan)
        if user.username == 'adilhasan':
            return jsonify({'success': False, 'message': 'Cannot modify the main admin account.'}), 400
        
        # Check if user is not an admin
        if not user.is_admin:
            return jsonify({'success': False, 'message': 'User is not an admin.'}), 400
        
        # Demote user from admin
        user.is_admin = False
        db.session.commit()
        
        # Log the activity
        activity = Activity(user_id=user.id, action=f'Demoted from admin by {session["username"]}')
        db.session.add(activity)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Successfully removed admin privileges from {user.username}.'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error demoting user: {str(e)}'}), 500

@app.route('/admin/create_user', methods=['POST'])
@login_required
def create_user():
    print(f"[DEBUG] Create user route accessed by user_id: {session.get('user_id')}")
    
    # Check if current user is an admin
    current_user = User.query.get(session['user_id'])
    if not current_user or not current_user.is_admin:
        print(f"[DEBUG] Access denied - user is not admin")
        return jsonify({'success': False, 'message': 'Admin access required.'}), 403
    
    try:
        print(f"[DEBUG] Form data received: {request.form}")
        
        # Get form data
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        age = request.form.get('age')
        gender = request.form.get('gender', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        is_admin = request.form.get('is_admin', 'false').lower() == 'true'
        
        print(f"[DEBUG] Parsed form data:")
        print(f"  full_name: {full_name}")
        print(f"  username: {username}")
        print(f"  email: {email}")
        print(f"  password: {'*' * len(password) if password else 'None'}")
        print(f"  age: {age}")
        print(f"  gender: {gender}")
        print(f"  phone_number: {phone_number}")
        print(f"  is_admin: {is_admin}")
        
        # Validate required fields
        if not all([full_name, username, email, password]):
            print(f"[DEBUG] Validation failed - missing required fields")
            return jsonify({'success': False, 'message': 'Full name, username, email, and password are required.'}), 400
        
        # Check if username already exists
        if User.query.filter_by(username=username).first():
            print(f"[DEBUG] Username already exists: {username}")
            return jsonify({'success': False, 'message': 'Username already exists.'}), 400
        
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            print(f"[DEBUG] Email already exists: {email}")
            return jsonify({'success': False, 'message': 'Email already exists.'}), 400
        
        # Generate medical ID
        medical_id = generate_medical_id()
        print(f"[DEBUG] Generated medical ID: {medical_id}")
        
        # Hash password
        hashed_password = generate_password_hash(password)
        
        # Create new user
        new_user = User(
            medical_id=medical_id,
            username=username,
            full_name=full_name,
            email=email,
            password=hashed_password,
            age=age if age else None,
            gender=gender if gender else None,
            phone_number=phone_number if phone_number else None,
            is_admin=is_admin,
            blocked=False
        )
        
        print(f"[DEBUG] Created user object: {new_user}")
        db.session.add(new_user)
        db.session.commit()
        print(f"[DEBUG] User saved to database successfully")
        
        # Log the activity
        activity = Activity(user_id=session['user_id'], action=f'Created new user: {username}')
        db.session.add(activity)
        db.session.commit()
        print(f"[DEBUG] Activity logged successfully")
        
        return jsonify({
            'success': True, 
            'message': f'User {username} created successfully with Medical ID: {medical_id}'
        })
    
    except Exception as e:
        print(f"[DEBUG] Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error creating user: {str(e)}'}), 500

@app.route('/admin/download_user_data/<int:user_id>')
@login_required
def download_user_data(user_id):
    # Check if current user is an admin
    current_user = User.query.get(session['user_id'])
    if not current_user or not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required.'}), 403
    
    try:
        # Get the target user
        target_user = User.query.get_or_404(user_id)
        
        # Get all user data
        health = UserHealthDetail.query.filter_by(user_id=user_id).first()
        activities = Activity.query.filter_by(user_id=user_id).all()
        appointments = Appointment.query.filter_by(user_id=user_id).all()
        reminders = PillReminder.query.filter_by(user_id=user_id).all()
        blood_donations = BloodDonor.query.filter_by(user_id=user_id).all()
        insurances = Insurance.query.filter_by(user_id=user_id).all()
        chats = ChatHistory.query.filter_by(user_id=user_id).all()
        notifications = Notification.query.filter_by(user_id=user_id).all()
        blood_requests = BloodRequest.query.filter_by(user_id=user_id).all()
        health_reviews = HealthReview.query.filter_by(user_id=user_id).all()

        def serialize(model):
            if model is None:
                return None
            if isinstance(model, list):
                return [serialize(m) for m in model]
            d = {}
            for c in model.__table__.columns:
                value = getattr(model, c.name)
                # Handle datetime objects
                if hasattr(value, 'isoformat'):
                    d[c.name] = value.isoformat()
                else:
                    d[c.name] = value
            return d

        data = {
            'user': serialize(target_user),
            'health': serialize(health),
            'activities': serialize(activities),
            'appointments': serialize(appointments),
            'reminders': serialize(reminders),
            'blood_donations': serialize(blood_donations),
            'insurances': serialize(insurances),
            'chats': serialize(chats),
            'notifications': serialize(notifications),
            'blood_requests': serialize(blood_requests),
            'health_reviews': serialize(health_reviews),
            'export_info': {
                'exported_by': current_user.username,
                'export_date': datetime.now().isoformat(),
                'user_id': user_id,
                'username': target_user.username
            }
        }
        
        response = Response(json.dumps(data, indent=2), mimetype='application/json')
        response.headers['Content-Disposition'] = f'attachment; filename={target_user.username}_data.json'
        return response
    
    except Exception as e:
        print(f"[DEBUG] Exception in download_user_data: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error downloading user data: {str(e)}'}), 500

@app.route('/admin/log_download/<int:user_id>', methods=['POST'])
@login_required
def log_download(user_id):
    # Check if current user is an admin
    current_user = User.query.get(session['user_id'])
    if not current_user or not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required.'}), 403
    
    try:
        target_user = User.query.get_or_404(user_id)
        
        # Log the download activity
        activity = Activity(
            user_id=session['user_id'], 
            action=f'Downloaded data for user: {target_user.username} (ID: {user_id})'
        )
        db.session.add(activity)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Download logged successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error logging download: {str(e)}'}), 500

def send_email(to_email, subject, body):
    gmail_user = 'muhammedadilhasan@gmail.com'
    gmail_password = '12001200'
    msg = MIMEText(body, 'html')
    msg['Subject'] = subject
    msg['From'] = gmail_user
    msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, [to_email], msg.as_string())
        print(f'Reminder sent to {to_email}')
    except Exception as e:
        print(f'Failed to send email: {e}')

# Background reminder scheduler

def check_and_send_reminders():
    with app.app_context():
        now = datetime.now()
        # Query for appointments that have a reminder set and are in the future
        appts = Appointment.query.filter(
            Appointment.reminder_hours != None,
            Appointment.appointment_datetime > now
        ).all()
        
        for appt in appts:
            try:
                # Calculate the exact time the reminder should be sent
                reminder_dt = appt.appointment_datetime - timedelta(hours=appt.reminder_hours)
                
                # Check if the reminder time is now (within a 10-minute window to prevent missing it)
                if reminder_dt <= now < reminder_dt + timedelta(minutes=10):
                    user = User.query.get(appt.user_id)
                    if user and user.email:
                        # Send email notification
                        send_email(
                            user.email,
                            "Appointment Reminder",
                            f"<h3>Appointment Reminder</h3><p>Your appointment with Dr. {appt.doctor} ({appt.department}) is scheduled at {appt.appointment_datetime.strftime('%H:%M on %Y-%m-%d')}.</p>"
                        )
                        # Create in-app notification
                        notif = Notification(
                            user_id=appt.user_id,
                            message=f"Reminder: Your appointment with Dr. {appt.doctor} is at {appt.appointment_datetime.strftime('%H:%M on %Y-%m-%d')}."
                        )
                        db.session.add(notif)
                        db.session.commit()
            except Exception as e:
                print(f"Error processing reminder for appointment {appt.id}: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=check_and_send_reminders, trigger="interval", minutes=10)
scheduler.start()

@app.route('/notifications/read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != session['user_id']:
        return '', 403
    notif.is_read = True
    db.session.commit()
    return '', 204

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/mental_journal', methods=['GET', 'POST'])
@login_required
def mental_journal_page():
    response = None
    if request.method == 'POST':
        message = request.form.get('message')
        if message:
            prompt = f"You are a mental health support assistant. User says: {message}"
            response = generate_gemini_response(prompt)
            # Save the journal entry to ChatHistory
            chat = ChatHistory(user_id=session['user_id'], message=message, response=response)
            db.session.add(chat)
            # Log activity
            activity = Activity(user_id=session['user_id'], action=f'Used mental journal: {message[:50]}{"..." if len(message) > 50 else ""}')
            db.session.add(activity)
            db.session.commit()
    # Fetch journal history for the user
    journal_history = ChatHistory.query.filter_by(user_id=session['user_id']).order_by(ChatHistory.timestamp.desc()).all()
    return render_template('mental_journal.html', response=response, journal_history=journal_history)

@app.route('/mental_breathing')
@login_required
def mental_breathing():
    return render_template('mental_breathing.html')

@app.route('/mental_coloring')
@login_required
def mental_coloring():
    return render_template('mental_coloring.html')

@app.route('/mental_music')
@login_required
def mental_music():
    return render_template('mental_music.html')

@app.route('/mental_memory')
@login_required
def mental_memory():
    return render_template('mental_memory.html')

@app.route('/mental_drawing')
@login_required
def mental_drawing():
    return render_template('mental_drawing.html')

@app.route('/mental_quotes')
@login_required
def mental_quotes():
    return render_template('mental_quotes.html')

@app.route('/mental_resources')
@login_required
def mental_resources():
    return render_template('mental_resources.html')

@app.route('/mental_word_puzzle')
@login_required
def mental_word_puzzle():
    return render_template('mental_word_puzzle.html')

@app.route('/mental_prompt_writing')
@login_required
def mental_prompt_writing():
    return render_template('mental_prompt_writing.html')

@app.route('/suggest_resource', methods=['POST'])
def suggest_resource():
    data = request.get_json()
    name = data.get('name', '').strip()
    url = data.get('url', '').strip()
    description = data.get('description', '').strip()
    if not name or not url:
        return jsonify({'success': False, 'message': 'Name and URL are required.'}), 400
    suggestion = ResourceSuggestion(name=name, url=url, description=description)
    db.session.add(suggestion)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Thank you for your suggestion! It will be reviewed by our team.'})

@app.route('/exercise_tutorials')
@login_required
def exercise_tutorials():
    return render_template('exercise_tutorials.html')

@app.route('/diet_plan', methods=['GET', 'POST'])
@login_required
def diet_plan():
    bmi = session.get('user_bmi')
    exclude_foods = session.get('exclude_foods', '')
    if request.method == 'POST':
        exclude_foods = request.form.get('exclude_foods', '').strip()
        session['exclude_foods'] = exclude_foods
    return render_template('diet_plan.html', bmi=bmi, exclude_foods=exclude_foods)

@app.context_processor
def inject_profile_picture():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user and user.profile_picture and os.path.exists(os.path.join(app.static_folder, user.profile_picture)):
            return {'profile_picture': user.profile_picture}
    return {'profile_picture': 'profile_placeholder.svg'}

@app.route('/backup_data')
@login_required
def backup_data():
    user_id = session['user_id']
    user = User.query.get(user_id)
    health = UserHealthDetail.query.filter_by(user_id=user_id).first()
    activities = Activity.query.filter_by(user_id=user_id).all()
    appointments = Appointment.query.filter_by(user_id=user_id).all()
    reminders = PillReminder.query.filter_by(user_id=user_id).all()
    blood_donations = BloodDonor.query.filter_by(user_id=user_id).all()
    insurances = Insurance.query.filter_by(user_id=user_id).all()
    chats = ChatHistory.query.filter_by(user_id=user_id).all()
    notifications = Notification.query.filter_by(user_id=user_id).all()
    blood_requests = BloodRequest.query.filter_by(user_id=user_id).all()
    health_reviews = HealthReview.query.filter_by(user_id=user_id).all()

    def serialize(model):
        if model is None:
            return None
        if isinstance(model, list):
            return [serialize(m) for m in model]
        d = {}
        for c in model.__table__.columns:
            value = getattr(model, c.name)
            # Handle datetime objects
            if hasattr(value, 'isoformat'):
                d[c.name] = value.isoformat()
            else:
                d[c.name] = value
        return d

    data = {
        'user': serialize(user),
        'health': serialize(health),
        'activities': serialize(activities),
        'appointments': serialize(appointments),
        'reminders': serialize(reminders),
        'blood_donations': serialize(blood_donations),
        'insurances': serialize(insurances),
        'chats': serialize(chats),
        'notifications': serialize(notifications),
        'blood_requests': serialize(blood_requests),
        'health_reviews': serialize(health_reviews),
    }
    response = Response(json.dumps(data, indent=2), mimetype='application/json')
    response.headers['Content-Disposition'] = 'attachment; filename=backup_data.json'
    return response

@app.route('/create_backup', methods=['POST'])
@login_required
def create_backup():
    user_id = session['user_id']
    backup_name = request.form.get('backup_name', f'Backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    description = request.form.get('description', '')
    
    # Get all user data
    user = User.query.get(user_id)
    health = UserHealthDetail.query.filter_by(user_id=user_id).first()
    activities = Activity.query.filter_by(user_id=user_id).all()
    appointments = Appointment.query.filter_by(user_id=user_id).all()
    reminders = PillReminder.query.filter_by(user_id=user_id).all()
    blood_donations = BloodDonor.query.filter_by(user_id=user_id).all()
    insurances = Insurance.query.filter_by(user_id=user_id).all()
    chats = ChatHistory.query.filter_by(user_id=user_id).all()
    notifications = Notification.query.filter_by(user_id=user_id).all()
    blood_requests = BloodRequest.query.filter_by(user_id=user_id).all()
    health_reviews = HealthReview.query.filter_by(user_id=user_id).all()

    def serialize(model):
        if model is None:
            return None
        if isinstance(model, list):
            return [serialize(m) for m in model]
        d = {}
        for c in model.__table__.columns:
            value = getattr(model, c.name)
            # Handle datetime objects
            if hasattr(value, 'isoformat'):
                d[c.name] = value.isoformat()
            else:
                d[c.name] = value
        return d

    data = {
        'user': serialize(user),
        'health': serialize(health),
        'activities': serialize(activities),
        'appointments': serialize(appointments),
        'reminders': serialize(reminders),
        'blood_donations': serialize(blood_donations),
        'insurances': serialize(insurances),
        'chats': serialize(chats),
        'notifications': serialize(notifications),
        'blood_requests': serialize(blood_requests),
        'health_reviews': serialize(health_reviews),
    }
    
    # Store backup in database
    backup = BackupData(
        user_id=user_id,
        backup_name=backup_name,
        backup_data=json.dumps(data, indent=2),
        description=description,
        is_auto_backup=False
    )
    db.session.add(backup)
    db.session.commit()
    
    flash(f'Backup "{backup_name}" created successfully!', 'success')
    return redirect(url_for('view_backups'))

@app.route('/view_backups')
@login_required
def view_backups():
    user_id = session['user_id']
    backups = BackupData.query.filter_by(user_id=user_id).order_by(BackupData.created_at.desc()).all()
    return render_template('view_backups.html', backups=backups)

@app.route('/download_backup/<int:backup_id>')
@login_required
def download_backup(backup_id):
    backup = BackupData.query.get_or_404(backup_id)
    if backup.user_id != session['user_id']:
        flash('Access denied.', 'danger')
        return redirect(url_for('view_backups'))
    
    response = Response(backup.backup_data, mimetype='application/json')
    response.headers['Content-Disposition'] = f'attachment; filename={backup.backup_name}.json'
    return response

@app.route('/restore_backup/<int:backup_id>', methods=['POST'])
@login_required
def restore_backup(backup_id):
    backup = BackupData.query.get_or_404(backup_id)
    if backup.user_id != session['user_id']:
        flash('Access denied.', 'danger')
        return redirect(url_for('view_backups'))
    
    try:
        data = json.loads(backup.backup_data)
        user_id = session['user_id']
        
        def parse_datetime(dt_str):
            if dt_str and isinstance(dt_str, str):
                try:
                    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                except:
                    return None
            return dt_str
        
        # Restore user
        user_data = data.get('user')
        if user_data:
            user = User.query.get(user_id)
            user.full_name = user_data.get('full_name', user.full_name)
            user.email = user_data.get('email', user.email)
            user.age = user_data.get('age', user.age)
            user.gender = user_data.get('gender', user.gender)
            user.phone_number = user_data.get('phone_number', user.phone_number)
            user.profile_picture = user_data.get('profile_picture', user.profile_picture)
            db.session.commit()
        
        # Restore health
        health_data = data.get('health')
        if health_data:
            health = UserHealthDetail.query.filter_by(user_id=user_id).first()
            if not health:
                health = UserHealthDetail(user_id=user_id)
                db.session.add(health)
            health.height_cm = health_data.get('height_cm')
            health.weight_kg = health_data.get('weight_kg')
            health.blood_group = health_data.get('blood_group')
            health.allergies = health_data.get('allergies')
            health.chronic_conditions = health_data.get('chronic_conditions')
            health.medications = health_data.get('medications')
            db.session.commit()
        
        # Restore activities
        Activity.query.filter_by(user_id=user_id).delete()
        for a in data.get('activities', []):
            db.session.add(Activity(
                user_id=user_id, 
                action=a.get('action'), 
                timestamp=parse_datetime(a.get('timestamp'))
            ))
        
        # Restore appointments (with backward compatibility)
        Appointment.query.filter_by(user_id=user_id).delete()
        for ap in data.get('appointments', []):
            try:
                if 'appointment_datetime' in ap and ap['appointment_datetime']:
                    appt_dt = datetime.fromisoformat(ap['appointment_datetime'])
                elif 'date' in ap and 'time' in ap: # Legacy format
                    appt_dt = datetime.strptime(f"{ap['date']} {ap['time']}", "%Y-%m-%d %H:%M")
                else:
                    continue # Skip if no valid time data
                
                new_appt = Appointment(
                    user_id=user_id,
                    appointment_datetime=appt_dt,
                    reason=ap.get('reason'),
                    doctor=ap.get('doctor'),
                    department=ap.get('department'),
                    reminder_hours=ap.get('reminder_hours') or ap.get('reminder_time') # Backward compatible
                )
                db.session.add(new_appt)
            except (ValueError, TypeError):
                continue # Skip invalid entries
        
        # Restore reminders (with backward compatibility)
        PillReminder.query.filter_by(user_id=user_id).delete()
        for r in data.get('reminders', []):
            try:
                time_str = r.get('reminder_time') or r.get('time')
                if not time_str: continue
                # Handle both HH:MM:SS and HH:MM formats
                reminder_t = datetime.strptime(time_str.split('.')[0], '%H:%M:%S' if ':' in time_str and len(time_str.split(':')) > 2 else '%H:%M').time()

                new_reminder = PillReminder(
                    user_id=user_id, 
                    pill_name=r.get('pill_name'), 
                    dosage=r.get('dosage'), 
                    reminder_time=reminder_t
                )
                db.session.add(new_reminder)
            except (ValueError, TypeError):
                continue

        # Restore blood donations (with backward compatibility)
        BloodDonor.query.filter_by(user_id=user_id).delete()
        for d in data.get('blood_donations', []):
            try:
                last_donation_date = None
                if d.get('last_donation'):
                    last_donation_date = datetime.fromisoformat(d['last_donation']).date()
                
                new_donor = BloodDonor(
                    user_id=user_id, 
                    blood_group=d.get('blood_group'), 
                    last_donation=last_donation_date
                )
                db.session.add(new_donor)
            except (ValueError, TypeError):
                continue
        
        # Restore insurances (with backward compatibility)
        Insurance.query.filter_by(user_id=user_id).delete()
        for ins in data.get('insurances', []):
            try:
                valid_until_date = None
                if ins.get('valid_until'):
                    valid_until_date = datetime.fromisoformat(ins['valid_until']).date()
                
                new_insurance = Insurance(
                    user_id=user_id, 
                    provider=ins.get('provider'), 
                    policy_number=ins.get('policy_number'), 
                    valid_until=valid_until_date, 
                    type=ins.get('type')
                )
                db.session.add(new_insurance)
            except (ValueError, TypeError):
                continue

        # Restore chats
        ChatHistory.query.filter_by(user_id=user_id).delete()
        for c in data.get('chats', []):
            db.session.add(ChatHistory(
                user_id=user_id, 
                message=c.get('message'), 
                response=c.get('response'), 
                timestamp=parse_datetime(c.get('timestamp'))
            ))
        
        # Restore notifications
        Notification.query.filter_by(user_id=user_id).delete()
        for n in data.get('notifications', []):
            db.session.add(Notification(
                user_id=user_id, 
                message=n.get('message'), 
                is_read=n.get('is_read'), 
                timestamp=parse_datetime(n.get('timestamp'))
            ))
        
        # Restore blood requests
        BloodRequest.query.filter_by(user_id=user_id).delete()
        for br in data.get('blood_requests', []):
            db.session.add(BloodRequest(
                user_id=user_id, 
                blood_group=br.get('blood_group'), 
                units_needed=br.get('units_needed'), 
                reason=br.get('reason'), 
                contact_info=br.get('contact_info'), 
                timestamp=parse_datetime(br.get('timestamp')), 
                accepted_by=br.get('accepted_by')
            ))
        
        # Restore health reviews
        HealthReview.query.filter_by(user_id=user_id).delete()
        for hr in data.get('health_reviews', []):
            db.session.add(HealthReview(
                user_id=user_id, 
                feature=hr.get('feature'), 
                status=hr.get('status'), 
                percentage=hr.get('percentage'), 
                timestamp=parse_datetime(hr.get('timestamp'))
            ))
        
        db.session.commit()
        flash(f'Data restored successfully from backup "{backup.backup_name}"!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring data: {e}', 'danger')
    return redirect(url_for('view_backups'))

@app.route('/delete_backup/<int:backup_id>', methods=['POST'])
@login_required
def delete_backup(backup_id):
    backup = BackupData.query.get_or_404(backup_id)
    if backup.user_id != session['user_id']:
        flash('Access denied.', 'danger')
        return redirect(url_for('view_backups'))
    
    backup_name = backup.backup_name
    db.session.delete(backup)
    db.session.commit()
    flash(f'Backup "{backup_name}" deleted successfully!', 'success')
    return redirect(url_for('view_backups'))

@app.route('/auto_backup')
@login_required
def auto_backup():
    """Create automatic backup for user"""
    user_id = session['user_id']
    
    # Get all user data
    user = User.query.get(user_id)
    health = UserHealthDetail.query.filter_by(user_id=user_id).first()
    activities = Activity.query.filter_by(user_id=user_id).all()
    appointments = Appointment.query.filter_by(user_id=user_id).all()
    reminders = PillReminder.query.filter_by(user_id=user_id).all()
    blood_donations = BloodDonor.query.filter_by(user_id=user_id).all()
    insurances = Insurance.query.filter_by(user_id=user_id).all()
    chats = ChatHistory.query.filter_by(user_id=user_id).all()
    notifications = Notification.query.filter_by(user_id=user_id).all()
    blood_requests = BloodRequest.query.filter_by(user_id=user_id).all()
    health_reviews = HealthReview.query.filter_by(user_id=user_id).all()

    def serialize(model):
        if model is None:
            return None
        if isinstance(model, list):
            return [serialize(m) for m in model]
        d = {}
        for c in model.__table__.columns:
            value = getattr(model, c.name)
            # Handle datetime objects
            if hasattr(value, 'isoformat'):
                d[c.name] = value.isoformat()
            else:
                d[c.name] = value
        return d

    data = {
        'user': serialize(user),
        'health': serialize(health),
        'activities': serialize(activities),
        'appointments': serialize(appointments),
        'reminders': serialize(reminders),
        'blood_donations': serialize(blood_donations),
        'insurances': serialize(insurances),
        'chats': serialize(chats),
        'notifications': serialize(notifications),
        'blood_requests': serialize(blood_requests),
        'health_reviews': serialize(health_reviews),
    }
    
    # Store automatic backup in database
    backup_name = f'Auto_Backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    backup = BackupData(
        user_id=user_id,
        backup_name=backup_name,
        backup_data=json.dumps(data, indent=2),
        description='Automatic backup created by system',
        is_auto_backup=True
    )
    db.session.add(backup)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Automatic backup created successfully'})

@app.route('/restore_data', methods=['POST'])
@login_required
def restore_data():
    from flask import request
    import json
    from datetime import datetime
    file = request.files.get('restore_file')
    if not file:
        flash('No file uploaded.', 'danger')
        return redirect(url_for('settings_page'))
    try:
        data = json.load(file)
        user_id = session['user_id']
        
        def parse_datetime(dt_str):
            if dt_str and isinstance(dt_str, str):
                try:
                    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                except:
                    return None
            return dt_str
        
        # Restore user
        user_data = data.get('user')
        if user_data:
            user = User.query.get(user_id)
            user.full_name = user_data.get('full_name', user.full_name)
            user.email = user_data.get('email', user.email)
            user.age = user_data.get('age', user.age)
            user.gender = user_data.get('gender', user.gender)
            user.phone_number = user_data.get('phone_number', user.phone_number)
            user.profile_picture = user_data.get('profile_picture', user.profile_picture)
            db.session.commit()
        
        # Restore health
        health_data = data.get('health')
        if health_data:
            health = UserHealthDetail.query.filter_by(user_id=user_id).first()
            if not health:
                health = UserHealthDetail(user_id=user_id)
                db.session.add(health)
            health.height_cm = health_data.get('height_cm')
            health.weight_kg = health_data.get('weight_kg')
            health.blood_group = health_data.get('blood_group')
            health.allergies = health_data.get('allergies')
            health.chronic_conditions = health_data.get('chronic_conditions')
            health.medications = health_data.get('medications')
            db.session.commit()
        
        # Restore activities
        Activity.query.filter_by(user_id=user_id).delete()
        for a in data.get('activities', []):
            db.session.add(Activity(
                user_id=user_id, 
                action=a.get('action'), 
                timestamp=parse_datetime(a.get('timestamp'))
            ))
        
        # Restore appointments
        Appointment.query.filter_by(user_id=user_id).delete()
        for ap in data.get('appointments', []):
            db.session.add(Appointment(
                user_id=user_id, 
                date=ap.get('date'), 
                time=ap.get('time'), 
                reason=ap.get('reason'), 
                doctor=ap.get('doctor'), 
                department=ap.get('department'), 
                reminder_time=ap.get('reminder_time')
            ))
        
        # Restore reminders
        PillReminder.query.filter_by(user_id=user_id).delete()
        for r in data.get('reminders', []):
            db.session.add(PillReminder(
                user_id=user_id, 
                pill_name=r.get('pill_name'), 
                dosage=r.get('dosage'), 
                time=r.get('time')
            ))
        
        # Restore blood donations
        BloodDonor.query.filter_by(user_id=user_id).delete()
        for d in data.get('blood_donations', []):
            db.session.add(BloodDonor(
                user_id=user_id, 
                blood_group=d.get('blood_group'), 
                last_donation=d.get('last_donation')
            ))
        
        # Restore insurances
        Insurance.query.filter_by(user_id=user_id).delete()
        for ins in data.get('insurances', []):
            db.session.add(Insurance(
                user_id=user_id, 
                provider=ins.get('provider'), 
                policy_number=ins.get('policy_number'), 
                valid_until=ins.get('valid_until'), 
                type=ins.get('type')
            ))
        
        # Restore chats
        ChatHistory.query.filter_by(user_id=user_id).delete()
        for c in data.get('chats', []):
            db.session.add(ChatHistory(
                user_id=user_id, 
                message=c.get('message'), 
                response=c.get('response'), 
                timestamp=parse_datetime(c.get('timestamp'))
            ))
        
        # Restore notifications
        Notification.query.filter_by(user_id=user_id).delete()
        for n in data.get('notifications', []):
            db.session.add(Notification(
                user_id=user_id, 
                message=n.get('message'), 
                is_read=n.get('is_read'), 
                timestamp=parse_datetime(n.get('timestamp'))
            ))
        
        # Restore blood requests
        BloodRequest.query.filter_by(user_id=user_id).delete()
        for br in data.get('blood_requests', []):
            db.session.add(BloodRequest(
                user_id=user_id, 
                blood_group=br.get('blood_group'), 
                units_needed=br.get('units_needed'), 
                reason=br.get('reason'), 
                contact_info=br.get('contact_info'), 
                timestamp=parse_datetime(br.get('timestamp')), 
                accepted_by=br.get('accepted_by')
            ))
        
        # Restore health reviews
        HealthReview.query.filter_by(user_id=user_id).delete()
        for hr in data.get('health_reviews', []):
            db.session.add(HealthReview(
                user_id=user_id, 
                feature=hr.get('feature'), 
                status=hr.get('status'), 
                percentage=hr.get('percentage'), 
                timestamp=parse_datetime(hr.get('timestamp'))
            ))
        
        db.session.commit()
        flash('Data restored successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring data: {e}', 'danger')
    return redirect(url_for('settings_page'))

@app.route('/admin/restore_data', methods=['POST'])
@login_required
def admin_restore_data():
    if not session.get('is_admin'):
        flash('Admin access required.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    file = request.files.get('admin_restore_file')
    if not file:
        flash('No file uploaded.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    try:
        all_users_data = json.load(file)
        users_data = all_users_data if isinstance(all_users_data, list) else [all_users_data]

        for user_data in users_data:
            user_info = user_data.get('user')
            if not user_info or not user_info.get('id'):
                continue
            
            user_id = user_info['id']
            
            # Check if user exists, if not create them
            existing_user = User.query.get(user_id)
            if not existing_user:
                # Create new user with a default password
                from werkzeug.security import generate_password_hash
                default_password = generate_password_hash('RestoredUser@123')
                medical_id = generate_medical_id()
                new_user = User(
                    id=user_id,
                    medical_id=medical_id,
                    username=user_info.get('username', f'user_{user_id}'),
                    full_name=user_info.get('full_name', ''),
                    email=user_info.get('email', ''),
                    password=default_password,
                    age=user_info.get('age'),
                    gender=user_info.get('gender'),
                    phone_number=user_info.get('phone_number'),
                    is_admin=user_info.get('is_admin', False),
                    blocked=user_info.get('blocked', False),
                    profile_picture=user_info.get('profile_picture')
                )
                db.session.add(new_user)
            else:
                # Update existing user
                existing_user.full_name = user_info.get('full_name', existing_user.full_name)
                existing_user.email = user_info.get('email', existing_user.email)
                existing_user.age = user_info.get('age', existing_user.age)
                existing_user.gender = user_info.get('gender', existing_user.gender)
                existing_user.phone_number = user_info.get('phone_number', existing_user.phone_number)
                existing_user.is_admin = user_info.get('is_admin', existing_user.is_admin)
                existing_user.blocked = user_info.get('blocked', existing_user.blocked)
                existing_user.profile_picture = user_info.get('profile_picture', existing_user.profile_picture)

            # Restore health details
            health_data = user_data.get('health')
            if health_data:
                health = UserHealthDetail.query.filter_by(user_id=user_id).first()
                if not health:
                    health = UserHealthDetail(user_id=user_id)
                    db.session.add(health)
                health.height_cm = health_data.get('height_cm')
                health.weight_kg = health_data.get('weight_kg')
                health.blood_group = health_data.get('blood_group')
                health.allergies = health_data.get('allergies')
                health.chronic_conditions = health_data.get('chronic_conditions')
                health.medications = health_data.get('medications')

            # Restore activities
            Activity.query.filter_by(user_id=user_id).delete()
            for a in user_data.get('activities', []):
                try:
                    timestamp = datetime.fromisoformat(a['timestamp']) if a.get('timestamp') else datetime.now()
                    db.session.add(Activity(
                        user_id=user_id, 
                        action=a.get('action'), 
                        timestamp=timestamp
                    ))
                except (ValueError, TypeError):
                    continue

            # Appointments (with backward compatibility)
            Appointment.query.filter_by(user_id=user_id).delete()
            for ap in user_data.get('appointments', []):
                try:
                    if 'appointment_datetime' in ap and ap['appointment_datetime']:
                        appt_dt = datetime.fromisoformat(ap['appointment_datetime'])
                    elif 'date' in ap and 'time' in ap: # Legacy format
                        appt_dt = datetime.strptime(f"{ap['date']} {ap['time']}", "%Y-%m-%d %H:%M")
                    else:
                        continue
                    
                    new_appt = Appointment(
                        user_id=user_id,
                        appointment_datetime=appt_dt,
                        reason=ap.get('reason'),
                        doctor=ap.get('doctor'),
                        department=ap.get('department'),
                        reminder_hours=ap.get('reminder_hours') or ap.get('reminder_time')
                    )
                    db.session.add(new_appt)
                except (ValueError, TypeError):
                    continue

            # Reminders (with backward compatibility)
            PillReminder.query.filter_by(user_id=user_id).delete()
            for r in user_data.get('reminders', []):
                try:
                    time_str = r.get('reminder_time') or r.get('time')
                    if not time_str: continue
                    reminder_t = datetime.strptime(time_str.split('.')[0], '%H:%M:%S' if ':' in time_str and len(time_str.split(':')) > 2 else '%H:%M').time()
                    
                    new_reminder = PillReminder(
                        user_id=user_id, pill_name=r.get('pill_name'),
                        dosage=r.get('dosage'), reminder_time=reminder_t
                    )
                    db.session.add(new_reminder)
                except (ValueError, TypeError):
                    continue

            # Blood donations (with backward compatibility)
            BloodDonor.query.filter_by(user_id=user_id).delete()
            for d in user_data.get('blood_donations', []):
                try:
                    last_donation_date = datetime.fromisoformat(d['last_donation']).date() if d.get('last_donation') else None
                    new_donor = BloodDonor(
                        user_id=user_id, blood_group=d.get('blood_group'), last_donation=last_donation_date
                    )
                    db.session.add(new_donor)
                except (ValueError, TypeError):
                    continue

            # Insurances (with backward compatibility)
            Insurance.query.filter_by(user_id=user_id).delete()
            for ins in user_data.get('insurances', []):
                try:
                    valid_until_date = datetime.fromisoformat(ins['valid_until']).date() if ins.get('valid_until') else None
                    new_insurance = Insurance(
                        user_id=user_id, provider=ins.get('provider'),
                        policy_number=ins.get('policy_number'), valid_until=valid_until_date,
                        type=ins.get('type')
                    )
                    db.session.add(new_insurance)
                except (ValueError, TypeError):
                    continue

            # Restore chats
            ChatHistory.query.filter_by(user_id=user_id).delete()
            for c in user_data.get('chats', []):
                try:
                    timestamp = datetime.fromisoformat(c['timestamp']) if c.get('timestamp') else datetime.now()
                    db.session.add(ChatHistory(
                        user_id=user_id, 
                        message=c.get('message'), 
                        response=c.get('response'), 
                        timestamp=timestamp
                    ))
                except (ValueError, TypeError):
                    continue

            # Restore notifications
            Notification.query.filter_by(user_id=user_id).delete()
            for n in user_data.get('notifications', []):
                try:
                    timestamp = datetime.fromisoformat(n['timestamp']) if n.get('timestamp') else datetime.now()
                    db.session.add(Notification(
                        user_id=user_id, 
                        message=n.get('message'), 
                        is_read=n.get('is_read', False), 
                        timestamp=timestamp
                    ))
                except (ValueError, TypeError):
                    continue

            # Restore blood requests
            BloodRequest.query.filter_by(user_id=user_id).delete()
            for br in user_data.get('blood_requests', []):
                try:
                    timestamp = datetime.fromisoformat(br['timestamp']) if br.get('timestamp') else datetime.now()
                    db.session.add(BloodRequest(
                        user_id=user_id, 
                        blood_group=br.get('blood_group'), 
                        units_needed=br.get('units_needed'), 
                        reason=br.get('reason'), 
                        contact_info=br.get('contact_info'), 
                        timestamp=timestamp, 
                        accepted_by=br.get('accepted_by')
                    ))
                except (ValueError, TypeError):
                    continue

            # Restore health reviews
            HealthReview.query.filter_by(user_id=user_id).delete()
            for hr in user_data.get('health_reviews', []):
                try:
                    timestamp = datetime.fromisoformat(hr['timestamp']) if hr.get('timestamp') else datetime.now()
                    db.session.add(HealthReview(
                        user_id=user_id, 
                        feature=hr.get('feature'), 
                        status=hr.get('status'), 
                        percentage=hr.get('percentage'), 
                        timestamp=timestamp
                    ))
                except (ValueError, TypeError):
                    continue
            
            db.session.commit()
            
        flash('All user data restored successfully! Default password for new users: RestoredUser@123', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring data: {e}', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/review-status')
@login_required
def review_status():
    from datetime import datetime, timedelta
    user_obj = User.query.get(session['user_id'])
    health = UserHealthDetail.query.filter_by(user_id=user_obj.id).first()
    # Use real user data
    user = {
        'name': user_obj.full_name or user_obj.username,
        'age': user_obj.age or 'N/A',
        'gender': user_obj.gender or 'N/A',
        'height_cm': health.height_cm if health and health.height_cm else None,
        'weight_kg': health.weight_kg if health and health.weight_kg else None,
    }
    # Calculate BMI if possible
    if user['height_cm'] and user['weight_kg']:
        bmi = round(float(user['weight_kg']) / ((float(user['height_cm'])/100) ** 2), 1)
        if bmi < 18.5:
            bmi_category = 'Underweight'
        elif bmi < 25:
            bmi_category = 'Normal'
        elif bmi < 30:
            bmi_category = 'Overweight'
        else:
            bmi_category = 'Obese'
    else:
        bmi = 'N/A'
        bmi_category = 'N/A'
    # Static vitals/labs for now
    vitals = {
        'heart_rate': 92,
        'bp_systolic': 145,
        'bp_diastolic': 95,
        'blood_sugar_fasting': 130,
        'blood_sugar_random': 180,
        'spo2': 97,
        'temperature': 98.6,
    }
    labs = {
        'cholesterol_hdl': 38,
        'cholesterol_ldl': 170,
        'hemoglobin': 11.2,
        'vitamin_d': 18,
        'vitamin_b12': 210,
    }
    trends = [
        {'date': '2024-06-20', 'heart_rate': 90, 'bp': '140/90', 'sugar': 125, 'spo2': 98, 'temp': 98.4},
        {'date': '2024-06-13', 'heart_rate': 88, 'bp': '135/88', 'sugar': 120, 'spo2': 97, 'temp': 98.2},
        {'date': '2024-06-06', 'heart_rate': 85, 'bp': '130/85', 'sugar': 110, 'spo2': 99, 'temp': 98.0},
    ]
    abnormal = []
    if not (60 <= vitals['heart_rate'] <= 100): abnormal.append('Heart Rate')
    if not (90 <= vitals['bp_systolic'] <= 120): abnormal.append('Blood Pressure')
    if not (70 <= vitals['bp_diastolic'] <= 80): abnormal.append('Blood Pressure')
    if not (70 <= vitals['blood_sugar_fasting'] <= 99): abnormal.append('Blood Sugar (Fasting)')
    if not (80 <= vitals['blood_sugar_random'] <= 140): abnormal.append('Blood Sugar (Random)')
    if not (95 <= vitals['spo2'] <= 100): abnormal.append('SpO2')
    if not (97 <= vitals['temperature'] <= 99): abnormal.append('Temperature')
    if not (40 <= labs['cholesterol_hdl'] <= 60): abnormal.append('HDL Cholesterol')
    if not (0 <= labs['cholesterol_ldl'] <= 100): abnormal.append('LDL Cholesterol')
    if not (13.5 <= labs['hemoglobin'] <= 17.5): abnormal.append('Hemoglobin')
    if not (20 <= labs['vitamin_d'] <= 50): abnormal.append('Vitamin D')
    if not (200 <= labs['vitamin_b12'] <= 900): abnormal.append('Vitamin B12')
    last_review = datetime.strptime(trends[0]['date'], '%Y-%m-%d')
    next_review = last_review + timedelta(days=7)
    recommendations = {
        'diet': 'Increase fiber and reduce saturated fat intake.',
        'exercise': 'Aim for at least 30 minutes of brisk walking daily.',
        'sleep': 'Maintain a regular sleep schedule with 7-8 hours per night.'
    }
    return render_template('review_status.html', user=user, bmi=bmi, bmi_category=bmi_category, vitals=vitals, labs=labs, trends=trends, abnormal=abnormal, recommendations=recommendations, last_review=last_review.date(), next_review=next_review.date())

@app.route('/test_notification', methods=['POST'])
@login_required
def test_notification():
    import traceback
    user = User.query.get(session['user_id'])
    print(f"[DEBUG] Sending test notification to user: {user.id}, email: {user.email}")
    try:
        notif = Notification(user_id=user.id, message='This is a test notification!')
        db.session.add(notif)
        db.session.commit()
        # Optionally send email
        if user.email:
            try:
                send_email(user.email, 'Test Notification', '<h3>This is a test notification from Healthcare AI.</h3>')
            except Exception as e:
                print('[ERROR] Email send failed:', e)
                traceback.print_exc()
                return jsonify({'success': True, 'message': f'Test notification created. Email failed: {e}'})
        return jsonify({'success': True, 'message': 'Test notification sent! Check your notifications and email.'})
    except Exception as e:
        print('[ERROR] Test notification failed:', e)
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Failed to create notification: {e}'})

def send_sms(to_number, message):
    account_sid = 'AC79fb1dedd2bef4461f10f4886bd099d0'
    auth_token = 'a5d6438cb918e389724733cafac94a44'
    from_number = '+18312825388'  # Your Twilio number
    client = Client(account_sid, auth_token)
    try:
        if not to_number.startswith('+'):
            to_number = '+91' + to_number
        print(f"[DEBUG] Sending SMS to {to_number} from {from_number}")
        client.messages.create(
            body=message,
            from_=from_number,
            to=to_number,
            provide_feedback=False  # This will not affect the trial message, but is best practice for production
        )
        print(f"SMS sent to {to_number}")
    except Exception as e:
        print(f"Failed to send SMS: {e}")

@app.route('/test_sms', methods=['POST'])
@login_required
def test_sms():
    import traceback
    user = User.query.get(session['user_id'])
    print(f"[DEBUG] Sending test SMS to user: {user.id}, phone: {user.phone_number}")
    print(f"[DEBUG] TWILIO_ACCOUNT_SID: {os.getenv('TWILIO_ACCOUNT_SID')}")
    print(f"[DEBUG] TWILIO_AUTH_TOKEN: {os.getenv('TWILIO_AUTH_TOKEN')}")
    print(f"[DEBUG] TWILIO_PHONE_NUMBER: {os.getenv('TWILIO_PHONE_NUMBER')}")
    if not user.phone_number:
        print('[ERROR] No phone number set in user profile.')
        return jsonify({'success': False, 'message': 'No phone number set in your profile.'})
    try:
        send_sms(user.phone_number, 'This is a test SMS from Healthcare AI.')
        return jsonify({'success': True, 'message': 'Test SMS sent!'})
    except Exception as e:
        print('[ERROR] Test SMS failed:', e)
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Failed to send SMS: {e}'})

@app.route('/debug_user_status')
@login_required
def debug_user_status():
    """Debug route to check current user's admin status"""
    current_user = User.query.get(session['user_id'])
    return jsonify({
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'session_is_admin': session.get('is_admin'),
        'db_is_admin': current_user.is_admin if current_user else None,
        'user_exists': current_user is not None
    })

@app.route('/test_route')
def test_route():
    return "Test route is working!"

@app.route('/debug_admin_status')
@login_required
def debug_admin_status():
    """Debug route to check current user's admin status and session"""
    current_user = User.query.get(session['user_id'])
    return jsonify({
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'session_is_admin': session.get('is_admin'),
        'db_is_admin': current_user.is_admin if current_user else None,
        'user_exists': current_user is not None,
        'user_details': {
            'id': current_user.id if current_user else None,
            'username': current_user.username if current_user else None,
            'full_name': current_user.full_name if current_user else None,
            'is_admin': current_user.is_admin if current_user else None,
            'blocked': current_user.blocked if current_user else None
        } if current_user else None
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print(app.url_map)
    print('GOOGLE_API_KEY:', GOOGLE_API_KEY)
    app.run(debug=True)