from io import BytesIO
import re

from django.http import FileResponse
from django.utils.translation import get_language_bidi, gettext as _
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .models import Payment
from .queries import filter_payments, payment_totals


def event_workbook(event, gifts, method, currency=""):
    payments = filter_payments(Payment.objects.filter(gift__in=gifts.order_by().values("pk")), method, currency)
    payments = payments.select_related("gift__group", "payer").prefetch_related(
        "covered_guests", "gift__recipients", "gift__payments",
    ).order_by("gift__group__name", "gift_id", "pk")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = _("Payments")
    sheet.sheet_view.rightToLeft = get_language_bidi()
    sheet.append([_("Group name"), _("Payer name"), _("Number of people"), _("Amount"), _("Payment method")])
    for payment in payments:
        covered = list(payment.covered_guests.all())
        if not covered and len(payment.gift.payments.all()) == 1:
            covered = list(payment.gift.recipients.all())
        names = ", ".join(guest.name for guest in covered)
        sheet.append([
            payment.gift.group.name, payment.payer.name, f"{len(covered)} ({names})" if covered else None,
            payment.amount, str(payment.get_method_display()),
        ])
        for column in ("A", "B", "E"):
            sheet[f"{column}{sheet.max_row}"].data_type = "s"
        sheet[f"D{sheet.max_row}"].number_format = currency_format(payment.get_currency_display())
        sheet[f"C{sheet.max_row}"].alignment = Alignment(wrap_text=True)

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        sheet.column_dimensions[cell.column_letter].width = 22
    sheet.column_dimensions["C"].width = 36
    add_gift_statistics(workbook, event, payments)
    return workbook_download(workbook, event, _("Gifts"))


def add_gift_statistics(workbook, event, payments):
    stats = workbook.create_sheet(_("Statistics"))
    rtl = get_language_bidi()
    stats.sheet_view.rightToLeft = rtl
    stats.sheet_view.showGridLines = False
    for column, width in zip("ABC", (36, 16, 23)):
        stats.column_dimensions[column].width = width

    start = "right" if rtl else "left"
    end = "left" if rtl else "right"

    def band(row, text, fill, color, size, height):
        stats.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
        cell = stats.cell(row, 1, text)
        cell.data_type = "s"
        cell.fill = PatternFill("solid", fgColor=fill)
        cell.font = Font(name="Arial", size=size, bold=True, color=color)
        cell.alignment = Alignment(horizontal=start, vertical="center", indent=1)
        stats.row_dimensions[row].height = height

    def table_row(row, values, fill, *, bold=False, symbol=None, height=26):
        for column, value in enumerate(values, start=1):
            cell = stats.cell(row, column, value)
            cell.fill = PatternFill("solid", fgColor=fill)
            cell.font = Font(name="Arial", size=11, bold=bold, color="38213E")
            cell.alignment = Alignment(horizontal=end if column == 3 else start, vertical="center", indent=1)
        if symbol:
            stats.cell(row, 3).number_format = currency_format(symbol)
        stats.row_dimensions[row].height = height

    band(1, _("Statistics"), "38213E", "FFFFFF", 24, 44)
    band(2, event.name, "59346B", "FFFFFF", 14, 31)
    table_row(4, [_("Gifts"), None, len({payment.gift_id for payment in payments})], "F0E4F7", bold=True)
    table_row(5, [_("Payments"), None, len(payments)], "FAF1DD", bold=True)

    totals, breakdown = payment_totals(payments)
    band(7, _("Total received"), "FFCB4C", "38213E", 14, 30)
    if not totals:
        band(8, _("No gifts recorded yet"), "FAF1DD", "38213E", 11, 28)
        return

    codes = {symbol: code for code, symbol in Payment.Currency.choices}
    for row, (symbol, amount) in enumerate(totals, start=8):
        table_row(row, [_("Currency"), codes[symbol], amount], "FAF1DD", bold=True, symbol=symbol)

    heading = 9 + len(totals)
    band(heading, _("Payment breakdown"), "59346B", "FFFFFF", 14, 30)
    table_row(heading + 1, [_("Payment method"), _("Currency"), _("Amount")], "EBDDF3", bold=True)
    for index, (label, symbol, amount) in enumerate(breakdown):
        fill = "F7EFFB" if index % 2 == 0 else "FFFAEC"
        table_row(heading + 2 + index, [str(label), codes[symbol], amount], fill, symbol=symbol)


def currency_format(symbol):
    return f'"{symbol}"#,##0.00'


def guest_workbook(event):
    groups = list(event.groups.prefetch_related("guests"))
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = _("Guest list")
    sheet.append([_("Group name"), _("Guests"), _("Group notes")])
    for group in groups:
        sheet.append([group.name, ", ".join(guest.name for guest in group.guests.all()), group.notes])
        for cell in sheet[sheet.max_row]:
            cell.data_type = "s"
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column, width in zip("ABC", (28, 48, 50)):
        sheet.column_dimensions[column].width = width

    summary = workbook.create_sheet(_("Event summary"))
    summary.append([_("Event details"), event.name])
    summary.append([_("Event date"), event.event_date])
    if event.event_date:
        summary["B2"].number_format = "dd/mm/yyyy"
    summary.append([_("Venue"), event.venue])
    summary.append([_("Event notes"), event.notes])
    summary.append([_("Guest groups"), len(groups)])
    summary.append([_("Guests"), sum(len(group.guests.all()) for group in groups)])
    summary.column_dimensions["A"].width = 25
    summary.column_dimensions["B"].width = 56
    for cell in (summary["B1"], summary["B3"], summary["B4"]):
        cell.data_type = "s"
        cell.alignment = Alignment(wrap_text=True)
    for tab in (sheet, summary):
        tab.sheet_view.rightToLeft = get_language_bidi()
        for cell in tab[1]:
            cell.font = Font(bold=True)
    return workbook_download(workbook, event, _("Guest list"))


def workbook_download(workbook, event, report_name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", event.name).strip(" .")[:100] or str(event.pk)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return FileResponse(output, as_attachment=True, filename=f"Trunemo - {name} - {report_name}.xlsx")
