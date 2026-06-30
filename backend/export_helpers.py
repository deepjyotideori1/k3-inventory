"""Shared helpers for adding company branding (logo + title block) to Excel
exports across the app. Two engines are supported: openpyxl (Workbook) and
xlsxwriter. Both helpers degrade gracefully if a logo is missing or invalid —
the export still succeeds without a logo.

Usage (openpyxl):
    from export_helpers import get_company_info_for_export, embed_logo_openpyxl
    company = await get_company_info_for_export()
    embed_logo_openpyxl(ws, company, last_col_letter='N')
    # write your headers starting at row 5

Usage (xlsxwriter):
    from export_helpers import get_company_info_for_export, embed_logo_xlsxwriter
    company = await get_company_info_for_export()
    embed_logo_xlsxwriter(ws, workbook, company, last_col_idx=13)
    # write your headers starting at row 4 (0-indexed)
"""
from datetime import datetime
import os
import tempfile
import base64

from database import db


async def get_company_info_for_export() -> dict:
    """Fetch company branding settings. Falls back to defaults so exports never
    crash if settings are absent."""
    settings = await db.hrms_settings.find_one({'key': 'company_info'}, {'_id': 0}) or {}
    return {
        'name': settings.get('company_name', 'K3 GAS SERVICE'),
        'tagline': settings.get('tagline', ''),
        'address': settings.get('address', ''),
        'email': settings.get('email', ''),
        'helpline': settings.get('helpline', ''),
        'logo_url': settings.get('logo_url', ''),
    }


def _decode_logo_to_tempfile(logo_data_uri: str):
    """Decode a logo (data URI or /app file path) to a temp PNG/JPG. Returns
    the file path on success, None otherwise. Caller is responsible for unlink.
    """
    if not logo_data_uri:
        return None
    try:
        if logo_data_uri.startswith('data:'):
            header, data = logo_data_uri.split(',', 1)
            img_bytes = base64.b64decode(data)
            ext = '.jpg' if ('jpeg' in header or 'jpg' in header) else '.png'
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            tmp.write(img_bytes)
            tmp.close()
            return tmp.name
        if logo_data_uri.startswith('/') and os.path.isfile(logo_data_uri):
            return logo_data_uri
    except Exception:
        return None
    return None


def embed_logo_openpyxl(ws, company: dict, title: str = '', period: str = '',
                        last_col_letter: str = 'J') -> str | None:
    """Add a branded header block (logo + company name + tagline + title/period)
    to an openpyxl worksheet. Returns the temp logo path (caller should unlink
    it after `wb.save()` to clean up) or None when no logo was embedded.

    Rows used: A1 (logo + company name), A2 (tagline/address), A3 (title+period).
    Data should begin from row 5 onwards so row 4 stays blank.
    """
    from openpyxl.styles import Font, Alignment

    logo_path = _decode_logo_to_tempfile(company.get('logo_url', ''))
    if logo_path:
        try:
            from openpyxl.drawing.image import Image as XLImage
            img = XLImage(logo_path)
            img.width = 70
            img.height = 70
            ws.add_image(img, 'A1')
            ws.row_dimensions[1].height = max(ws.row_dimensions[1].height or 0, 55)
        except Exception:
            pass

    # Company name (merged across columns, leaving A column for the logo)
    ws.merge_cells(f'B1:{last_col_letter}1')
    ws['B1'] = company.get('name', '')
    ws['B1'].font = Font(name='Arial', size=14, bold=True, color='1E5A8C')
    ws['B1'].alignment = Alignment(horizontal='center', vertical='center')

    # Tagline + address
    sub_parts = []
    if company.get('tagline'):
        sub_parts.append(company['tagline'])
    if company.get('address'):
        sub_parts.append(company['address'])
    if company.get('helpline'):
        sub_parts.append(f"Helpline: {company['helpline']}")
    ws.merge_cells(f'B2:{last_col_letter}2')
    ws['B2'] = '  |  '.join(sub_parts)
    ws['B2'].font = Font(name='Arial', size=9, color='555555')
    ws['B2'].alignment = Alignment(horizontal='center', vertical='center')

    # Title + period
    bits = []
    if title:
        bits.append(title)
    if period:
        bits.append(f'Period: {period}')
    bits.append(f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    ws.merge_cells(f'A3:{last_col_letter}3')
    ws['A3'] = '   |   '.join(bits)
    ws['A3'].font = Font(name='Arial', size=9, italic=True, color='666666')
    ws['A3'].alignment = Alignment(horizontal='center')

    return logo_path


def embed_logo_xlsxwriter(ws, workbook, company: dict, title: str = '',
                          period: str = '', last_col_idx: int = 9) -> str | None:
    """Add a branded header block to an xlsxwriter worksheet. Mirrors the
    openpyxl version. Returns the temp logo path for cleanup or None.

    Rows used: row 0 (logo+name), row 1 (tagline/address), row 2 (title+period).
    Data should begin at row 4 (0-indexed) so row 3 stays blank.
    `last_col_idx` is the 0-based index of the last column to merge across.
    """
    logo_path = _decode_logo_to_tempfile(company.get('logo_url', ''))
    if logo_path:
        try:
            ws.set_row(0, 55)
            ws.insert_image(0, 0, logo_path, {
                'x_scale': 0.45, 'y_scale': 0.45,
                'x_offset': 4, 'y_offset': 4, 'object_position': 1,
            })
        except Exception:
            pass

    name_fmt = workbook.add_format({
        'bold': True, 'font_size': 14, 'font_color': '#1E5A8C',
        'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter',
    })
    sub_fmt = workbook.add_format({
        'font_size': 9, 'font_color': '#555555', 'font_name': 'Arial',
        'align': 'center', 'valign': 'vcenter',
    })
    title_fmt = workbook.add_format({
        'font_size': 9, 'italic': True, 'font_color': '#666666',
        'font_name': 'Arial', 'align': 'center',
    })

    ws.merge_range(0, 1, 0, last_col_idx, company.get('name', ''), name_fmt)

    sub_parts = []
    if company.get('tagline'):
        sub_parts.append(company['tagline'])
    if company.get('address'):
        sub_parts.append(company['address'])
    if company.get('helpline'):
        sub_parts.append(f"Helpline: {company['helpline']}")
    ws.merge_range(1, 1, 1, last_col_idx, '  |  '.join(sub_parts), sub_fmt)

    bits = []
    if title:
        bits.append(title)
    if period:
        bits.append(f'Period: {period}')
    bits.append(f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    ws.merge_range(2, 0, 2, last_col_idx, '   |   '.join(bits), title_fmt)

    return logo_path


def cleanup_logo_tempfile(logo_path):
    """Best-effort cleanup of a temp file created by the logo embedders."""
    if not logo_path:
        return
    try:
        # Only unlink files we created in /tmp (don't delete user-supplied paths)
        if logo_path.startswith(tempfile.gettempdir()):
            os.unlink(logo_path)
    except Exception:
        pass
