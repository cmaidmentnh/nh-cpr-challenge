"""Email notifications via AWS SES."""

import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3
from botocore.exceptions import ClientError


def get_ses_client():
    return boto3.client(
        'ses',
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )


def send_email(to, subject, html_body, plain_body=None):
    """Send an email via SES. Returns True on success."""
    sender_name = os.getenv('SES_SENDER_NAME', 'NH CPR Challenge')
    sender_email = os.getenv('SES_SENDER_EMAIL', 'info@cprchallengenh.com')

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f'{sender_name} <{sender_email}>'
    msg['To'] = to

    if plain_body:
        msg.attach(MIMEText(plain_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        client = get_ses_client()
        client.send_raw_email(
            Source=f'{sender_name} <{sender_email}>',
            Destinations=[to],
            RawMessage={'Data': msg.as_string()},
        )
        return True
    except ClientError as e:
        print(f"SES error sending to {to}: {e}")
        return False


def _email_wrapper(html):
    """Wrap HTML content in a styled email template."""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;">
<tr><td style="background:#1e3a5f;padding:24px;text-align:center;">
<h1 style="color:#ffffff;margin:0;font-size:22px;">NH CPR Challenge</h1>
<p style="color:#d4a843;margin:4px 0 0;font-size:14px;">EMS Week 2026 &middot; May 17&ndash;23</p>
</td></tr>
<tr><td style="padding:32px 24px;">{html}</td></tr>
<tr><td style="background:#f8fafc;padding:16px 24px;text-align:center;font-size:12px;color:#64748b;">
NH EMS Week CPR Challenge 2026<br>
A bipartisan initiative of the New Hampshire Executive Council
</td></tr>
</table>
</td></tr></table>
</body></html>"""


def send_rsvp_confirmation(rsvp, training):
    """Send RSVP confirmation to attendee."""
    app_url = os.getenv('APP_URL', 'https://cprchallengenh.com')
    html = _email_wrapper(f"""
<h2 style="color:#1e3a5f;margin-top:0;">You're Registered!</h2>
<p>Hi {rsvp.name},</p>
<p>You're signed up for a free Hands-Only CPR training session. Here are the details:</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0;">
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">Date</td>
<td style="padding:8px;">{training.date.strftime('%A, %B %d, %Y')}</td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">Time</td>
<td style="padding:8px;">{training.start_time or 'TBD'}{(' - ' + training.end_time) if training.end_time else ''}</td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">Location</td>
<td style="padding:8px;">{training.location_name}<br>{training.address or ''}, {training.city or ''}</td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">Host</td>
<td style="padding:8px;">{training.organization or training.host_name}</td></tr>
</table>
<p><strong>What to expect:</strong> A quick 15-20 minute session where you'll learn the two steps of Hands-Only CPR: (1) Call 911, and (2) Push hard and fast in the center of the chest. No prior experience needed.</p>
<p>After attending, you'll receive a certificate of participation.</p>
<p style="text-align:center;margin-top:24px;">
<a href="{app_url}/trainings" style="display:inline-block;padding:12px 24px;background:#d4a843;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;">View All Trainings</a>
</p>
""")
    send_email(rsvp.email, 'Your CPR Training is Confirmed!', html)


def send_rsvp_notification_to_host(rsvp, training):
    """Notify host that someone RSVPed."""
    html = _email_wrapper(f"""
<h2 style="color:#1e3a5f;margin-top:0;">New RSVP!</h2>
<p>Hi {training.host_name},</p>
<p>Someone has signed up for your CPR training on {training.date.strftime('%B %d')}:</p>
<ul>
<li><strong>Name:</strong> {rsvp.name}</li>
<li><strong>Email:</strong> {rsvp.email}</li>
{f'<li><strong>Phone:</strong> {rsvp.phone}</li>' if rsvp.phone else ''}
</ul>
<p>You now have <strong>{training.rsvps.count()}</strong> of {training.capacity} spots filled.</p>
""")
    send_email(training.host_email, f'New RSVP for your CPR training - {rsvp.name}', html)


def send_host_application_received(training):
    """Confirm to host that their application was received."""
    html = _email_wrapper(f"""
<h2 style="color:#1e3a5f;margin-top:0;">Application Received</h2>
<p>Hi {training.host_name},</p>
<p>Thank you for applying to host a free Hands-Only CPR training through the NH CPR Challenge! We've received your application and will review it shortly.</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0;">
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">Location</td>
<td style="padding:8px;">{training.location_name}</td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">Date</td>
<td style="padding:8px;">{training.date.strftime('%A, %B %d, %Y')}</td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">City</td>
<td style="padding:8px;">{training.city or 'Not specified'}</td></tr>
</table>
<p>You'll receive another email once your training has been approved and is listed on the website.</p>
<p style="color:#64748b;font-size:13px;">If you have any questions, reply to this email.</p>
""")
    send_email(training.host_email, 'CPR Training Application Received', html)


def send_training_approved(training):
    """Notify host their training was approved. Includes host portal link."""
    app_url = os.getenv('APP_URL', 'https://cprchallengenh.com')
    html = _email_wrapper(f"""
<h2 style="color:#1e3a5f;margin-top:0;">Your Training is Approved!</h2>
<p>Hi {training.host_name},</p>
<p>Great news! Your CPR training has been approved and is now listed on the NH CPR Challenge website.</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0;">
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">Date</td>
<td style="padding:8px;">{training.date.strftime('%A, %B %d, %Y')}</td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">Location</td>
<td style="padding:8px;">{training.location_name}</td></tr>
</table>
<p>After your event, please use this link to report attendance:</p>
<p style="text-align:center;margin-top:24px;">
<a href="{app_url}/host/report/{training.host_token}" style="display:inline-block;padding:12px 24px;background:#1e3a5f;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;">Report Attendance</a>
</p>
<p style="color:#64748b;font-size:13px;">Keep this link private — it's your unique portal for managing your training event.</p>
""")
    send_email(training.host_email, 'Your CPR Training Has Been Approved!', html)


def send_admin_new_host_application(training):
    """Notify admin that a new host training application was submitted."""
    admin_email = os.getenv('ADMIN_EMAIL', '')
    if not admin_email:
        print("ADMIN_EMAIL not set, skipping admin notification")
        return
    app_url = os.getenv('APP_URL', 'https://cprchallengenh.com')
    html = _email_wrapper(f"""
<h2 style="color:#1e3a5f;margin-top:0;">New Host Application</h2>
<p>A new training application has been submitted and needs review.</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0;">
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">Host</td>
<td style="padding:8px;">{training.host_name}</td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">Email</td>
<td style="padding:8px;">{training.host_email}</td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">Organization</td>
<td style="padding:8px;">{training.organization or 'N/A'}</td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">Location</td>
<td style="padding:8px;">{training.location_name}, {training.city or ''}</td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">Date</td>
<td style="padding:8px;">{training.date.strftime('%A, %B %d, %Y')}</td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">District</td>
<td style="padding:8px;">{training.district}</td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#1e3a5f;">Capacity</td>
<td style="padding:8px;">{training.capacity}</td></tr>
</table>
<p style="text-align:center;margin-top:24px;">
<a href="{app_url}/admin/trainings" style="display:inline-block;padding:12px 24px;background:#1e3a5f;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;">Review in Admin</a>
</p>
""")
    send_email(admin_email, f'New CPR Training Application — {training.host_name}', html)


def send_host_post_event_reminder(training):
    """Remind host to submit attendance count after their event."""
    app_url = os.getenv('APP_URL', 'https://cprchallengenh.com')
    if not training.host_token:
        return
    html = _email_wrapper(f"""
<h2 style="color:#1e3a5f;margin-top:0;">How Did It Go?</h2>
<p>Hi {training.host_name},</p>
<p>Your CPR training at <strong>{training.location_name}</strong> was scheduled for yesterday. Thank you for hosting!</p>
<p>Please take a moment to report how many people attended. This helps us track the CPR Challenge progress and issue certificates to participants.</p>
<p style="text-align:center;margin-top:24px;">
<a href="{app_url}/host/report/{training.host_token}" style="display:inline-block;padding:12px 24px;background:#d4a843;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;">Report Attendance</a>
</p>
<p style="color:#64748b;font-size:13px;">If you already submitted your report, you can ignore this email. Thank you!</p>
""")
    send_email(training.host_email, 'How did your CPR training go? Please report attendance', html)


def send_certificate_ready(rsvp, certificate):
    """Notify attendee their certificate is available."""
    app_url = os.getenv('APP_URL', 'https://cprchallengenh.com')
    html = _email_wrapper(f"""
<h2 style="color:#1e3a5f;margin-top:0;">Your Certificate is Ready!</h2>
<p>Hi {rsvp.name},</p>
<p>Thank you for participating in the NH CPR Challenge! Your certificate of participation is ready to download.</p>
<p><strong>Certificate #:</strong> {certificate.certificate_number}</p>
<p style="text-align:center;margin-top:24px;">
<a href="{app_url}/certificate/{certificate.certificate_number}" style="display:inline-block;padding:12px 24px;background:#d4a843;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;">Download Certificate</a>
</p>
<p style="color:#64748b;font-size:13px;">Note: This certificate recognizes your participation in Hands-Only CPR awareness training. It is not an official CPR certification.</p>
""")
    send_email(rsvp.email, 'Your CPR Challenge Certificate is Ready!', html)
