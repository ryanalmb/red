"""CSV and Excel Export for Cyber-Red (Story 13.8).

This module provides CSV and Excel export for spreadsheet analysis of findings.
Supports both standard (5 columns) and extended (9 columns) output formats.

Story 13.8: CSV/Excel Export (FR38)

Usage:
    from cyberred.storage.csv_excel_exporter import (
        CSVExporter,
        ExcelExporter,
        export_findings_csv,
        export_findings_xlsx,
    )

    # Create exporter
    csv_exporter = CSVExporter()
    excel_exporter = ExcelExporter()

    # Export to string/bytes
    csv_content = csv_exporter.export(report_data)
    xlsx_bytes = excel_exporter.export(report_data)

    # Export to file
    csv_exporter.export(report_data, output_path=Path("findings.csv"))
    excel_exporter.export(report_data, output_path=Path("findings.xlsx"))

    # Export with extended columns
    csv_extended = csv_exporter.export(report_data, extended=True)
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font

if TYPE_CHECKING:
    from cyberred.storage.report_generator import ReportData

logger = logging.getLogger(__name__)

__all__ = [
    "CSVExporter",
    "ExcelExporter",
    "export_findings_csv",
    "export_findings_xlsx",
    "STANDARD_COLUMNS",
    "EXTENDED_COLUMNS",
]


# =============================================================================
# Constants
# =============================================================================

STANDARD_COLUMNS = ["severity", "type", "target", "description", "timestamp"]
EXTENDED_COLUMNS = [
    "severity",
    "type",
    "target",
    "description",
    "timestamp",
    "agent_id",
    "tool",
    "topic",
    "attck_id",
]

COLUMN_WIDTHS = {
    "A": 12,   # severity
    "B": 15,   # type
    "C": 40,   # target
    "D": 60,   # description
    "E": 25,   # timestamp
    "F": 20,   # agent_id (extended)
    "G": 15,   # tool (extended)
    "H": 20,   # topic (extended)
    "I": 15,   # attck_id (extended)
}


# =============================================================================
# Shared Helper Functions
# =============================================================================


def _map_finding_to_row(finding: dict[str, Any], extended: bool = False) -> list[str]:
    """Map finding dict to row values.

    This is a shared helper used by both CSVExporter and ExcelExporter
    to ensure consistent column mapping.

    Args:
        finding: Finding dictionary with keys like severity, type, target, etc.
        extended: Whether to include extended columns (agent_id, tool, topic, attck_id).

    Returns:
        List of string values for the row.
    """
    # Normalize timestamp - handle datetime objects and None
    timestamp = finding.get("timestamp", "")
    if hasattr(timestamp, "isoformat"):
        timestamp = timestamp.isoformat()
    elif timestamp is None:
        timestamp = ""

    row = [
        finding.get("severity") or "",
        finding.get("type") or "",
        finding.get("target") or "",
        finding.get("evidence") or "",  # 'evidence' maps to 'description' column
        str(timestamp) if timestamp else "",
    ]

    if extended:
        row.extend([
            finding.get("agent_id") or "",
            finding.get("tool") or "",
            finding.get("topic") or "",
            finding.get("attck_id") or "",
        ])

    return row


def _validate_report_data(report_data: Any) -> None:
    """Validate that report_data has required attributes.

    Args:
        report_data: Object to validate.

    Raises:
        TypeError: If report_data is not a valid ReportData-like object.
        ValueError: If report_data.findings is not iterable.
    """
    if not hasattr(report_data, "findings"):
        raise TypeError(
            f"report_data must have a 'findings' attribute, got {type(report_data).__name__}"
        )
    
    # Check findings is iterable (but not string)
    if isinstance(report_data.findings, str):
        raise ValueError("report_data.findings must be an iterable of dicts, not a string")


def _write_to_file(output_path: Path, content: str | bytes, encoding: str | None = None) -> None:
    """Write content to file with proper error handling.

    Args:
        output_path: Path to write to.
        content: String or bytes content to write.
        encoding: Encoding for text content (None for bytes).

    Raises:
        IOError: If file cannot be written with details about the error.
    """
    try:
        if isinstance(content, bytes):
            output_path.write_bytes(content)
        else:
            output_path.write_text(content, encoding=encoding or "utf-8")
        logger.debug("Exported to file: %s", output_path)
    except FileNotFoundError as e:
        raise IOError(
            f"Cannot write to '{output_path}': parent directory does not exist"
        ) from e
    except PermissionError as e:
        raise IOError(
            f"Cannot write to '{output_path}': permission denied"
        ) from e
    except OSError as e:
        raise IOError(
            f"Cannot write to '{output_path}': {e}"
        ) from e


# =============================================================================
# CSV Exporter
# =============================================================================


class CSVExporter:
    """Export findings to CSV format.

    Produces RFC 4180 compliant CSV with UTF-8 encoding and proper escaping.

    Example:
        exporter = CSVExporter()
        csv_content = exporter.export(report_data)
        exporter.export(report_data, output_path=Path("findings.csv"))
    """

    def __init__(self) -> None:
        """Initialize the CSV exporter."""

    def export(
        self,
        report_data: ReportData,
        output_path: Path | None = None,
        extended: bool = False,
    ) -> str:
        """Export findings to CSV format.

        Args:
            report_data: ReportData containing findings to export.
            output_path: Optional path to write CSV file. If None, returns string only.
            extended: If True, include extended columns (agent_id, tool, topic, attck_id).

        Returns:
            CSV content as string.

        Raises:
            TypeError: If report_data is not a valid ReportData-like object.
            IOError: If output_path cannot be written to.
        """
        _validate_report_data(report_data)
        
        columns = EXTENDED_COLUMNS if extended else STANDARD_COLUMNS
        finding_count = len(report_data.findings) if hasattr(report_data.findings, "__len__") else "unknown"
        logger.debug("Exporting %s findings to CSV (extended=%s)", finding_count, extended)

        # Create CSV in memory with Unix line endings
        output = io.StringIO(newline="")
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")

        # Write header
        writer.writerow(columns)

        # Write finding rows
        for finding in report_data.findings:
            row = _map_finding_to_row(finding, extended)
            writer.writerow(row)

        csv_content = output.getvalue()

        # Write to file if path provided
        if output_path is not None:
            _write_to_file(output_path, csv_content, encoding="utf-8")

        return csv_content


# =============================================================================
# Excel Exporter
# =============================================================================


class ExcelExporter:
    """Export findings to Excel format.

    Produces Excel workbook with formatted headers, auto-filter, and proper
    column widths using pandas and openpyxl.

    Example:
        exporter = ExcelExporter()
        xlsx_bytes = exporter.export(report_data)
        exporter.export(report_data, output_path=Path("findings.xlsx"))
    """

    def __init__(self) -> None:
        """Initialize the Excel exporter."""

    def export(
        self,
        report_data: ReportData,
        output_path: Path | None = None,
        extended: bool = False,
    ) -> bytes:
        """Export findings to Excel format.

        Args:
            report_data: ReportData containing findings to export.
            output_path: Optional path to write Excel file. If None, returns bytes only.
            extended: If True, include extended columns (agent_id, tool, topic, attck_id).

        Returns:
            Excel file content as bytes.

        Raises:
            TypeError: If report_data is not a valid ReportData-like object.
            IOError: If output_path cannot be written to.
        """
        _validate_report_data(report_data)
        
        columns = EXTENDED_COLUMNS if extended else STANDARD_COLUMNS
        finding_count = len(report_data.findings) if hasattr(report_data.findings, "__len__") else "unknown"
        logger.debug("Exporting %s findings to Excel (extended=%s)", finding_count, extended)

        # Create DataFrame
        df = self._create_dataframe(report_data.findings, extended)

        # Write to Excel in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Findings", index=False)
            
            # Get workbook and apply formatting
            workbook = writer.book
            self._apply_formatting(workbook, len(columns))

        xlsx_bytes = output.getvalue()

        # Write to file if path provided
        if output_path is not None:
            _write_to_file(output_path, xlsx_bytes)

        return xlsx_bytes

    def _create_dataframe(
        self,
        findings: Sequence[dict[str, Any]],
        extended: bool = False,
    ) -> pd.DataFrame:
        """Create DataFrame from findings.

        Args:
            findings: Sequence of finding dictionaries.
            extended: Whether to include extended columns.

        Returns:
            DataFrame with finding data.
        """
        columns = EXTENDED_COLUMNS if extended else STANDARD_COLUMNS
        rows = [_map_finding_to_row(f, extended) for f in findings]

        return pd.DataFrame(rows, columns=columns)

    def _apply_formatting(self, workbook: Workbook, num_columns: int) -> None:
        """Apply formatting to Excel workbook.

        Args:
            workbook: openpyxl Workbook to format.
            num_columns: Number of columns in the data.
        """
        ws = workbook.active
        ws.title = "Findings"

        # Header formatting (bold)
        header_font = Font(bold=True)
        for cell in ws[1]:
            cell.font = header_font

        # Auto-filter on all data (always at least header row)
        ws.auto_filter.ref = ws.dimensions

        # Column widths
        for col_letter, width in COLUMN_WIDTHS.items():
            # Only set width for columns that exist
            col_idx = ord(col_letter) - ord("A") + 1
            if col_idx <= num_columns:
                ws.column_dimensions[col_letter].width = width


# =============================================================================
# Convenience Functions
# =============================================================================


def export_findings_csv(
    report_data: ReportData,
    output_path: Path | None = None,
    extended: bool = False,
) -> str:
    """Export findings to CSV format.

    Convenience function that creates CSVExporter and exports.

    Args:
        report_data: ReportData containing findings to export.
        output_path: Optional path to write CSV file.
        extended: If True, include extended columns.

    Returns:
        CSV content as string.
    """
    exporter = CSVExporter()
    return exporter.export(report_data, output_path=output_path, extended=extended)


def export_findings_xlsx(
    report_data: ReportData,
    output_path: Path | None = None,
    extended: bool = False,
) -> bytes:
    """Export findings to Excel format.

    Convenience function that creates ExcelExporter and exports.

    Args:
        report_data: ReportData containing findings to export.
        output_path: Optional path to write Excel file.
        extended: If True, include extended columns.

    Returns:
        Excel file content as bytes.
    """
    exporter = ExcelExporter()
    return exporter.export(report_data, output_path=output_path, extended=extended)
