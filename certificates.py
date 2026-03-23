"""PDF certificate generation using ReportLab."""

import os
from io import BytesIO
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

NAVY = HexColor('#0d1b2a')
NAVY_MED = HexColor('#1e3a5f')
GOLD = HexColor('#c5a55a')
DARK_TEXT = HexColor('#1a1a2e')
GRAY = HexColor('#64748b')

# Register Lato font family
_fonts_dir = os.path.join(os.path.dirname(__file__), 'static', 'fonts')
pdfmetrics.registerFont(TTFont('Lato', os.path.join(_fonts_dir, 'Lato-Regular.ttf')))
pdfmetrics.registerFont(TTFont('Lato-Bold', os.path.join(_fonts_dir, 'Lato-Bold.ttf')))
pdfmetrics.registerFont(TTFont('Lato-Italic', os.path.join(_fonts_dir, 'Lato-Italic.ttf')))


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

    # Background image (full-page ornate border)
    bg_path = os.path.join(os.path.dirname(__file__), 'static', 'img', 'cert_background.png')
    if os.path.exists(bg_path):
        c.drawImage(bg_path, 0, 0, width, height)

    # NH state seal
    seal_path = os.path.join(os.path.dirname(__file__), 'static', 'img', 'nh-seal.png')
    seal_size = 1.15 * inch
    if os.path.exists(seal_path):
        c.drawImage(seal_path,
                     width / 2 - seal_size / 2, height - 2.35 * inch,
                     seal_size, seal_size,
                     preserveAspectRatio=True, mask='auto')

    # Title
    c.setFillColor(NAVY)
    c.setFont('Times-Bold', 30)
    c.drawCentredString(width / 2, height - 2.8 * inch, 'Certificate of Participation')

    # Subtitle
    c.setFillColor(GOLD)
    c.setFont('Lato', 12)
    c.drawCentredString(width / 2, height - 3.15 * inch, 'NH EMS Week CPR Challenge 2026')

    # "This certifies that"
    c.setFillColor(DARK_TEXT)
    c.setFont('Lato', 11)
    c.drawCentredString(width / 2, height - 3.7 * inch, 'This certifies that')

    # Participant name
    c.setFillColor(NAVY)
    name_font_size = 34
    if len(name) > 25:
        name_font_size = 28
    if len(name) > 35:
        name_font_size = 24
    c.setFont('Times-BoldItalic', name_font_size)
    name_y = height - 4.3 * inch
    c.drawCentredString(width / 2, name_y, name)

    # Gold underline beneath name
    name_width = c.stringWidth(name, 'Times-BoldItalic', name_font_size)
    line_extend = 30
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.25)
    c.line(width / 2 - name_width / 2 - line_extend, name_y - 8,
           width / 2 + name_width / 2 + line_extend, name_y - 8)

    # Description
    c.setFillColor(DARK_TEXT)
    c.setFont('Lato', 11)
    c.drawCentredString(width / 2, height - 4.85 * inch,
                         'completed Hands-Only CPR awareness training')
    c.drawCentredString(width / 2, height - 5.1 * inch,
                         'during the New Hampshire EMS Week CPR Challenge')

    # Date and location
    c.setFont('Lato-Bold', 11)
    date_loc = f'{date_str}  |  {location}'
    c.drawCentredString(width / 2, height - 5.55 * inch, date_loc)

    # "A bipartisan initiative"
    c.setFillColor(NAVY_MED)
    c.setFont('Lato', 9)
    c.drawCentredString(width / 2, height - 5.95 * inch,
                         'A Bipartisan Initiative of the New Hampshire Executive Council')

    # Disclaimer
    c.setFillColor(GRAY)
    c.setFont('Lato', 7.5)
    c.drawCentredString(width / 2, 1.55 * inch,
                         'This certificate recognizes participation in Hands-Only CPR awareness training.')
    c.drawCentredString(width / 2, 1.35 * inch,
                         'It is NOT an official CPR certification from the American Heart Association, Red Cross, or any other certifying body.')

    # Certificate number
    c.setFont('Lato', 7)
    c.drawCentredString(width / 2, 1.15 * inch,
                         f'Certificate #{certificate_number}')

    c.save()
    buf.seek(0)
    return buf
