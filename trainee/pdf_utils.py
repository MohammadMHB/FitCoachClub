"""
تولید PDF برنامه‌ی تمرینی با reportlab.

چرا reportlab (نه WeasyPrint/Playwright)؟
    این تنها روشیه که فقط با ``pip install`` کار می‌کنه — هیچ کتابخونه‌ی
    سیستمی (pango/cairo) و هیچ دانلود مرورگر (Chromium) لازم نداره. برای
    هاستی مثل چابکان که دسترسی اینترنتی محدودی به مخازن apt/دانلود مرورگر
    داره، این مهم‌ترین مزیتشه.

نکته درباره‌ی متن فارسی:
    reportlab پشتیبانی بومی از راست‌به‌چپ نداره، برای همین با
    ``arabic_reshaper`` + ``python-bidi`` متن رو از قبل به شکل بصری صحیح
    "بازچینی" می‌کنیم. این دو کتابخونه هم صرفاً پایتونی هستن (بدون هیچ
    وابستگی سیستمی)، پس همچنان نصب روی سرور بدون دردسره.
    محدودیتش: متن داخل فایل PDF از نظر ظاهری (تو هر PDF viewer) درسته، ولی
    اگه کسی بخواد ازش کپی/سرچ کنه، چون کاراکترها فیزیکی بازچینی شدن، درست
    استخراج نمی‌شه. این trade-off آگاهانه‌ست در ازای صفر دردسر نصب.

فونت:
    از فایل‌های .ttf استفاده می‌کنیم (نه woff2، چون reportlab فقط ttf/otf
    می‌فهمه). برخلاف Chromium که Vazirmatn-Bold.ttf رو به‌خاطر یک جدول
    GPOS خراب رد می‌کرد (OTS sanitizer)، reportlab از GPOS اصلاً استفاده
    نمی‌کنه (چون شکل‌دهی حروف رو arabic_reshaper از قبل با انتخاب گلیف
    مناسب انجام می‌ده، نه از طریق فونت) — پس همون فایل ttf موجود بدون
    مشکل کار می‌کنه.

تضمین تک‌صفحه‌ای بودن:
    از ``KeepInFrame`` با ``mode='shrink'`` استفاده می‌کنیم: اگه محتوا در
    یک صفحه جا نشه، خودکار کمی کوچک‌تر می‌شه (نه اینکه به صفحه‌ی دوم بره).
"""
import os
from io import BytesIO

import arabic_reshaper
from bidi.algorithm import get_display

from django.conf import settings

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer,
    HRFlowable, KeepInFrame, KeepTogether,
)
from reportlab.platypus.flowables import _listWrapOn
from reportlab.pdfgen.canvas import Canvas as _Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ───────────────────────── فونت ──────────────────────────
FONT_DIR = os.path.join(settings.BASE_DIR, 'static', 'fonts')
_FONTS_REGISTERED = False


def _ensure_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    pdfmetrics.registerFont(TTFont('Vazir', os.path.join(FONT_DIR, 'Vazirmatn-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('VazirBold', os.path.join(FONT_DIR, 'Vazirmatn-Bold.ttf')))
    _FONTS_REGISTERED = True


def fa(text):
    """بازچینی متن فارسی برای نمایش بصری صحیح در reportlab."""
    if not text:
        return ''
    return get_display(arabic_reshaper.reshape(str(text)))


# ───────────────────────── رنگ‌ها و ثابت‌ها ─────────────────────────
INDIGO      = colors.HexColor('#4338CA')
INDIGO_SOFT = colors.HexColor('#EEF2FF')
INDIGO_MID  = colors.HexColor('#6366F1')
INK         = colors.HexColor('#1E1B2E')
MUTED       = colors.HexColor('#6B7280')
LINE        = colors.HexColor('#E5E7EB')
ROW_ALT     = colors.HexColor('#F8F8FC')
WHITE       = colors.white

# رنگ متن، رنگ پس‌زمینه، برچسب فارسی، حرف اختصاری
TAG = {
    'superset': (colors.HexColor('#2563EB'), colors.HexColor('#DBEAFE'), 'سوپرست', '#2563EB', 'S'),
    'triset':   (colors.HexColor('#C2410C'), colors.HexColor('#FFEDD5'), 'تری‌ست', '#C2410C', 'T'),
    'dropset':  (colors.HexColor('#B91C1C'), colors.HexColor('#FEE2E2'), 'دراپ‌ست', '#B91C1C', 'D'),
}
DAY_NAMES = {1: 'شنبه', 2: 'یکشنبه', 3: 'دوشنبه', 4: 'سه‌شنبه', 5: 'چهارشنبه', 6: 'پنجشنبه'}


def _ps(name, **kw):
    return ParagraphStyle(name, **kw)


def _rest_fmt(sec):
    if not sec:
        return '-'
    return f'{sec}s' if sec < 60 else f'{sec // 60}m'


def _build_day_card(day, card_w, fn, fnb):
    day_label = DAY_NAMES.get(day.day_number, str(day.day_number))
    day_reshaped = fa(day_label)
    if day.notes:
        # نکته‌ی مهم: قطعه‌ای که می‌خواهیم در خوانش راست‌به‌چپ "دومین" خونده
        # بشه (اینجا یادداشت)، باید در storage اول بیاد. نقطه‌ی جداکننده هم
        # باید داخل همین قطعه و بعد از متنِ‌reshape‌شده بیاد، وگرنه ته خط
        # تنها می‌افته.
        notes_frag = f"<font size=7.5 color='#E0E7FF'>{fa(day.notes)} ·</font>"
        title_txt = f"{notes_frag} {day_reshaped}"
    else:
        title_txt = day_reshaped

    exs = list(day.exercises.all())
    head = Table([[
        Paragraph(f"{len(exs)} {fa('حرکت')}",
                  _ps(f'cnt{day.day_number}', fontName=fn, fontSize=6.5, alignment=0,
                      textColor=colors.HexColor('#C7D2FE'))),
        Paragraph(title_txt, _ps(f'dh{day.day_number}', fontName=fnb, fontSize=10, alignment=2, textColor=WHITE)),
    ]], colWidths=[card_w * 0.3, card_w * 0.7])
    head.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), INDIGO),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 1.8), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.8),
    ]))

    hdr_labels = ['استراحت', 'ست×تکرار', 'نام حرکت', '', '#']
    col_w = [card_w * 0.17, card_w * 0.20, card_w * 0.44, card_w * 0.09, card_w * 0.10]
    hs = _ps(f'h{day.day_number}', fontName=fnb, fontSize=6.8, alignment=1, textColor=WHITE, leading=8)
    rows = [[Paragraph(fa(h), hs) for h in hdr_labels]]
    row_bg = []

    for i, wex in enumerate(exs, 1):
        stype = wex.set_type or 'normal'
        fg, bg, label, fghex, abbr = TAG.get(stype, (INK, None, '', '#666666', ''))
        name_style = _ps(f'nm{day.day_number}{i}', fontName=fnb, fontSize=7.2, alignment=1,
                          textColor=INK, leading=8.4)
        name_reshaped = fa(wex.exercise.name)
        if wex.notes:
            # نکته‌ی مهم درباره‌ی ترتیب: هر بخش را جدا reshape می‌کنیم (نه با
            # تگ HTML قاطی، چون reshape کردن متنی که تگ داخلش باشه تگ رو
            # خراب می‌کنه)، و برای اینکه در خوانش راست‌به‌چپ "اسم حرکت" اول
            # خونده بشه و "(توضیحات)" بعدش بیاد، توضیحاتِ‌ازقبل‌reshape‌شده
            # را قبل از اسم در رشته می‌چینیم.
            notes_frag = f"<font color='#999' size=6>({fa(wex.notes)})</font>"
            name_html = f"{notes_frag} {name_reshaped}"
        else:
            name_html = name_reshaped
        cs = _ps(f'c{day.day_number}{i}', fontName=fn, fontSize=6.9, alignment=1, textColor=INK, leading=8.2)

        tag_html = f"<font color='{fghex}'>{abbr}</font>" if abbr else ''
        if stype == 'dropset' and getattr(wex, 'dropset_weights', ''):
            tag_html += f"<br/><font size=5 color='#999'>{fa(wex.dropset_weights)}</font>"
        tag_style = _ps(f'tg{day.day_number}{i}', fontName=fnb, fontSize=7.5, alignment=1, leading=8)

        rows.append([
            Paragraph(fa(_rest_fmt(wex.rest_seconds)), cs),
            Paragraph(fa(f'{wex.sets}×{wex.reps}'), cs),
            Paragraph(name_html, name_style),
            Paragraph(tag_html, tag_style) if tag_html else '',
            Paragraph(str(i), _ps(f'n{day.day_number}{i}', fontName=fnb, fontSize=7.5, alignment=1,
                                   textColor=INDIGO_MID)),
        ])
        row_bg.append(bg)

    tbl_style = [
        ('BACKGROUND', (0, 0), (-1, 0), INDIGO_MID),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 1.6), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.6),
        ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]
    for idx, bg in enumerate(row_bg, 1):
        tbl_style.append(('BACKGROUND', (0, idx), (-1, idx), bg or (ROW_ALT if idx % 2 == 0 else WHITE)))

    tbl = Table(rows, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle(tbl_style))

    card = Table([[head], [tbl]], colWidths=[card_w])
    card.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('BOX', (0, 0), (-1, -1), 0.6, LINE),
    ]))
    return card


def render_program_pdf(program, profile):
    """PDF برنامه‌ی تمرینی را برمی‌گرداند (bytes). همیشه در یک صفحه."""
    _ensure_fonts()
    fn, fnb = 'Vazir', 'VazirBold'

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.0 * cm, leftMargin=1.0 * cm,
        topMargin=0.6 * cm, bottomMargin=0.5 * cm,
    )
    PAGE_W = A4[0] - 2.2 * cm
    story = []

    # ── هدر ──────────────────────────────────────────────
    header_tbl = Table([[
        Paragraph(fa(program.title), _ps('title', fontName=fnb, fontSize=15, alignment=2, textColor=INK)),
        Paragraph('FitCoach', _ps('brand', fontName=fnb, fontSize=15, alignment=0, textColor=INDIGO)),
    ]], colWidths=[PAGE_W * 0.8, PAGE_W * 0.2])
    header_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(header_tbl)
    story.append(HRFlowable(width='100%', thickness=2, color=INDIGO, spaceAfter=5, spaceBefore=2))

    # ── چیپ‌های اطلاعات ────────────────────────────────
    coach_name = profile.coach.get_full_name() if profile.coach else '-'
    weight = f"{profile.weight} kg" if profile.weight else '-'
    height = f"{profile.height} cm" if profile.height else '-'
    age = f"{profile.age} سال" if profile.age else '-'
    date_str = program.created_at.strftime('%Y/%m/%d')

    chips = [('مربی', coach_name), ('وزن', weight), ('قد', height), ('سن', age), ('تاریخ', date_str)]
    chip_cells = [
        Paragraph(f"{fa(val)} <font color='#6B7280' size=6.5>{fa(label)}</font>",
                  _ps('chip', fontName=fnb, fontSize=8, alignment=1, textColor=INK))
        for label, val in chips
    ]
    chip_tbl = Table([chip_cells], colWidths=[PAGE_W / len(chips)] * len(chips))
    chip_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), INDIGO_SOFT),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
    ]))
    story.append(chip_tbl)
    story.append(Spacer(1, 3))

    # ── راهنمای رنگ (legend) ───────────────────────────
    leg_cells = [Paragraph(f"<font color='#6B7280' size=7>{fa('راهنما:')}</font>",
                            _ps('lgt', fontName=fn, fontSize=7, alignment=1))]
    for key, (fg, bg, label, fghex, abbr) in TAG.items():
        leg_cells.append(Table([[Paragraph(fa(label), _ps(f'lg{key}', fontName=fnb, fontSize=6.5,
                                                            alignment=1, textColor=fg))]],
                                colWidths=[2.2 * cm],
                                style=TableStyle([
                                    ('BACKGROUND', (0, 0), (-1, -1), bg),
                                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                    ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                                ])))
    leg_row = Table([leg_cells], colWidths=[2 * cm] + [2.3 * cm] * 3)
    leg_row.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    story.append(leg_row)
    story.append(Spacer(1, 3))

    # اندازه‌گیری دقیق ارتفاع واقعی هدر تا فضای گرید روزها دقیق باشد
    _measure_canv = _Canvas(BytesIO(), pagesize=A4)
    _, header_h = _listWrapOn(story, PAGE_W, _measure_canv)

    # ── چیدمان: ۲ ستون در هر ردیف، راست‌چین (روز اول سمت راست) ──
    days_list = list(program.days.all())
    N_COLS = 2
    gap = 1.3 * cm
    card_w = (PAGE_W - gap * (N_COLS - 1)) / N_COLS

    grid_story = []
    for i in range(0, len(days_list), N_COLS):
        chunk = days_list[i:i + N_COLS]
        while len(chunk) < N_COLS:
            chunk.append(None)
        cards = [_build_day_card(d, card_w, fn, fnb) if d else '' for d in chunk]
        cards.reverse()  # راست‌چین: روز اول سمت راست بیفتد
        # یک ستون خالیِ واقعی بین دو کارت به‌عنوان فاصله‌گذار (نه padding)
        row = [cards[0], '', cards[1]]
        outer = Table([row], colWidths=[card_w, gap, card_w])
        outer.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        grid_story.append(outer)

    grid_story.append(HRFlowable(width='100%', thickness=0.5, color=LINE, spaceBefore=2, spaceAfter=3))
    grid_story.append(Paragraph(
        fa('FitCoach — این برنامه توسط مربی شما طراحی شده است'),
        _ps('ft', fontName=fn, fontSize=6.5, alignment=1, textColor=MUTED)))

    avail_h = A4[1] - doc.topMargin - doc.bottomMargin - header_h - 0.15 * cm
    story.append(KeepInFrame(PAGE_W, avail_h, grid_story, mode='shrink', hAlign='CENTER'))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


# ═══════════════════════ PDF رژیم غذایی ═══════════════════════

DIET_DAY_NAMES = {1: 'شنبه', 2: 'یکشنبه', 3: 'دوشنبه', 4: 'سه‌شنبه',
                   5: 'چهارشنبه', 6: 'پنجشنبه', 7: 'جمعه'}

MEAL_TYPE_LABELS = {
    'breakfast':       'صبحانه',
    'morning_snack':   'میان‌وعده صبح',
    'lunch':           'ناهار',
    'afternoon_snack': 'میان‌وعده عصر',
    'dinner':          'شام',
    'evening_snack':   'میان‌وعده شب',
}


def _build_diet_day_block(day, page_w, fn, fnb):
    day_label = DIET_DAY_NAMES.get(day.day_number, str(day.day_number))
    day_reshaped = fa(day_label)
    if day.notes:
        notes_frag = f"<font size=7.5 color='#E0E7FF'>{fa(day.notes)} ·</font>"
        title_txt = f"{notes_frag} {day_reshaped}"
    else:
        title_txt = day_reshaped

    meals = list(day.meals.all())
    head = Table([[
        Paragraph(f"{len(meals)} {fa('وعده')}",
                  _ps(f'dcnt{day.day_number}', fontName=fn, fontSize=6.5, alignment=0,
                      textColor=colors.HexColor('#C7D2FE'))),
        Paragraph(title_txt, _ps(f'ddh{day.day_number}', fontName=fnb, fontSize=10.5, alignment=2, textColor=WHITE)),
    ]], colWidths=[page_w * 0.25, page_w * 0.75])
    head.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), INDIGO),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 2.2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2),
    ]))

    col_w = [page_w * 0.22, page_w * 0.78]
    ms = _ps(f'dh{day.day_number}', fontName=fnb, fontSize=7.5, alignment=1, textColor=WHITE, leading=9)
    rows = [[Paragraph(fa('وعده'), ms), Paragraph(fa('مواد غذایی'), ms)]]

    for meal in meals:
        type_style = _ps(f'mt{day.day_number}{meal.pk}', fontName=fnb, fontSize=8, alignment=1,
                          textColor=INDIGO_MID, leading=10)
        content_lines = [fa(line) for line in meal.content.splitlines() if line.strip()]
        content_html = '<br/>'.join(content_lines) if content_lines else fa(meal.content)
        content_style = _ps(f'mc{day.day_number}{meal.pk}', fontName=fn, fontSize=8, alignment=2,
                             textColor=INK, leading=11)
        rows.append([
            Paragraph(fa(MEAL_TYPE_LABELS.get(meal.meal_type, meal.meal_type)), type_style),
            Paragraph(content_html, content_style),
        ])

    tbl_style = [
        ('BACKGROUND', (0, 0), (-1, 0), INDIGO_MID),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    for idx in range(1, len(rows)):
        if idx % 2 == 0:
            tbl_style.append(('BACKGROUND', (0, idx), (-1, idx), ROW_ALT))

    tbl = Table(rows, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle(tbl_style))

    card = Table([[head], [tbl]], colWidths=[page_w])
    card.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('BOX', (0, 0), (-1, -1), 0.6, LINE),
    ]))
    return card


def render_diet_pdf(plan, profile):
    """
    PDF رژیم غذایی را برمی‌گرداند (bytes).
    برخلاف PDF برنامه‌ی تمرینی، اینجا محتوا (متن آزاد هر وعده) می‌تونه خیلی
    متغیر و طولانی باشه، پس برخلاف برنامه‌ی تمرینی، این PDF رو در یک صفحه
    فشرده نمی‌کنیم؛ اجازه می‌دیم به‌صورت طبیعی به چند صفحه سرریز کنه تا متن
    همیشه خوانا بمونه.
    """
    _ensure_fonts()
    fn, fnb = 'Vazir', 'VazirBold'

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.0 * cm, leftMargin=1.0 * cm,
        topMargin=0.8 * cm, bottomMargin=0.7 * cm,
    )
    PAGE_W = A4[0] - 2.2 * cm
    story = []

    # ── هدر ──────────────────────────────────────────────
    header_tbl = Table([[
        Paragraph(fa(plan.title), _ps('dtitle', fontName=fnb, fontSize=15, alignment=2, textColor=INK)),
        Paragraph('FitCoach', _ps('dbrand', fontName=fnb, fontSize=15, alignment=0, textColor=INDIGO)),
    ]], colWidths=[PAGE_W * 0.8, PAGE_W * 0.2])
    header_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(header_tbl)
    story.append(HRFlowable(width='100%', thickness=2, color=INDIGO, spaceAfter=5, spaceBefore=2))

    # ── چیپ‌های اطلاعات ────────────────────────────────
    coach_name = profile.coach.get_full_name() if profile.coach else '-'
    weight = f"{profile.weight} kg" if profile.weight else '-'
    height = f"{profile.height} cm" if profile.height else '-'
    duration = f"{plan.duration_days} روز"
    date_str = plan.created_at.strftime('%Y/%m/%d')

    chips = [('مربی', coach_name), ('وزن', weight), ('قد', height), ('مدت', duration), ('تاریخ', date_str)]
    chip_cells = [
        Paragraph(f"{fa(val)} <font color='#6B7280' size=6.5>{fa(label)}</font>",
                  _ps('dchip', fontName=fnb, fontSize=8, alignment=1, textColor=INK))
        for label, val in chips
    ]
    chip_tbl = Table([chip_cells], colWidths=[PAGE_W / len(chips)] * len(chips))
    chip_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), INDIGO_SOFT),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
    ]))
    story.append(chip_tbl)

    if plan.description:
        story.append(Spacer(1, 4))
        story.append(Paragraph(fa(plan.description),
                                _ps('ddesc', fontName=fn, fontSize=8.5, alignment=2, textColor=MUTED, leading=11)))

    story.append(Spacer(1, 8))

    # ── بلوک هر روز (پشت سر هم، با سرریز طبیعی به صفحه‌ی بعد) ──
    days_list = list(plan.days.all())
    for day in days_list:
        block = _build_diet_day_block(day, PAGE_W, fn, fnb)
        story.append(KeepTogether([block, Spacer(1, 8)]))

    story.append(HRFlowable(width='100%', thickness=0.5, color=LINE, spaceBefore=2, spaceAfter=3))
    story.append(Paragraph(
        fa('FitCoach — این رژیم توسط مربی شما طراحی شده است'),
        _ps('dft', fontName=fn, fontSize=6.5, alignment=1, textColor=MUTED)))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
