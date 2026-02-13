"""Streamlit rendering helpers for QC support notes."""

from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import streamlit as st


def render_qc_support_notes_panel(
    st,
    qc_result: Dict,
    *,
    title: str = "QC Support Notes"
) -> None:
    """Render QC support notes as a panel in a Streamlit page.
    
    This function renders:
    - A compact text area with support_notes (copy-paste ready)
    - A collapsible "Details" section showing issues with redacted evidence
    
    Args:
        st: Streamlit module (imported as `import streamlit as st`, pass `st` here).
        qc_result: Dict returned from run_qc_support_notes.
        title: Optional title for the panel.
    """
    st.subheader(title)
    
    # Display support notes in a text area for easy copy-paste
    support_notes = qc_result.get("support_notes", "")
    st.text_area(
        "Support Notes (copy-paste ready)",
        value=support_notes,
        height=200,
        help="Copy these notes to paste into your report review workflow.",
        key="qc_support_notes_display"
    )
    
    # Collapsible details section
    with st.expander("Details", expanded=False):
        issues = qc_result.get("issues", [])
        redactions = qc_result.get("redactions", [])
        detected_header = qc_result.get("detected_header")
        
        # Show detected header if available
        if detected_header:
            st.caption("**Detected header information:**")
            if detected_header.get("field_office"):
                st.write(f"Field Office: {detected_header['field_office']}")
            if detected_header.get("report_date"):
                st.write(f"Report Date: {detected_header['report_date']}")
            st.divider()
        
        # Show redactions if any
        if redactions:
            st.caption("**Redactions detected:**")
            redaction_summary = {}
            for r in redactions:
                r_type = r.get("type", "unknown")
                redaction_summary[r_type] = redaction_summary.get(r_type, 0) + 1
            
            for r_type, count in redaction_summary.items():
                st.write(f"• {r_type.capitalize()}: {count} instance(s)")
            st.info("⚠️ Evidence excerpts have been redacted to protect confidentiality.")
            st.divider()
        
        # Show issues
        if issues:
            st.caption(f"**Issues found ({len(issues)}):**")
            
            # Group by severity
            attention_issues = [i for i in issues if i.get("severity") == "attention"]
            note_issues = [i for i in issues if i.get("severity") == "note"]
            
            if attention_issues:
                st.markdown("**Items for attention:**")
                for idx, issue in enumerate(attention_issues, 1):
                    with st.container():
                        st.markdown(f"**{idx}.** {issue.get('message', '')}")
                        evidence = issue.get("evidence", "")
                        if evidence:
                            st.code(evidence, language="text")
                        if issue.get("location"):
                            loc = issue["location"]
                            st.caption(f"Position: {loc.get('start_char')}-{loc.get('end_char')}")
                        st.divider()
            
            if note_issues:
                st.markdown("**Optional refinements:**")
                for idx, issue in enumerate(note_issues, 1):
                    with st.container():
                        st.markdown(f"**{idx}.** {issue.get('message', '')}")
                        evidence = issue.get("evidence", "")
                        if evidence:
                            st.code(evidence, language="text")
                        if issue.get("location"):
                            loc = issue["location"]
                            st.caption(f"Position: {loc.get('start_char')}-{loc.get('end_char')}")
                        st.divider()
        else:
            st.success("✓ No issues identified.")
        
        # Show redactions list if detailed view needed
        if redactions and len(redactions) > 0:
            with st.expander("Redactions detail", expanded=False):
                for idx, r in enumerate(redactions, 1):
                    st.write(f"**{idx}.** Type: {r.get('type')} | Masked: {r.get('masked')}")


# Example usage snippet (in a comment block):
"""
# Example usage in a Streamlit page:

import streamlit as st
from app.qc_support_notes import run_qc_support_notes, render_qc_support_notes_panel

# In your page function:
def my_page():
    st.title("HRD Daily Report QC")
    
    report_text = st.text_area("Paste report text here")
    
    if st.button("Generate QC Notes"):
        report_payload = {
            "report_text": report_text,
            "metadata": {
                "field_office": "Bor",  # optional
                "report_date": "2025-01-15",  # optional
            },
            "confidentiality_level": "CONFIDENTIAL",
            "settings": {
                "enable_confidentiality_scan": True,
                "show_evidence_by_default": False,
            }
        }
        
        qc_result = run_qc_support_notes(report_payload)
        
        render_qc_support_notes_panel(st, qc_result, title="QC Support Notes")
        
        # Optionally use the result programmatically:
        # for issue in qc_result["issues"]:
        #     print(f"Issue: {issue['key']} - {issue['message']}")
"""

