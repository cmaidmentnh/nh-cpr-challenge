"""Database models for NH CPR Challenge."""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Executive Councilors (2025-2026)
COUNCILORS = {
    1: {
        'name': 'Joseph Kenney',
        'party': 'R',
        'photo': 'https://img1.wsimg.com/isteam/ip/23893cc3-a682-414b-b986-d7c49394301a/kenny.jpeg',
        'bio': 'Lt. Col. USMC (Ret.) first elected in a 2014 special election. Former NH State Senator and State Representative, now serving his fifth term on the Executive Council.',
        'email': 'Joseph.D.Kenney@nh.gov',
        'phone': '(603) 271-3632',
        'district_desc': 'Northern and western NH — Coos, Grafton, and parts of Belknap, Carroll, Merrimack, and Sullivan Counties.',
    },
    2: {
        'name': 'Karen Liot Hill',
        'party': 'D',
        'photo': 'https://img1.wsimg.com/isteam/ip/23893cc3-a682-414b-b986-d7c49394301a/karen-liot-hill-headshot.png',
        'bio': 'Dartmouth Class of 2000, 20-year Lebanon City Councilor, former Mayor of Lebanon, and four-term Grafton County Treasurer. Elected in 2024.',
        'email': 'Karen.LiotHill@nh.gov',
        'phone': '(603) 271-3632',
        'district_desc': 'Capital region and western NH — 81 cities and towns including Concord, Keene, Lebanon, and Hanover.',
    },
    3: {
        'name': 'Janet Stevens',
        'party': 'R',
        'photo': 'https://img1.wsimg.com/isteam/ip/23893cc3-a682-414b-b986-d7c49394301a/stevens-sq.jpg',
        'bio': 'Rye resident and small business owner with 29+ years of public service. First elected in 2020, she became the second Republican woman on the Council since 1913.',
        'email': 'Janet.L.Stevens@nh.gov',
        'phone': '(603) 271-3632',
        'district_desc': 'Seacoast and southeast NH — 32 towns and cities including Portsmouth, Exeter, Hampton, Derry, and Salem.',
    },
    4: {
        'name': 'John Stephen',
        'party': 'R',
        'photo': 'https://img1.wsimg.com/isteam/ip/23893cc3-a682-414b-b986-d7c49394301a/john-stephen-headshot.png',
        'bio': 'Manchester attorney and healthcare reformer. Former Commissioner of NH DHHS and Deputy Commissioner of NH Dept. of Safety. Elected in 2024.',
        'email': 'John.A.Stephen@nh.gov',
        'phone': '(603) 271-3632',
        'district_desc': 'Manchester and surrounding communities — 20 cities and towns including Bedford, Goffstown, Londonderry, and Hooksett.',
    },
    5: {
        'name': 'Dave Wheeler',
        'party': 'R',
        'photo': 'https://img1.wsimg.com/isteam/ip/23893cc3-a682-414b-b986-d7c49394301a/wheeler-sq.jpg',
        'bio': 'Milford resident and longest-serving current Councilor, now in his eighth term. Former State Senator and State Representative.',
        'email': 'David.K.Wheeler@nh.gov',
        'phone': '(603) 271-3632',
        'district_desc': 'Southern NH and Monadnock region — 35 towns including Nashua, Hudson, Merrimack, Milford, and Hollis.',
    },
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


class Subscriber(db.Model):
    __tablename__ = 'subscribers'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), nullable=False, unique=True)
    district = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Settings(db.Model):
    __tablename__ = 'settings'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)
