"""
LeadNexus AI X — Saved Leads Export Service
Phase 12: CSV and Excel Export
CRITICAL RULE:
The export endpoint must query the saved_leads table rather than the temporary search results.
Never export search results that have not been added.
"""

import io
import csv
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import Response
from sqlalchemy.orm import Session
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.services.saved_lead_service import SavedLeadService


class SavedLeadExportService:
    """
    Exports strictly user-saved leads from PostgreSQL/SQLite to CSV and Excel (XLSX).
    """

    EXPORT_COLUMNS = [
        "Company Name",
        "Website",
        "Industry",
        "Country",
        "State",
        "City",
        "Description",
        "Decision Maker",
        "Job Title",
        "Business Email",
        "Email Verification Status",
        "Business Phone",
        "Phone Verification Status",
        "LinkedIn URL",
        "Source Name",
        "Source URL",
        "Evidence",
        "Search Keyword",
        "Date Saved",
    ]

    @classmethod
    def _fetch_records(cls, db: Session, filters: Optional[Dict[str, Any]] = None):
        """Fetches all records from saved_leads table."""
        filters = filters or {}
        items, _ = SavedLeadService.list_saved_leads(
            db=db,
            search=filters.get("search"),
            company=filters.get("company"),
            location=filters.get("location"),
            industry=filters.get("industry"),
            job_title=filters.get("job_title"),
            limit=10000,
            offset=0,
        )
        return items

    @classmethod
    def generate_csv_response(cls, db: Session, filters: Optional[Dict[str, Any]] = None) -> Response:
        """
        Generates RFC 4180 compliant CSV stream with UTF-8 BOM encoding.
        """
        records = cls._fetch_records(db, filters)
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"leadnexus_saved_leads_{timestamp_str}.csv"

        output = io.StringIO()
        # Write UTF-8 BOM for seamless Excel compatibility
        output.write("\ufeff")

        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(cls.EXPORT_COLUMNS)

        for r in records:
            writer.writerow([
                r["company_name"],
                r["website"],
                r["industry"],
                r["country"],
                r["state"],
                r["city"],
                r["description"],
                r["decision_maker_name"],
                r["job_title"],
                r["business_email"],
                r["email_status"],
                r["business_phone"],
                r["phone_status"],
                r["linkedin_url"],
                r["source_name"],
                r["source_url"],
                r["evidence"],
                r["search_keyword"],
                r["saved_at"],
            ])

        csv_content = output.getvalue().encode("utf-8")
        return Response(
            content=csv_content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

    @classmethod
    def generate_excel_response(cls, db: Session, filters: Optional[Dict[str, Any]] = None) -> Response:
        """
        Generates formatted XLSX workbook using OpenPyXL with styled headers and adjusted columns.
        """
        records = cls._fetch_records(db, filters)
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"leadnexus_saved_leads_{timestamp_str}.xlsx"

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Saved Leads"

        # Header Styles
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=False)
        thin_border = Border(
            left=Side(style="thin", color="CCCCCC"),
            right=Side(style="thin", color="CCCCCC"),
            top=Side(style="thin", color="CCCCCC"),
            bottom=Side(style="thin", color="CCCCCC"),
        )

        # Write Header Row
        for col_idx, col_name in enumerate(cls.EXPORT_COLUMNS, start=1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border

        # Write Data Rows
        data_font = Font(name="Calibri", size=10)
        data_alignment = Alignment(vertical="center")

        for row_idx, r in enumerate(records, start=2):
            values = [
                r["company_name"],
                r["website"],
                r["industry"],
                r["country"],
                r["state"],
                r["city"],
                r["description"],
                r["decision_maker_name"],
                r["job_title"],
                r["business_email"],
                r["email_status"],
                r["business_phone"],
                r["phone_status"],
                r["linkedin_url"],
                r["source_name"],
                r["source_url"],
                r["evidence"],
                r["search_keyword"],
                r["saved_at"],
            ]
            for col_idx, val in enumerate(values, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val if val != "Not Found" else "")
                cell.font = data_font
                cell.alignment = data_alignment
                cell.border = thin_border

        # Auto-fit column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 50)

        # Freeze header row
        ws.freeze_panes = "A2"

        excel_stream = io.BytesIO()
        wb.save(excel_stream)
        excel_content = excel_stream.getvalue()

        return Response(
            content=excel_content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

