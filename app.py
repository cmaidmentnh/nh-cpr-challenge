#!/usr/bin/env python3
"""NH EMS Week CPR Challenge — Flask Application."""

import csv
import logging
import os
import secrets
import string
from datetime import datetime, date
from functools import wraps
from io import BytesIO, StringIO

from flask import (Flask, render_template, request, jsonify, redirect,
                   url_for, session, send_file, flash, abort, Response, make_response)
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from models import db, User, Training, RSVP, Attendance, Certificate, Settings, Subscriber, COUNCILORS, DISTRICT_COLORS
from emails import (send_rsvp_confirmation, send_rsvp_notification_to_host,
                    send_training_approved, send_certificate_ready,
                    send_host_application_received, send_admin_new_host_application,
                    send_host_post_event_reminder, send_subscriber_training_notification)
from certificates import generate_certificate
from geocode import geocode_address

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///cpr_challenge.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

db.init_app(app)
csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=['200 per day', '50 per hour'])

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------
@app.context_processor
def inject_globals():
    has_approved = Training.query.filter(Training.status.in_(['approved', 'completed'])).first() is not None
    pending_nav = 0
    if current_user.is_authenticated and current_user.role == 'admin':
        pending_nav = Training.query.filter_by(status='pending').count()
    return {
        'councilors': COUNCILORS,
        'district_colors': DISTRICT_COLORS,
        'now': datetime.utcnow(),
        'show_leaderboard': has_approved,
        'current_user': current_user,
        'pending_nav': pending_nav,
    }


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def host_or_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('host', 'admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def get_setting(key, default=None):
    s = Settings.query.get(key)
    return s.value if s else default


def set_setting(key, value):
    s = Settings.query.get(key)
    if s:
        s.value = value
    else:
        s = Settings(key=key, value=value)
        db.session.add(s)
    db.session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def generate_cert_number():
    chars = string.ascii_uppercase + string.digits
    rand = ''.join(secrets.choice(chars) for _ in range(6))
    return f'CPR-2026-{rand}'


def generate_host_token():
    return secrets.token_hex(32)


def get_district_counts():
    """Get trained-people counts per district."""
    counts = {}
    for d in range(1, 6):
        # Use approved attendance reports
        att = db.session.query(db.func.sum(Attendance.reported_count)).join(Training).filter(
            Training.district == d,
            Attendance.approved == True
        ).scalar() or 0
        counts[d] = int(att)
    return counts


# =========================================================================
# PUBLIC ROUTES
# =========================================================================

@app.route('/')
def index():
    district_counts = get_district_counts()
    total = sum(district_counts.values())
    goal = int(get_setting('goal_target', '1000'))
    upcoming = Training.query.filter_by(status='approved').filter(
        Training.date >= date.today()
    ).order_by(Training.date).limit(3).all()
    return render_template('index.html',
                           district_counts=district_counts,
                           total=total,
                           goal=goal,
                           upcoming=upcoming)


@app.route('/trainings')
def trainings():
    district_filter = request.args.get('district', type=int)
    query = Training.query.filter_by(status='approved').filter(
        Training.date >= date.today()
    ).order_by(Training.date)
    if district_filter:
        query = query.filter_by(district=district_filter)
    all_trainings = query.all()
    return render_template('trainings.html', trainings=all_trainings,
                           district_filter=district_filter)


@app.route('/host', methods=['GET', 'POST'])
@limiter.limit('10 per hour', methods=['POST'])
def host():
    if request.method == 'POST':
        training = Training(
            host_name=request.form.get('host_name', '').strip(),
            host_email=request.form.get('host_email', '').strip(),
            host_phone=request.form.get('host_phone', '').strip(),
            organization=request.form.get('organization', '').strip(),
            location_name=request.form.get('location_name', '').strip(),
            address=request.form.get('address', '').strip(),
            city=request.form.get('city', '').strip(),
            zip_code=request.form.get('zip_code', '').strip(),
            district=int(request.form.get('district', 0)),
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            start_time=request.form.get('start_time', '').strip(),
            end_time=request.form.get('end_time', '').strip(),
            capacity=int(request.form.get('capacity', 30)),
            description=request.form.get('description', '').strip(),
            materials_needed='materials_needed' in request.form,
            status='pending',
            host_user_id=current_user.id if current_user.is_authenticated else None,
        )
        db.session.add(training)
        db.session.commit()

        try:
            send_host_application_received(training)
        except Exception as e:
            logger.error("Host confirmation email error: %s", e)

        try:
            send_admin_new_host_application(training)
        except Exception as e:
            logger.error("Admin notification email error: %s", e)

        flash('Thank you! Your training application has been submitted and is pending review. Check your email for confirmation.', 'success')
        return redirect(url_for('host'))
    return render_template('host.html')


@app.route('/rsvp/<int:training_id>', methods=['GET', 'POST'])
@limiter.limit('20 per hour', methods=['POST'])
def rsvp(training_id):
    training = Training.query.get_or_404(training_id)
    if training.status != 'approved':
        abort(404)

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        # Check for duplicate
        existing = RSVP.query.filter_by(training_id=training_id, email=email).first()
        if existing:
            flash('You have already RSVPed for this training.', 'warning')
            return redirect(url_for('rsvp', training_id=training_id))

        if training.is_full:
            flash('Sorry, this training is full.', 'error')
            return redirect(url_for('rsvp', training_id=training_id))

        new_rsvp = RSVP(
            training_id=training_id,
            name=request.form.get('name', '').strip(),
            email=email,
            phone=request.form.get('phone', '').strip(),
            district=int(request.form.get('district', 0)) or None,
        )
        db.session.add(new_rsvp)
        db.session.commit()

        # Send emails (non-blocking — if SES fails, RSVP is still saved)
        try:
            send_rsvp_confirmation(new_rsvp, training)
            send_rsvp_notification_to_host(new_rsvp, training)
        except Exception as e:
            logger.error("RSVP email error: %s", e)

        flash("You're registered! Check your email for confirmation details.", 'success')
        return redirect(url_for('rsvp', training_id=training_id))

    return render_template('rsvp.html', training=training)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/register-aed')
def register_aed():
    return render_template('register_aed.html')


@app.route('/map')
def map_page():
    return render_template('map.html')


@app.route('/leaderboard')
def leaderboard():
    district_counts = get_district_counts()
    total = sum(district_counts.values())
    goal = int(get_setting('goal_target', '1000'))
    return render_template('leaderboard.html',
                           district_counts=district_counts,
                           total=total,
                           goal=goal)


@app.route('/subscribe', methods=['POST'])
@limiter.limit('10 per hour', methods=['POST'])
def subscribe():
    email = request.form.get('email', '').strip().lower()
    district = request.form.get('district', type=int)

    if not email:
        flash('Please enter your email address.', 'error')
        return redirect(request.referrer or url_for('trainings'))

    existing = Subscriber.query.filter_by(email=email).first()
    if existing:
        if district and existing.district != district:
            existing.district = district
            db.session.commit()
        flash("You're already on the list! We'll keep you updated.", 'info')
    else:
        sub = Subscriber(email=email, district=district)
        db.session.add(sub)
        db.session.commit()
        flash("You're signed up! We'll notify you when trainings are posted in your area.", 'success')

    return redirect(request.referrer or url_for('trainings'))


# =========================================================================
# API ROUTES
# =========================================================================

@csrf.exempt
@app.route('/api/trainings')
def api_trainings():
    query = Training.query.filter_by(status='approved')
    district = request.args.get('district', type=int)
    if district:
        query = query.filter_by(district=district)
    trainings = query.all()
    return jsonify([t.to_dict() for t in trainings])


@csrf.exempt
@app.route('/api/districts')
def api_districts():
    counts = get_district_counts()
    total = sum(counts.values())
    goal = int(get_setting('goal_target', '1000'))
    return jsonify({
        'districts': {str(d): {
            'count': c,
            'councilor': COUNCILORS[d]['name'],
            'color': DISTRICT_COLORS[d],
        } for d, c in counts.items()},
        'total': total,
        'goal': goal,
    })


@csrf.exempt
@app.route('/api/ec-districts.geojson')
def api_geojson():
    return send_file('static/data/ec-districts.geojson', mimetype='application/json')


@csrf.exempt
@app.route('/api/detect-district')
def api_detect_district():
    """Detect EC district from lat/lng using point-in-polygon on GeoJSON."""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    if lat is None or lng is None:
        return jsonify({'error': 'lat and lng required'}), 400

    import json
    geojson_path = os.path.join(app.static_folder, 'data', 'ec-districts.geojson')
    with open(geojson_path) as f:
        geojson = json.load(f)

    for feature in geojson['features']:
        district = feature['properties']['district']
        geom = feature['geometry']
        if _point_in_geometry(lng, lat, geom):
            return jsonify({'district': district, 'councilor': COUNCILORS[district]['name']})

    return jsonify({'district': None})


def _point_in_geometry(x, y, geometry):
    """Check if point (x,y) is inside a GeoJSON geometry (Polygon or MultiPolygon)."""
    if geometry['type'] == 'Polygon':
        return _point_in_polygon(x, y, geometry['coordinates'])
    elif geometry['type'] == 'MultiPolygon':
        return any(_point_in_polygon(x, y, poly) for poly in geometry['coordinates'])
    return False


def _point_in_polygon(x, y, coordinates):
    """Ray-casting algorithm for point-in-polygon. coordinates is a list of rings."""
    ring = coordinates[0]  # exterior ring
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


# =========================================================================
# HOST PORTAL
# =========================================================================

@app.route('/host/report/<host_token>', methods=['GET', 'POST'])
def host_report(host_token):
    training = Training.query.filter_by(host_token=host_token).first_or_404()

    if request.method == 'POST':
        count = int(request.form.get('reported_count', 0))
        notes = request.form.get('notes', '').strip()

        attendance = Attendance(
            training_id=training.id,
            reported_count=count,
            reported_by='host',
            notes=notes,
        )
        db.session.add(attendance)

        # Mark individual RSVPs as attended if provided
        attended_ids = request.form.getlist('attended')
        for rsvp in training.rsvps.all():
            rsvp.attended = str(rsvp.id) in attended_ids

        training.status = 'completed'
        db.session.commit()

        flash('Thank you! Your attendance report has been submitted.', 'success')
        return redirect(url_for('host_report', host_token=host_token))

    rsvps = training.rsvps.all()
    existing_report = Attendance.query.filter_by(training_id=training.id).first()
    return render_template('host_report.html', training=training,
                           rsvps=rsvps, existing_report=existing_report)


# =========================================================================
# HOST DASHBOARD
# =========================================================================

@app.route('/host/dashboard')
@host_or_admin_required
def host_dashboard():
    my_trainings = Training.query.filter_by(
        host_user_id=current_user.id
    ).order_by(Training.date.desc()).all()
    return render_template('host/dashboard.html', trainings=my_trainings)


@app.route('/host/training/<int:training_id>')
@host_or_admin_required
def host_training_detail(training_id):
    training = Training.query.get_or_404(training_id)
    if training.host_user_id != current_user.id and current_user.role != 'admin':
        abort(403)
    rsvps = training.rsvps.all()
    existing_report = Attendance.query.filter_by(training_id=training.id).first()
    return render_template('host/training_detail.html', training=training,
                           rsvps=rsvps, existing_report=existing_report)


@app.route('/host/training/<int:training_id>/report', methods=['GET', 'POST'])
@host_or_admin_required
def host_training_report(training_id):
    training = Training.query.get_or_404(training_id)
    if training.host_user_id != current_user.id and current_user.role != 'admin':
        abort(403)

    if request.method == 'POST':
        count = int(request.form.get('reported_count', 0))
        notes = request.form.get('notes', '').strip()

        attendance = Attendance(
            training_id=training.id,
            reported_count=count,
            reported_by='host',
            notes=notes,
        )
        db.session.add(attendance)

        attended_ids = request.form.getlist('attended')
        for rsvp in training.rsvps.all():
            rsvp.attended = str(rsvp.id) in attended_ids

        training.status = 'completed'
        db.session.commit()

        flash('Thank you! Your attendance report has been submitted.', 'success')
        return redirect(url_for('host_training_detail', training_id=training_id))

    rsvps = training.rsvps.all()
    existing_report = Attendance.query.filter_by(training_id=training.id).first()
    return render_template('host/report.html', training=training,
                           rsvps=rsvps, existing_report=existing_report)


# =========================================================================
# CERTIFICATES
# =========================================================================

@app.route('/certificate/<certificate_number>')
def download_certificate(certificate_number):
    cert = Certificate.query.filter_by(certificate_number=certificate_number).first_or_404()
    rsvp = cert.rsvp
    training = rsvp.training

    pdf = generate_certificate(
        name=rsvp.name,
        date_str=training.date.strftime('%B %d, %Y'),
        location=training.location_name,
        certificate_number=cert.certificate_number,
    )

    cert.downloaded = True
    db.session.commit()

    return send_file(pdf, mimetype='application/pdf',
                     download_name=f'CPR_Certificate_{cert.certificate_number}.pdf',
                     as_attachment=True)


# =========================================================================
# ADMIN ROUTES
# =========================================================================

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit('5 per minute', methods=['POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('host_dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.is_active and user.check_password(password):
            login_user(user)
            # Auto-claim trainings by matching host email
            Training.query.filter_by(
                host_email=user.email, host_user_id=None
            ).update({'host_user_id': user.id})
            db.session.commit()
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('host_dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/admin/login')
def admin_login():
    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/admin/logout')
def admin_logout():
    return redirect(url_for('logout'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    total_trainings = Training.query.count()
    pending = Training.query.filter_by(status='pending').count()
    approved = Training.query.filter_by(status='approved').count()
    completed = Training.query.filter_by(status='completed').count()
    total_rsvps = RSVP.query.count()
    total_subscribers = Subscriber.query.count()
    total_users = User.query.count()
    district_counts = get_district_counts()
    total_trained = sum(district_counts.values())
    goal = int(get_setting('goal_target', '1000'))
    unapproved_attendance = Attendance.query.filter_by(approved=False).count()
    upcoming = Training.query.filter_by(status='approved').filter(
        Training.date >= date.today()
    ).order_by(Training.date).limit(5).all()
    recent_rsvps = RSVP.query.order_by(RSVP.created_at.desc()).limit(8).all()
    recent_trainings = Training.query.order_by(Training.created_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html',
                           total_trainings=total_trainings,
                           pending=pending,
                           approved=approved,
                           completed=completed,
                           total_rsvps=total_rsvps,
                           total_subscribers=total_subscribers,
                           total_users=total_users,
                           district_counts=district_counts,
                           total_trained=total_trained,
                           goal=goal,
                           unapproved_attendance=unapproved_attendance,
                           upcoming=upcoming,
                           recent_rsvps=recent_rsvps,
                           recent_trainings=recent_trainings)


@app.route('/admin/trainings')
@admin_required
def admin_trainings():
    status_filter = request.args.get('status', '')
    query = Training.query.order_by(Training.created_at.desc())
    if status_filter:
        query = query.filter_by(status=status_filter)
    all_trainings = query.all()
    return render_template('admin/trainings.html', trainings=all_trainings,
                           status_filter=status_filter)


@app.route('/admin/trainings/<int:training_id>/approve', methods=['POST'])
@admin_required
def admin_approve_training(training_id):
    training = Training.query.get_or_404(training_id)
    training.status = 'approved'
    training.host_token = generate_host_token()

    # Geocode the address if lat/lng not set
    if not training.latitude and training.address:
        lat, lng = geocode_address(training.address, training.city, zip_code=training.zip_code)
        if lat:
            training.latitude = lat
            training.longitude = lng

    db.session.commit()

    try:
        send_training_approved(training)
    except Exception as e:
        logger.error("Training approval email error: %s", e)

    # Notify subscribers in this district
    subscribers = Subscriber.query.filter(
        (Subscriber.district == training.district) | (Subscriber.district.is_(None))
    ).all()
    notified = 0
    for sub in subscribers:
        try:
            send_subscriber_training_notification(sub.email, training)
            notified += 1
        except Exception as e:
            logger.error("Subscriber notification error for %s: %s", sub.email, e)
    if notified:
        logger.info("Notified %d subscriber(s) for training %d", notified, training.id)

    flash(f'Training by {training.host_name} approved. {notified} subscriber(s) notified.', 'success')
    return redirect(url_for('admin_trainings'))


@app.route('/admin/trainings/<int:training_id>/reject', methods=['POST'])
@admin_required
def admin_reject_training(training_id):
    training = Training.query.get_or_404(training_id)
    training.status = 'cancelled'
    db.session.commit()
    flash(f'Training by {training.host_name} rejected.', 'warning')
    return redirect(url_for('admin_trainings'))


@app.route('/admin/trainings/<int:training_id>/complete', methods=['POST'])
@admin_required
def admin_complete_training(training_id):
    training = Training.query.get_or_404(training_id)
    training.status = 'completed'
    db.session.commit()
    flash(f'Training marked as completed.', 'success')
    return redirect(url_for('admin_trainings'))


@app.route('/admin/rsvps')
@admin_required
def admin_rsvps():
    training_id = request.args.get('training_id', type=int)
    query = RSVP.query.order_by(RSVP.created_at.desc())
    if training_id:
        query = query.filter_by(training_id=training_id)
    all_rsvps = query.all()
    trainings_list = Training.query.order_by(Training.date).all()
    return render_template('admin/rsvps.html', rsvps=all_rsvps,
                           trainings_list=trainings_list,
                           training_id=training_id)


@app.route('/admin/attendance/<int:training_id>', methods=['POST'])
@admin_required
def admin_attendance(training_id):
    training = Training.query.get_or_404(training_id)
    count = int(request.form.get('reported_count', 0))
    notes = request.form.get('notes', '').strip()

    attendance = Attendance(
        training_id=training_id,
        reported_count=count,
        reported_by='admin',
        approved=True,
        notes=notes,
    )
    db.session.add(attendance)

    if training.status != 'completed':
        training.status = 'completed'

    db.session.commit()
    flash(f'Attendance of {count} recorded and approved.', 'success')
    return redirect(url_for('admin_trainings'))


@app.route('/admin/attendance/<int:attendance_id>/approve', methods=['POST'])
@admin_required
def admin_approve_attendance(attendance_id):
    att = Attendance.query.get_or_404(attendance_id)
    att.approved = True
    db.session.commit()
    flash('Attendance report approved.', 'success')
    return redirect(url_for('admin_trainings'))


@app.route('/admin/certificates/<int:training_id>/issue', methods=['POST'])
@admin_required
def admin_issue_certificates(training_id):
    training = Training.query.get_or_404(training_id)
    issued = 0
    for rsvp in training.rsvps.filter_by(attended=True).all():
        if not rsvp.certificate:
            cert = Certificate(
                rsvp_id=rsvp.id,
                certificate_number=generate_cert_number(),
            )
            db.session.add(cert)
            issued += 1
            try:
                db.session.flush()
                send_certificate_ready(rsvp, cert)
            except Exception as e:
                logger.error("Certificate email error: %s", e)
    db.session.commit()
    flash(f'{issued} certificates issued.', 'success')
    return redirect(url_for('admin_trainings'))


@app.route('/admin/export/csv/<data_type>')
@admin_required
def admin_export_csv(data_type):
    si = StringIO()
    writer = csv.writer(si)

    if data_type == 'trainings':
        writer.writerow(['ID', 'Host', 'Email', 'Phone', 'Organization', 'Location',
                          'Address', 'City', 'Zip', 'District', 'Date', 'Time',
                          'Capacity', 'Status', 'RSVPs', 'Created'])
        for t in Training.query.order_by(Training.date).all():
            writer.writerow([t.id, t.host_name, t.host_email, t.host_phone,
                              t.organization, t.location_name, t.address, t.city,
                              t.zip_code, t.district, t.date, t.start_time,
                              t.capacity, t.status, t.rsvps.count(), t.created_at])

    elif data_type == 'rsvps':
        writer.writerow(['ID', 'Training', 'Training Date', 'Name', 'Email',
                          'Phone', 'District', 'RSVP Date', 'Attended'])
        for r in RSVP.query.order_by(RSVP.created_at).all():
            writer.writerow([r.id, r.training.location_name, r.training.date,
                              r.name, r.email, r.phone, r.district,
                              r.created_at, r.attended])

    elif data_type == 'certificates':
        writer.writerow(['Certificate #', 'Name', 'Email', 'Training',
                          'Training Date', 'Issued', 'Downloaded'])
        for c in Certificate.query.order_by(Certificate.issued_at).all():
            writer.writerow([c.certificate_number, c.rsvp.name, c.rsvp.email,
                              c.rsvp.training.location_name, c.rsvp.training.date,
                              c.issued_at, c.downloaded])

    elif data_type == 'subscribers':
        writer.writerow(['ID', 'Email', 'District', 'Signed Up'])
        for s in Subscriber.query.order_by(Subscriber.created_at).all():
            writer.writerow([s.id, s.email, s.district or 'Any', s.created_at])
    else:
        abort(404)

    output = BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)
    return send_file(output, mimetype='text/csv',
                     download_name=f'cpr_challenge_{data_type}_{date.today()}.csv',
                     as_attachment=True)


@app.route('/admin/settings', methods=['POST'])
@admin_required
def admin_settings():
    goal = request.form.get('goal_target', '1000')
    set_setting('goal_target', goal)

    new_password = request.form.get('new_password', '').strip()
    if new_password:
        current_user.set_password(new_password)
        db.session.commit()
        flash('Password updated.', 'success')

    flash('Settings saved.', 'success')
    return redirect(url_for('admin_dashboard'))


# =========================================================================
# ADMIN USER MANAGEMENT
# =========================================================================

@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@app.route('/admin/users/create', methods=['POST'])
@admin_required
def admin_create_user():
    email = request.form.get('email', '').strip().lower()
    name = request.form.get('name', '').strip()
    role = request.form.get('role', 'host')
    password = request.form.get('password', '').strip()

    if not email or not name or not password:
        flash('Email, name, and password are required.', 'error')
        return redirect(url_for('admin_users'))

    if role not in ('admin', 'host'):
        role = 'host'

    existing = User.query.filter_by(email=email).first()
    if existing:
        flash(f'A user with email {email} already exists.', 'error')
        return redirect(url_for('admin_users'))

    user = User(email=email, name=name, role=role)
    user.set_password(password)
    db.session.add(user)

    # Auto-claim any trainings with matching host email
    Training.query.filter_by(
        host_email=email, host_user_id=None
    ).update({'host_user_id': user.id})

    db.session.commit()
    flash(f'User {name} ({role}) created.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/toggle-active', methods=['POST'])
@admin_required
def admin_toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate yourself.', 'error')
        return redirect(url_for('admin_users'))
    user.is_active = not user.is_active
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.name} {status}.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def admin_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('password', '').strip()
    if not new_password:
        flash('Password is required.', 'error')
        return redirect(url_for('admin_users'))
    user.set_password(new_password)
    db.session.commit()
    flash(f'Password reset for {user.name}.', 'success')
    return redirect(url_for('admin_users'))


# =========================================================================
# SITEMAP & ROBOTS
# =========================================================================

@app.route('/sitemap.xml')
def sitemap():
    pages = [
        ('/', '1.0', 'weekly'),
        ('/trainings', '0.9', 'daily'),
        ('/host', '0.8', 'monthly'),
        ('/about', '0.7', 'monthly'),
        ('/map', '0.7', 'monthly'),
        ('/leaderboard', '0.6', 'daily'),
        ('/register-aed', '0.8', 'monthly'),
    ]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    base = 'https://cprchallengenh.com'
    for path, priority, freq in pages:
        xml.append(f'<url><loc>{base}{path}</loc>'
                   f'<changefreq>{freq}</changefreq>'
                   f'<priority>{priority}</priority></url>')
    # Add individual training pages
    for t in Training.query.filter_by(status='approved').all():
        xml.append(f'<url><loc>{base}/rsvp/{t.id}</loc>'
                   f'<changefreq>weekly</changefreq>'
                   f'<priority>0.6</priority></url>')
    xml.append('</urlset>')
    return Response('\n'.join(xml), mimetype='application/xml')


@app.route('/robots.txt')
def robots():
    txt = """User-agent: *
Allow: /
Disallow: /admin/
Disallow: /host/report/
Disallow: /host/dashboard
Disallow: /host/training/
Disallow: /api/

Sitemap: https://cprchallengenh.com/sitemap.xml"""
    return Response(txt, mimetype='text/plain')


@app.route('/llms.txt')
def llms_txt():
    content = """# NH CPR Challenge
> cprchallengenh.com

Free Hands-Only CPR awareness training across all five New Hampshire Executive Council districts during EMS Week 2026 (May 17-23).

## Key Pages
- / - Homepage with overview, countdown, and district map
- /find - Find a free CPR training near you by town or zip code
- /host - Sign up to host a training at your organization
- /about - About the initiative and the Executive Council's role

## About
The NH CPR Challenge is a bipartisan initiative of the New Hampshire Executive Council. The goal is to train as many Granite Staters as possible in Hands-Only CPR during EMS Week. Training takes 15 minutes, requires no experience, and is completely free.

## Key Facts
- Hands-Only CPR has two steps: Call 911, then push hard and fast in the center of the chest
- Cardiac arrest kills more than 350,000 Americans per year
- Bystander CPR can double or triple survival rates
- New Hampshire trains across all five Executive Council districts
"""
    return Response(content, mimetype='text/plain')


# =========================================================================
# ERROR HANDLERS
# =========================================================================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('404.html', error_500=True), 500


# =========================================================================
# CLI COMMANDS
# =========================================================================

@app.cli.command('send-post-event-reminders')
def send_post_event_reminders():
    """Send reminder emails to hosts whose trainings were yesterday."""
    from datetime import timedelta
    yesterday = date.today() - timedelta(days=1)
    trainings = Training.query.filter_by(
        status='approved', date=yesterday
    ).all()
    sent = 0
    for t in trainings:
        # Skip if already reported
        existing = Attendance.query.filter_by(training_id=t.id).first()
        if existing:
            continue
        try:
            send_host_post_event_reminder(t)
            sent += 1
            logger.info("Sent reminder to %s for %s", t.host_email, t.location_name)
        except Exception as e:
            logger.error("Error sending reminder to %s: %s", t.host_email, e)
    logger.info("Done. Sent %d reminder(s).", sent)


# ---------------------------------------------------------------------------
# DB Init
# ---------------------------------------------------------------------------
def init_db():
    from sqlalchemy import text, inspect
    db.create_all()

    # Migrate: add host_user_id column to trainings if missing
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('trainings')]
    if 'host_user_id' not in columns:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE trainings ADD COLUMN host_user_id INTEGER REFERENCES users(id)'))
            conn.commit()

    # Create default admin user if none exists
    if not User.query.filter_by(role='admin').first():
        admin = User(
            email=os.getenv('ADMIN_EMAIL', 'admin@cprchallengenh.com'),
            name='Admin',
            role='admin',
        )
        admin.set_password(os.getenv('ADMIN_PASSWORD', 'changeme'))
        db.session.add(admin)
        db.session.commit()

    if not get_setting('goal_target'):
        set_setting('goal_target', os.getenv('GOAL_TARGET', '1000'))


with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5011, debug=True)
