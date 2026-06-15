"""One-off roster ingest: Hands-Only CPR class, Windham Woods School, 2026-06-09.

Creates the completed internal training, the 4 attendees (marked attended),
an approved attendance count (so it counts toward the District 3 goal), and
issues + emails certificates. Idempotent: re-running will not duplicate the
training, RSVPs, or certificates.

Run on the production server (real DB + SES creds):
    cd /opt/nh-cpr-challenge && ./venv/bin/python ingest_windham_20260609.py
"""

from datetime import date

import app as A
from app import db, generate_cert_number, generate_host_token, WALKIN_EMAIL_DOMAIN
from emails import send_certificate_ready
from models import Training, RSVP, Attendance, Certificate

LOCATION = 'Windham Woods School'
CITY = 'Windham'
DISTRICT = 3
CLASS_DATE = date(2026, 6, 9)
LAT, LNG = 42.8197263, -71.2546743

HOST_NAME = 'Michael Martin'
HOST_EMAIL = 'michael@smartinrealestate.net'

NARRATIVE = (
    "Class began at 1700hr on 6/9/26 with one student (Helen) in attendance. With "
    "there only being one student the block of instruction and practical exercise "
    "were completed by 1730hr. At 1730 three additional students (Lynda, Carol, "
    "Patrick) arrived. The block of instruction was then given to the new students. "
    "Instruction and practical exercises were completed at 1815hr for the second "
    "group. All students filled out their name and email in the above section. All "
    "students successfully completed the class and the event concluded at 1830hr."
)

STUDENTS = [
    ('Helen Samson', 'nufern@gmail.com'),
    ('Lynda Donovan', 'lyndadonovan@comcast.net'),  # typo 'comcst' corrected
    ('Carol Williams', 'carolann.williams@comcast.net'),
    ('Patrick Palmer', 'palmerpa@icloud.com'),
]


def main():
    with A.app.app_context():
        training = Training.query.filter_by(
            location_name=LOCATION, date=CLASS_DATE
        ).first()
        if training:
            print(f"Training already exists (id={training.id}); reusing it.")
        else:
            training = Training(
                host_name=HOST_NAME,
                host_email=HOST_EMAIL,
                organization=None,
                location_name=LOCATION,
                city=CITY,
                latitude=LAT,
                longitude=LNG,
                district=DISTRICT,
                date=CLASS_DATE,
                start_time='5:00 PM',
                end_time='6:30 PM',
                capacity=30,
                description=NARRATIVE,
                status='completed',
                internal_only=True,
                host_token=generate_host_token(),
            )
            db.session.add(training)
            db.session.commit()
            print(f"Created training id={training.id}")

        # Attendees
        for name, email in STUDENTS:
            email = email.strip().lower()
            rsvp = RSVP.query.filter_by(training_id=training.id, email=email).first()
            if rsvp:
                rsvp.attended = True
                print(f"  RSVP exists: {name} <{email}>")
            else:
                rsvp = RSVP(
                    training_id=training.id,
                    name=name,
                    email=email,
                    district=DISTRICT,
                    attended=True,
                )
                db.session.add(rsvp)
                print(f"  Added RSVP: {name} <{email}>")
        db.session.commit()

        # Approved attendance count -> counts toward District 3 goal
        attended_rsvps = training.rsvps.filter_by(attended=True).all()
        att = Attendance.query.filter_by(training_id=training.id).first()
        if not att:
            att = Attendance(
                training_id=training.id,
                reported_count=len(attended_rsvps),
                reported_by='admin-roster',
                approved=True,
            )
            db.session.add(att)
            print(f"Created approved attendance: {len(attended_rsvps)}")
        else:
            att.reported_count = len(attended_rsvps)
            att.approved = True
            print(f"Updated attendance count: {len(attended_rsvps)}")
        db.session.commit()

        # Issue + email certificates
        issued = 0
        for rsvp in attended_rsvps:
            if rsvp.certificate:
                print(f"  Cert exists for {rsvp.name}: {rsvp.certificate.certificate_number}")
                continue
            cert = Certificate(rsvp_id=rsvp.id, certificate_number=generate_cert_number())
            db.session.add(cert)
            db.session.flush()
            issued += 1
            if not rsvp.email.endswith('@' + WALKIN_EMAIL_DOMAIN):
                try:
                    ok = send_certificate_ready(rsvp, cert)
                    print(f"  Issued + emailed {rsvp.name}: {cert.certificate_number} (sent={ok})")
                except Exception as e:
                    print(f"  Issued {rsvp.name}: {cert.certificate_number} BUT EMAIL FAILED: {e}")
        db.session.commit()
        print(f"Done. Issued {issued} new certificate(s).")


if __name__ == '__main__':
    main()
