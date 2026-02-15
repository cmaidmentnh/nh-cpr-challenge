"""PDF certificate generation using ReportLab."""

import os
from io import BytesIO
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas


NAVY = HexColor('#1e3a5f')
GOLD = HexColor('#d4a843')
LIGHT_NAVY = HexColor('#e8edf2')
DARK_TEXT = HexColor('#1a1a2e')


def generate_certificate(name, date_str, location, certificate_number):
    """Generate a PDF participation certificate.

    Args:
        name: Participant's full name
        date_str: Training date as formatted string (e.g., "May 19, 2026")
        location: Training location name
        certificate_number: Unique certificate ID (e.g., "CPR-2026-A3F8K")

    Returns:
        BytesIO containing the PDF
    """
    buf = BytesIO()
    width, height = landscape(letter)  # 11" x 8.5"
    c = canvas.Canvas(buf, pagesize=landscape(letter))

    # Background
    c.setFillColor(HexColor('#ffffff'))
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # Outer border
    c.setStrokeColor(NAVY)
    c.setLineWidth(3)
    c.rect(0.4 * inch, 0.4 * inch, width - 0.8 * inch, height - 0.8 * inch)

    # Inner border
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.rect(0.55 * inch, 0.55 * inch, width - 1.1 * inch, height - 1.1 * inch)

    # Gold accent line at top
    c.setFillColor(GOLD)
    c.rect(0.55 * inch, height - 1.4 * inch, width - 1.1 * inch, 4)

    # NH state seal (if image exists, otherwise a placeholder circle)
    seal_path = os.path.join(os.path.dirname(__file__), 'static', 'img', 'nh-seal.png')
    if os.path.exists(seal_path):
        c.drawImage(seal_path, width / 2 - 0.5 * inch, height - 2.3 * inch,
                     1 * inch, 1 * inch, preserveAspectRatio=True, mask='auto')
    else:
        # Placeholder circle
        c.setFillColor(LIGHT_NAVY)
        c.circle(width / 2, height - 1.8 * inch, 0.4 * inch, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont('Helvetica', 8)
        c.drawCentredString(width / 2, height - 1.85 * inch, 'NH')

    # Title
    c.setFillColor(NAVY)
    c.setFont('Times-Bold', 28)
    c.drawCentredString(width / 2, height - 2.8 * inch, 'Certificate of Participation')

    # Subtitle
    c.setFillColor(GOLD)
    c.setFont('Helvetica', 14)
    c.drawCentredString(width / 2, height - 3.15 * inch, 'NH EMS Week CPR Challenge 2026')

    # "This certifies that"
    c.setFillColor(DARK_TEXT)
    c.setFont('Helvetica', 12)
    c.drawCentredString(width / 2, height - 3.8 * inch, 'This certifies that')

    # Participant name
    c.setFillColor(NAVY)
    c.setFont('Times-BoldItalic', 32)
    c.drawCentredString(width / 2, height - 4.4 * inch, name)

    # Underline
    name_width = c.stringWidth(name, 'Times-BoldItalic', 32)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(width / 2 - name_width / 2 - 20, height - 4.5 * inch,
           width / 2 + name_width / 2 + 20, height - 4.5 * inch)

    # Description
    c.setFillColor(DARK_TEXT)
    c.setFont('Helvetica', 12)
    c.drawCentredString(width / 2, height - 5.0 * inch,
                         'completed Hands-Only CPR awareness training')
    c.drawCentredString(width / 2, height - 5.25 * inch,
                         'during the New Hampshire EMS Week CPR Challenge')

    # Date and location
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(width / 2, height - 5.75 * inch,
                         f'{date_str}  |  {location}')

    # Disclaimer
    c.setFillColor(HexColor('#94a3b8'))
    c.setFont('Helvetica', 8)
    c.drawCentredString(width / 2, 1.15 * inch,
                         'This certificate recognizes participation in Hands-Only CPR awareness training.')
    c.drawCentredString(width / 2, 0.95 * inch,
                         'It is NOT an official CPR certification from the American Heart Association or Red Cross.')

    # Certificate number
    c.setFont('Helvetica', 7)
    c.drawCentredString(width / 2, 0.7 * inch,
                         f'Certificate #{certificate_number}')

    # "A bipartisan initiative"
    c.setFillColor(NAVY)
    c.setFont('Helvetica', 9)
    c.drawCentredString(width / 2, height - 6.2 * inch,
                         'A bipartisan initiative of the New Hampshire Executive Council')

    c.save()
    buf.seek(0)
    return buf
