"""Quality Control Support Notes module for HRD daily reports.

This module provides supportive quality control feedback for UN HRD daily reports,
focusing on constructive suggestions rather than scoring or grading.
"""

from app.qc_support_notes.core import run_qc_support_notes
from app.qc_support_notes.render import render_qc_support_notes_panel

__all__ = ["run_qc_support_notes", "render_qc_support_notes_panel"]

