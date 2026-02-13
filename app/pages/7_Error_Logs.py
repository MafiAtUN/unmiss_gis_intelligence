"""Error logs and diagnostics page."""
import streamlit as st
import sys
from pathlib import Path

# Add project root to Python path to ensure imports work
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import json
from datetime import datetime
from typing import List, Dict, Any
from app.core.config import LOG_FILE, DATA_DIR
from app.utils.error_handler import handle_streamlit_errors

st.title("🔍 Error Logs & Diagnostics")

# Initialize session state for filters
if "error_log_filter_level" not in st.session_state:
    st.session_state.error_log_filter_level = "ALL"
if "error_log_filter_module" not in st.session_state:
    st.session_state.error_log_filter_module = "ALL"

@handle_streamlit_errors()
def load_error_logs(log_file: Path, max_lines: int = 1000) -> List[Dict[str, Any]]:
    """Load and parse error logs from file."""
    error_logs = []
    
    if not log_file.exists():
        return error_logs
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Parse JSON logs (read from end for most recent)
        for line in reversed(lines[-max_lines:]):
            line = line.strip()
            if not line:
                continue
            try:
                log_entry = json.loads(line)
                # Only show ERROR and CRITICAL level logs
                if log_entry.get("level") in ["ERROR", "CRITICAL"]:
                    error_logs.append(log_entry)
            except json.JSONDecodeError:
                # Skip invalid JSON lines
                continue
    except Exception as e:
        st.error(f"Error reading log file: {e}")
    
    return error_logs


@handle_streamlit_errors()
def get_error_statistics(error_logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate error statistics."""
    stats = {
        "total_errors": len(error_logs),
        "by_level": {},
        "by_module": {},
        "by_error_type": {},
        "recent_errors": error_logs[:10] if error_logs else []
    }
    
    for log in error_logs:
        # Count by level
        level = log.get("level", "UNKNOWN")
        stats["by_level"][level] = stats["by_level"].get(level, 0) + 1
        
        # Count by module
        module = log.get("module", "unknown")
        stats["by_module"][module] = stats["by_module"].get(module, 0) + 1
        
        # Count by error type
        error_type = log.get("error_type", "Unknown")
        stats["by_error_type"][error_type] = stats["by_error_type"].get(error_type, 0) + 1
    
    return stats


# Main content
log_file = LOG_FILE

# File info
st.subheader("📁 Log File Information")
col1, col2, col3 = st.columns(3)

with col1:
    if log_file.exists():
        file_size = log_file.stat().st_size
        st.metric("Log File Size", f"{file_size / 1024 / 1024:.2f} MB")
    else:
        st.metric("Log File Size", "File not found")

with col2:
    if log_file.exists():
        st.metric("Log File Path", str(log_file))
    else:
        st.metric("Log File Path", "Not created yet")

with col3:
    if log_file.exists():
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        st.metric("Last Modified", mtime.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        st.metric("Last Modified", "N/A")

# Load and display errors
if log_file.exists():
    st.subheader("📊 Error Statistics")
    
    error_logs = load_error_logs(log_file)
    
    if error_logs:
        stats = get_error_statistics(error_logs)
        
        # Display statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Errors", stats["total_errors"])
        with col2:
            critical_count = stats["by_level"].get("CRITICAL", 0)
            st.metric("Critical Errors", critical_count, delta=None)
        with col3:
            error_count = stats["by_level"].get("ERROR", 0)
            st.metric("Regular Errors", error_count)
        
        # Filters
        st.subheader("🔍 Filter Errors")
        col1, col2 = st.columns(2)
        
        with col1:
            levels = ["ALL"] + list(stats["by_level"].keys())
            selected_level = st.selectbox(
                "Filter by Level",
                levels,
                index=0 if st.session_state.error_log_filter_level == "ALL" else levels.index(st.session_state.error_log_filter_level)
            )
            st.session_state.error_log_filter_level = selected_level
        
        with col2:
            modules = ["ALL"] + sorted(list(stats["by_module"].keys()))
            selected_module = st.selectbox(
                "Filter by Module",
                modules,
                index=0 if st.session_state.error_log_filter_module == "ALL" else modules.index(st.session_state.error_log_filter_module) if st.session_state.error_log_filter_module in modules else 0
            )
            st.session_state.error_log_filter_module = selected_module
        
        # Filter logs
        filtered_logs = error_logs
        if selected_level != "ALL":
            filtered_logs = [log for log in filtered_logs if log.get("level") == selected_level]
        if selected_module != "ALL":
            filtered_logs = [log for log in filtered_logs if log.get("module") == selected_module]
        
        # Error breakdown charts
        st.subheader("📈 Error Breakdown")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if stats["by_level"]:
                st.bar_chart(stats["by_level"])
                st.caption("Errors by Level")
        
        with col2:
            if stats["by_module"]:
                # Show top 10 modules
                top_modules = dict(sorted(stats["by_module"].items(), key=lambda x: x[1], reverse=True)[:10])
                st.bar_chart(top_modules)
                st.caption("Top 10 Modules by Error Count")
        
        # Error type breakdown
        if stats["by_error_type"]:
            st.subheader("🐛 Error Types")
            top_error_types = dict(sorted(stats["by_error_type"].items(), key=lambda x: x[1], reverse=True)[:10])
            st.bar_chart(top_error_types)
            st.caption("Top 10 Error Types")
        
        # Display filtered errors
        st.subheader(f"📋 Error Details ({len(filtered_logs)} errors)")
        
        if filtered_logs:
            # Pagination
            items_per_page = 10
            total_pages = (len(filtered_logs) + items_per_page - 1) // items_per_page
            page = st.number_input("Page", min_value=1, max_value=max(1, total_pages), value=1, step=1)
            
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            page_logs = filtered_logs[start_idx:end_idx]
            
            for i, log in enumerate(page_logs, start=start_idx + 1):
                timestamp = log.get("timestamp", "Unknown")
                level = log.get("level", "UNKNOWN")
                error_type = log.get("error_type", "Unknown")
                error_message = log.get("error_message", log.get("message", "No message"))
                module = log.get("module", "unknown")
                function = log.get("function", "unknown")
                
                # Color code by level
                if level == "CRITICAL":
                    st.markdown(f"### 🔴 {i}. {error_type} (CRITICAL)")
                else:
                    st.markdown(f"### ⚠️ {i}. {error_type}")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.text(f"Time: {timestamp}")
                with col2:
                    st.text(f"Module: {module}.{function}")
                with col3:
                    st.text(f"Level: {level}")
                
                st.text(f"Message: {error_message}")
                
                # Show traceback if available
                if "traceback" in log:
                    with st.expander("📜 View Traceback", expanded=False):
                        st.code(log["traceback"], language="python")
                
                # Show additional context
                context_keys = [k for k in log.keys() if k not in ["timestamp", "level", "error_type", "error_message", "message", "traceback", "module", "function"]]
                if context_keys:
                    with st.expander("🔍 View Context", expanded=False):
                        context = {k: log[k] for k in context_keys}
                        st.json(context)
                
                st.divider()
            
            st.caption(f"Showing {len(page_logs)} of {len(filtered_logs)} errors (Page {page} of {total_pages})")
        else:
            st.info("No errors match the selected filters.")
    else:
        st.success("✅ No errors found in logs! The application is running smoothly.")
        
        # Show some helpful information
        st.info("""
        **Tips:**
        - Errors are automatically logged when they occur
        - Check the log file at: `{log_file}`
        - Errors are logged with full context including module, function, and traceback
        - Critical errors are automatically sent to error tracking (if configured)
        """.format(log_file=log_file))
else:
    st.warning("⚠️ Log file not found. Errors will be logged once the application starts generating logs.")
    st.info(f"Expected log file location: `{log_file}`")

# Actions
st.subheader("⚙️ Actions")
col1, col2 = st.columns(2)

with col1:
    if st.button("🔄 Refresh Logs"):
        st.rerun()

with col2:
    if log_file.exists():
        if st.button("📥 Download Log File"):
            with open(log_file, 'rb') as f:
                st.download_button(
                    label="Download",
                    data=f.read(),
                    file_name=log_file.name,
                    mime="text/plain"
                )

