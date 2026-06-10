"""Admin tool: re-issue / resend certificates with the PDF attached.

Attendees behind workplace firewalls often can't open the certificate
*download link*, but email attachments reach them fine. These commands resend
the certificate as an attached PDF, and can correct a misspelled name first.

Examples:
    # Resend one certificate (by cert number or attendee email), PDF attached
    python resend_certificates.py resend --cert CPR-2026-L45C8I
    python resend_certificates.py resend --email kathybob10@aol.com

    # Fix a misspelled name, then resend the corrected certificate
    python resend_certificates.py fixname --cert CPR-2026-VS8F88 --name "Diane Caruso" --resend

    # Email one recipient a single PDF with every cert from given trainings
    python resend_certificates.py bundle --trainings 100,104,105,106,107 \
        --to stacey.carroll@snhhs.org --name "Stacey"

Add --dry-run to any command to preview without sending or writing.
"""
import argparse
import sys

from app import app, db
from models import RSVP, Certificate, Training
from emails import send_certificate_ready, send_certificate_bundle


def _find(cert_number=None, email=None):
    if cert_number:
        cert = Certificate.query.filter_by(certificate_number=cert_number).first()
        return (cert.rsvp, cert) if cert else (None, None)
    rsvp = RSVP.query.filter(RSVP.email.ilike(email)).first()
    if not rsvp:
        return (None, None)
    return (rsvp, rsvp.certificate)


def cmd_resend(args):
    rsvp, cert = _find(args.cert, args.email)
    if not rsvp:
        sys.exit(f"No attendee found for {args.cert or args.email}")
    if not cert:
        sys.exit(f"{rsvp.name} has no certificate on record (training not closed?)")
    print(f"Resend: {rsvp.name} <{rsvp.email}>  cert {cert.certificate_number}")
    if args.dry_run:
        print("  [dry-run] not sent")
        return
    ok = send_certificate_ready(rsvp, cert)
    print("  sent" if ok else "  FAILED")


def cmd_fixname(args):
    rsvp, cert = _find(args.cert, args.email)
    if not rsvp:
        sys.exit(f"No attendee found for {args.cert or args.email}")
    print(f"Rename: '{rsvp.name}' -> '{args.name}'  ({rsvp.email})")
    if args.dry_run:
        print("  [dry-run] not changed")
        return
    rsvp.name = args.name
    db.session.commit()
    print("  name updated")
    if args.resend:
        if not cert:
            sys.exit("  no certificate to resend")
        ok = send_certificate_ready(rsvp, cert)
        print("  corrected certificate sent" if ok else "  resend FAILED")


def cmd_bundle(args):
    tids = [int(x) for x in args.trainings.split(',') if x.strip()]
    pairs = (db.session.query(RSVP, Certificate)
             .join(Certificate, Certificate.rsvp_id == RSVP.id)
             .filter(RSVP.training_id.in_(tids))
             .order_by(RSVP.training_id, RSVP.id).all())
    if not pairs:
        sys.exit(f"No issued certificates found for trainings {tids}")
    print(f"Bundle {len(pairs)} certs -> {args.name} <{args.to}>")
    for rsvp, cert in pairs:
        print(f"  - {rsvp.name}  {cert.certificate_number}")
    if args.dry_run:
        print("  [dry-run] not sent")
        return
    ok = send_certificate_bundle(args.to, args.name, pairs, org_label=args.org)
    print("  sent" if ok else "  FAILED")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='command', required=True)

    pr = sub.add_parser('resend', help='Resend one certificate with PDF attached')
    pr.add_argument('--cert')
    pr.add_argument('--email')
    pr.add_argument('--dry-run', action='store_true')
    pr.set_defaults(func=cmd_resend)

    pf = sub.add_parser('fixname', help='Correct an attendee name (optionally resend)')
    pf.add_argument('--cert')
    pf.add_argument('--email')
    pf.add_argument('--name', required=True)
    pf.add_argument('--resend', action='store_true')
    pf.add_argument('--dry-run', action='store_true')
    pf.set_defaults(func=cmd_fixname)

    pb = sub.add_parser('bundle', help='Email one recipient a merged PDF of many certs')
    pb.add_argument('--trainings', required=True, help='comma-separated training IDs')
    pb.add_argument('--to', required=True)
    pb.add_argument('--name', required=True)
    pb.add_argument('--org', default=None, help='optional label, e.g. "Southern NH Health"')
    pb.add_argument('--dry-run', action='store_true')
    pb.set_defaults(func=cmd_bundle)

    args = p.parse_args()
    if args.command in ('resend', 'fixname') and not (args.cert or args.email):
        sys.exit("Provide --cert or --email")
    with app.app_context():
        args.func(args)


if __name__ == '__main__':
    main()
