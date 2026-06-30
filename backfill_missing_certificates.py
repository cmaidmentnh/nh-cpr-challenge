"""Backfill certificates for attendees marked attended=True who never had a
certificate issued.

Root cause: for ~19 trainings the certificate-issuance step (normally run on
host check-in close or via the admin "issue certificates" action) was never
executed, so attendance was recorded but no Certificate rows / emails were
created.

This mirrors admin_issue_certificates(): for every RSVP with attended=True and
no certificate, create a Certificate and email it via send_certificate_ready.
Walk-in placeholders (@walkin.local) get a certificate row but no email, exactly
as the rest of the app behaves. Idempotent and resumable: commits after each
recipient, skips anyone who already has a certificate.

Run on the production server (real DB + SES creds):
    cd /opt/nh-cpr-challenge && ./venv/bin/python backfill_missing_certificates.py
Dry run (no writes, no emails):
    ./venv/bin/python backfill_missing_certificates.py --dry-run
"""
import sys
import time

import app as A
from app import db, generate_cert_number, WALKIN_EMAIL_DOMAIN
from emails import send_certificate_ready
from models import Training, RSVP, Certificate

DRY_RUN = '--dry-run' in sys.argv
SLEEP_BETWEEN_SENDS = 0.15  # gentle pacing for SES


def main():
    with A.app.app_context():
        targets = [r for r in RSVP.query.filter_by(attended=True).all()
                   if not r.certificate]
        real = [r for r in targets if not r.email.endswith('@' + WALKIN_EMAIL_DOMAIN)]
        walkin = [r for r in targets if r.email.endswith('@' + WALKIN_EMAIL_DOMAIN)]

        print(f"Attendees missing a certificate: {len(targets)} "
              f"({len(real)} real-email, {len(walkin)} walk-in)")
        if DRY_RUN:
            print("DRY RUN — no certificates created, no emails sent.")
            return

        issued = 0
        emailed = 0
        failed = []
        for r in targets:
            t = Training.query.get(r.training_id)
            cert = Certificate(rsvp_id=r.id, certificate_number=generate_cert_number())
            db.session.add(cert)
            db.session.flush()
            issued += 1
            is_walkin = r.email.endswith('@' + WALKIN_EMAIL_DOMAIN)
            if is_walkin:
                db.session.commit()
                print(f"  [walkin] {r.name} (T{t.id}) cert {cert.certificate_number} — no email")
                continue
            try:
                send_certificate_ready(r, cert)
                db.session.commit()
                emailed += 1
                print(f"  [sent]   {r.name} <{r.email}> (T{t.id}) {cert.certificate_number}")
                time.sleep(SLEEP_BETWEEN_SENDS)
            except Exception as e:
                db.session.commit()  # keep the cert; allow resend later
                failed.append((r.name, r.email, cert.certificate_number, str(e)))
                print(f"  [FAIL]   {r.name} <{r.email}> (T{t.id}) {cert.certificate_number}: {e}")

        print()
        print(f"Done. Issued {issued} certificate(s); emailed {emailed}; "
              f"{len(walkin)} walk-in (no email); {len(failed)} email failure(s).")
        if failed:
            print("Email failures (cert issued, resend via resend_certificates.py):")
            for name, email, num, err in failed:
                print(f"  {name} <{email}> {num}: {err}")


if __name__ == '__main__':
    main()
