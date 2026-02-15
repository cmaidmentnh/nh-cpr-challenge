"""Database models for NH CPR Challenge."""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Executive Councilors (2025-2026)
COUNCILORS = {
    1: {'name': 'Joseph Kenney', 'party': 'R'},
    2: {'name': 'Karen Liot Hill', 'party': 'D'},
    3: {'name': 'Janet Stevens', 'party': 'R'},
    4: {'name': 'John Stephen', 'party': 'R'},
    5: {'name': 'Dave Wheeler', 'party': 'R'},
}

# District colors for map
DISTRICT_COLORS = {
    1: '#2563eb',  # Blue
    2: '#059669',  # Green
    3: '#d97706',  # Amber
    4: '#dc2626',  # Red
    5: '#7c3aed',  # Purple
}


class Training(db.Model):
    __tablename__ = 'trainings'

    id = db.Column(db.Integer, primary_key=True)
    host_name = db.Column(db.String(200), nullable=False)
    host_email = db.Column(db.String(200), nullable=False)
    host_phone = db.Column(db.String(20))
    organization = db.Column(db.String(200))
    location_name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(300))
    city = db.Column(db.String(100))
    zip_code = db.Column(db.String(10))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    district = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(10))
    end_time = db.Column(db.String(10))
    capacity = db.Column(db.Integer, default=30)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    materials_needed = db.Column(db.Boolean, default=False)
    host_token = db.Column(db.String(64), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    rsvps = db.relationship('RSVP', backref='training', lazy='dynamic')
    attendances = db.relationship('Attendance', backref='training', lazy='dynamic')

    @property
    def spots_remaining(self):
        return max(0, self.capacity - self.rsvps.count())

    @property
    def is_full(self):
        return self.spots_remaining == 0

    def to_dict(self):
        return {
            'id': self.id,
            'host_name': self.host_name,
            'organization': self.organization,
            'location_name': self.location_name,
            'address': self.address,
            'city': self.city,
            'zip_code': self.zip_code,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'district': self.district,
            'date': self.date.isoformat() if self.date else None,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'capacity': self.capacity,
            'spots_remaining': self.spots_remaining,
            'description': self.description,
            'status': self.status,
        }


class RSVP(db.Model):
    __tablename__ = 'rsvps'

    id = db.Column(db.Integer, primary_key=True)
    training_id = db.Column(db.Integer, db.ForeignKey('trainings.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    district = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    attended = db.Column(db.Boolean, nullable=True, default=None)

    certificate = db.relationship('Certificate', backref='rsvp', uselist=False)

    __table_args__ = (
        db.UniqueConstraint('training_id', 'email', name='uq_rsvp_training_email'),
    )


class Attendance(db.Model):
    __tablename__ = 'attendances'

    id = db.Column(db.Integer, primary_key=True)
    training_id = db.Column(db.Integer, db.ForeignKey('trainings.id'), nullable=False)
    reported_count = db.Column(db.Integer, nullable=False)
    reported_by = db.Column(db.String(20))
    reported_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)


class Certificate(db.Model):
    __tablename__ = 'certificates'

    id = db.Column(db.Integer, primary_key=True)
    rsvp_id = db.Column(db.Integer, db.ForeignKey('rsvps.id'), unique=True)
    certificate_number = db.Column(db.String(20), unique=True, nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    downloaded = db.Column(db.Boolean, default=False)


class Settings(db.Model):
    __tablename__ = 'settings'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)
