from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# SQLAlchemy instance (to be initialized in app.py)
db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medical_id = db.Column(db.String(12), unique=True, nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    full_name = db.Column(db.String(150), nullable=True)
    email = db.Column(db.String(150), unique=True, nullable=True)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    blocked = db.Column(db.Boolean, default=False)
    profile_picture = db.Column(db.String(255), nullable=True)
    activities = db.relationship('Activity', backref='user', lazy=True)

class BackupData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    backup_name = db.Column(db.String(200), nullable=False)
    backup_data = db.Column(db.Text, nullable=False)  # JSON data as text
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    description = db.Column(db.String(500), nullable=True)
    is_auto_backup = db.Column(db.Boolean, default=False)  # True for automatic backups
    user = db.relationship('User', backref='backups')

class HealthReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    feature = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(200), nullable=False)
    percentage = db.Column(db.Float, nullable=True)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    appointment_datetime = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(200), nullable=True)
    doctor = db.Column(db.String(100), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    reminder_hours = db.Column(db.Integer, nullable=True)

class PillReminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pill_name = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(50), nullable=False)
    reminder_time = db.Column(db.Time, nullable=False)

class BloodDonor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blood_group = db.Column(db.String(5), nullable=False)
    last_donation = db.Column(db.Date, nullable=True)
    
    # Relationship to get the user information
    user = db.relationship('User', backref='blood_donations')

class Insurance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    provider = db.Column(db.String(100), nullable=False)
    policy_number = db.Column(db.String(100), nullable=False)
    valid_until = db.Column(db.Date, nullable=True)
    type = db.Column(db.String(20), nullable=False, default='Health')

class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

class UserHealthDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    height_cm = db.Column(db.Float, nullable=True)
    weight_kg = db.Column(db.Float, nullable=True)
    blood_group = db.Column(db.String(5), nullable=True)
    allergies = db.Column(db.String(255), nullable=True)
    chronic_conditions = db.Column(db.String(255), nullable=True)
    medications = db.Column(db.String(255), nullable=True)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

class BloodRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blood_group = db.Column(db.String(5), nullable=False)
    units_needed = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    contact_info = db.Column(db.String(150), nullable=True)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    accepted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # user_id of donor 
    
    # Relationship to get the accepted user information
    accepted_by_user = db.relationship('User', foreign_keys=[accepted_by], backref='accepted_donations')

class ResourceSuggestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    description = db.Column(db.String(400))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed = db.Column(db.Boolean, default=False) 