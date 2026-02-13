"""QC Support Notes - Generate supportive quality control notes for HRD daily reports."""
import streamlit as st
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.qc_support_notes import run_qc_support_notes, render_qc_support_notes_panel
from app.qc_support_notes.document_extractor import extract_text_from_file
from app.qc_support_notes.chat_helper import get_available_ollama_models, chat_with_report
from app.qc_support_notes import rules
from app.core.config import UNMISS_DEPLOYMENTS, OLLAMA_BASE_URL, ENABLE_OLLAMA


def main():
    """Main QC Support Notes page."""
    st.set_page_config(
        page_title="QC Support Notes",
        page_icon="📝",
        layout="wide"
    )
    
    st.title("📝 QC Support Notes")
    st.markdown("Generate supportive quality control notes for HRD daily reports and chat with your reports.")
    
    # Initialize session state for chat
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "current_report_text" not in st.session_state:
        st.session_state.current_report_text = ""
    
    # Main layout: Left (Upload) and Right (Paste Text)
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader("📄 Upload Document")
        uploaded_file = st.file_uploader(
            "Upload Daily Report",
            type=["docx", "pdf"],
            help="Upload a single Word document (.docx) or PDF file",
            key="qc_upload"
        )
        
        extracted_text = ""
        if uploaded_file is not None:
            with st.spinner("Extracting text from document..."):
                file_bytes = uploaded_file.read()
                extracted_text = extract_text_from_file(
                    file_bytes=file_bytes,
                    file_name=uploaded_file.name
                )
                
                if extracted_text:
                    st.success(f"✓ Extracted {len(extracted_text)} characters")
                    st.session_state.current_report_text = extracted_text
                    st.session_state.uploaded_text = extracted_text
                else:
                    st.error("❌ Failed to extract text. Please try pasting manually.")
    
    with col_right:
        st.subheader("📝 Paste Text")
        default_text = st.session_state.get("uploaded_text", "") if "uploaded_text" in st.session_state else ""
        report_text = st.text_area(
            "Daily Report Text",
            value=default_text,
            height=300,
            help="Paste the full text of the daily report here",
            placeholder="Field Office: Bor\nDate: 2025-01-15\n\n[Paste report text here...]",
            key="qc_report_text"
        )
        
        if report_text:
            st.session_state.current_report_text = report_text
    
    st.divider()
    
    # Metadata Section
    st.subheader("📋 Metadata (Optional)")
    meta_col1, meta_col2, meta_col3 = st.columns(3)
    
    with meta_col1:
        field_office = st.text_input(
            "Field Office",
            help="Will be auto-detected if not provided",
            placeholder="e.g., Bor, Bentiu, Juba"
        )
    
    with meta_col2:
        report_date = st.text_input(
            "Report Date",
            help="Will be auto-detected if not provided",
            placeholder="e.g., 2025-01-15"
        )
    
    with meta_col3:
        confidentiality_level = st.selectbox(
            "Confidentiality Level",
            options=["CONFIDENTIAL", "RESTRICTED", "INTERNAL", "PUBLIC"],
            index=0
        )
    
    st.divider()
    
    # Analysis Configuration
    st.subheader("🔧 Analysis Configuration")
    
    analysis_col1, analysis_col2 = st.columns(2)
    
    with analysis_col1:
        analysis_mode = st.radio(
            "Analysis Mode",
            options=["regex", "nlp", "ollama", "openai"],
            index=0,
            horizontal=True,
            help="Choose analysis method: Regex (fast, rule-based), NLP (spaCy, linguistic), Ollama (local LLM), or OpenAI (cloud LLM)"
        )
    
    with analysis_col2:
        llm_model = None
        nlp_model = None
        if analysis_mode == "nlp":
            nlp_model = st.selectbox(
                "spaCy Model",
                options=["en_core_web_sm", "en_core_web_md", "en_core_web_lg"],
                index=0,
                help="spaCy model (sm=small/fast, md=medium, lg=large/accurate). Run: python -m spacy download en_core_web_sm"
            )
        elif analysis_mode == "ollama":
            # Get available Ollama models
            ollama_models = []
            if ENABLE_OLLAMA:
                try:
                    ollama_models = get_available_ollama_models()
                except:
                    pass
            
            if ollama_models:
                llm_model = st.selectbox(
                    "Ollama Model",
                    options=ollama_models,
                    index=0 if ollama_models else None,
                    help="Select from available Ollama models"
                )
            else:
                st.warning("⚠️ Ollama not available. Check if Ollama is running.")
                llm_model = st.text_input(
                    "Ollama Model (manual)",
                    value="llama3.2:3b",
                    help="Enter model name manually"
                )
        
        elif analysis_mode == "openai":
            openai_models = list(UNMISS_DEPLOYMENTS.keys())
            llm_model = st.selectbox(
                "OpenAI Model",
                options=openai_models,
                index=0 if openai_models else None,
                help="Select Azure OpenAI deployment"
            )
    
    st.divider()
    
    # Enhanced QC Settings
    with st.expander("⚙️ Enhanced QC Settings", expanded=True):
        settings_tab1, settings_tab2, settings_tab3, settings_tab4 = st.tabs(["General", "Checks", "Terms", "Advanced"])
        
        # Initialize defaults
        enable_confidentiality = True
        show_evidence_by_default = False
        hybrid_mode = False
        check_missing_when = True
        check_vague_where = True
        check_vague_who = True
        check_facts_analysis = True
        check_corroboration = True
        check_follow_up = True
        vague_when_input = ", ".join(rules.DEFAULT_VAGUE_WHEN_TERMS)
        vague_where_input = ", ".join(rules.DEFAULT_VAGUE_WHERE_TERMS)
        interpretive_input = ", ".join(rules.DEFAULT_INTERPRETIVE_TERMS)
        definitive_verbs_input = ", ".join(rules.DEFAULT_DEFINITIVE_VERBS)
        follow_up_indicators_input = ", ".join(rules.DEFAULT_FOLLOW_UP_INDICATORS)
        min_evidence_length = 20
        max_evidence_length = 200
        context_window = 50
        
        with settings_tab1:
            col1, col2 = st.columns(2)
            with col1:
                enable_confidentiality = st.checkbox(
                    "Enable confidentiality scan",
                    value=True,
                    help="Scan for and redact PII"
                )
                show_evidence_by_default = st.checkbox(
                    "Show evidence by default",
                    value=False,
                    help="Expand evidence sections by default"
                )
                hybrid_mode = st.checkbox(
                    "Hybrid mode (LLM + Regex)",
                    value=False,
                    help="Combine LLM and regex results"
                )
            with col2:
                min_evidence_length = st.number_input(
                    "Min Evidence Length",
                    min_value=10,
                    max_value=100,
                    value=20,
                    help="Minimum characters for evidence excerpts"
                )
                max_evidence_length = st.number_input(
                    "Max Evidence Length",
                    min_value=50,
                    max_value=500,
                    value=200,
                    help="Maximum characters for evidence excerpts"
                )
                context_window = st.number_input(
                    "Context Window (chars)",
                    min_value=10,
                    max_value=200,
                    value=50,
                    help="Characters before/after for context"
                )
        
        with settings_tab2:
            st.caption("Enable/disable specific quality checks")
            col1, col2, col3 = st.columns(3)
            with col1:
                check_missing_when = st.checkbox("Check missing/vague 'When'", value=True)
                check_vague_where = st.checkbox("Check vague 'Where'", value=True)
            with col2:
                check_vague_who = st.checkbox("Check vague 'Who'", value=True)
                check_facts_analysis = st.checkbox("Check facts vs analysis", value=True)
            with col3:
                check_corroboration = st.checkbox("Check corroboration language", value=True)
                check_follow_up = st.checkbox("Check follow-up/actions", value=True)
        
        with settings_tab3:
            st.caption("Customize term lists (comma-separated)")
            vague_when_input = st.text_area(
                "Vague 'When' Terms",
                value=", ".join(rules.DEFAULT_VAGUE_WHEN_TERMS),
                height=80,
                help="Terms indicating vague temporal references"
            )
            vague_where_input = st.text_area(
                "Vague 'Where' Terms",
                value=", ".join(rules.DEFAULT_VAGUE_WHERE_TERMS),
                height=80,
                help="Terms indicating vague geographic references"
            )
            interpretive_input = st.text_area(
                "Interpretive Terms",
                value=", ".join(rules.DEFAULT_INTERPRETIVE_TERMS),
                height=80,
                help="Terms indicating interpretive/legal conclusions"
            )
        
        with settings_tab4:
            st.caption("Advanced term customization")
            definitive_verbs_input = st.text_area(
                "Definitive Verbs",
                value=", ".join(rules.DEFAULT_DEFINITIVE_VERBS),
                height=80,
                help="Verbs that require source framing"
            )
            follow_up_indicators_input = st.text_area(
                "Follow-up Indicators",
                value=", ".join(rules.DEFAULT_FOLLOW_UP_INDICATORS),
                height=80,
                help="Terms indicating follow-up or action"
            )
    
    st.divider()
    
    # Generate QC Notes Button
    generate_col1, generate_col2 = st.columns([3, 1])
    
    with generate_col1:
        generate_button = st.button(
            "🔍 Generate QC Support Notes",
            type="primary",
            use_container_width=True
        )
    
    with generate_col2:
        if "qc_result" in st.session_state:
            if st.button("🔄 Show Last Result", use_container_width=True):
                st.session_state.show_last_result = True
                st.rerun()
    
    # Generate QC Notes
    if generate_button:
        current_text = st.session_state.get("current_report_text", report_text if report_text else "")
        
        if not current_text.strip():
            st.warning("⚠️ Please upload a document or paste text to generate QC notes.")
        else:
            with st.spinner(f"Analyzing report using {analysis_mode.upper()} mode..."):
                # Prepare metadata
                metadata = {}
                if field_office:
                    metadata["field_office"] = field_office
                if report_date:
                    metadata["report_date"] = report_date
                
                # Parse term lists
                vague_when_terms = [t.strip() for t in vague_when_input.split(",") if t.strip()]
                vague_where_terms = [t.strip() for t in vague_where_input.split(",") if t.strip()]
                interpretive_terms = [t.strip() for t in interpretive_input.split(",") if t.strip()]
                definitive_verbs = [t.strip() for t in definitive_verbs_input.split(",") if t.strip()]
                follow_up_indicators = [t.strip() for t in follow_up_indicators_input.split(",") if t.strip()]
                
                # Prepare report payload
                report_payload = {
                    "report_text": current_text,
                    "metadata": metadata if metadata else None,
                    "confidentiality_level": confidentiality_level,
                    "settings": {
                        "analysis_mode": analysis_mode,
                        "llm_model": llm_model,
                        "nlp_model": nlp_model if analysis_mode == "nlp" else None,
                        "enable_confidentiality_scan": enable_confidentiality,
                        "show_evidence_by_default": show_evidence_by_default,
                        "hybrid_mode": hybrid_mode,
                        "check_missing_when": check_missing_when,
                        "check_vague_where": check_vague_where,
                        "check_vague_who": check_vague_who,
                        "check_facts_analysis": check_facts_analysis,
                        "check_corroboration": check_corroboration,
                        "check_follow_up": check_follow_up,
                        "vague_when_terms": vague_when_terms,
                        "vague_where_terms": vague_where_terms,
                        "interpretive_terms": interpretive_terms,
                        "definitive_verbs": definitive_verbs,
                        "follow_up_indicators": follow_up_indicators,
                        "min_evidence_length": min_evidence_length,
                        "max_evidence_length": max_evidence_length,
                        "context_window": context_window,
                    }
                }
                
                # Run QC analysis
                try:
                    qc_result = run_qc_support_notes(report_payload)
                    
                    # Store in session state
                    st.session_state.qc_result = qc_result
                    st.session_state.qc_report_text = current_text
                    
                    # Show analysis mode
                    if qc_result.get("analysis_mode"):
                        st.info(f"📊 Analysis completed using: **{qc_result['analysis_mode'].upper()}** mode")
                    
                    # Render QC panel
                    render_qc_support_notes_panel(st, qc_result, title="QC Support Notes")
                    
                except Exception as e:
                    st.error(f"❌ Error generating QC notes: {str(e)}")
                    import traceback
                    with st.expander("Error Details", expanded=False):
                        st.code(traceback.format_exc(), language="python")
    
    # Show previous result
    if "qc_result" in st.session_state and st.session_state.get("show_last_result", False):
        st.divider()
        render_qc_support_notes_panel(st, st.session_state.qc_result, title="QC Support Notes (Last Result)")
        if "qc_report_text" in st.session_state:
            st.caption(f"Report text length: {len(st.session_state.qc_report_text)} characters")
        st.session_state.show_last_result = False
    
    st.divider()
    
    # Chat Interface
    st.subheader("💬 Chat with Daily Report")
    st.caption("Ask questions about the daily report using various LLM models")
    
    # Check if we have report text
    chat_report_text = st.session_state.get("current_report_text", "")
    
    if not chat_report_text:
        st.info("👆 Please upload a document or paste text above to enable chat.")
    else:
        # Model selection for chat
        chat_col1, chat_col2 = st.columns([1, 2])
        
        with chat_col1:
            chat_model_type = st.radio(
                "Chat Model Type",
                options=["ollama", "openai"],
                index=0,
                horizontal=True
            )
            
            if chat_model_type == "ollama":
                chat_ollama_models = []
                if ENABLE_OLLAMA:
                    try:
                        chat_ollama_models = get_available_ollama_models()
                    except:
                        pass
                
                if chat_ollama_models:
                    chat_model = st.selectbox(
                        "Ollama Model",
                        options=chat_ollama_models,
                        index=0,
                        key="chat_ollama_model"
                    )
                else:
                    st.warning("⚠️ Ollama not available")
                    chat_model = st.text_input("Model name", value="llama3.2:3b", key="chat_ollama_manual")
            else:  # openai
                chat_openai_models = list(UNMISS_DEPLOYMENTS.keys())
                chat_model = st.selectbox(
                    "OpenAI Model",
                    options=chat_openai_models,
                    index=0,
                    key="chat_openai_model"
                )
        
        with chat_col2:
            user_question = st.text_input(
                "Ask a question about the report",
                placeholder="e.g., What incidents are mentioned? Who are the main actors?",
                key="chat_question"
            )
            
            if st.button("💬 Ask", type="primary", use_container_width=True):
                if user_question.strip():
                    with st.spinner(f"Querying {chat_model_type.upper()} model..."):
                        try:
                            response = chat_with_report(
                                chat_report_text,
                                user_question,
                                chat_model_type,
                                chat_model
                            )
                            
                            # Add to chat history
                            st.session_state.chat_messages.append({
                                "role": "user",
                                "content": user_question,
                                "model": f"{chat_model_type}:{chat_model}"
                            })
                            st.session_state.chat_messages.append({
                                "role": "assistant",
                                "content": response,
                                "model": f"{chat_model_type}:{chat_model}"
                            })
                            
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
        
        # Display chat history
        if st.session_state.chat_messages:
            st.divider()
            st.caption("Chat History")
            
            for i, msg in enumerate(st.session_state.chat_messages):
                if msg["role"] == "user":
                    with st.chat_message("user"):
                        st.write(msg["content"])
                        st.caption(f"Model: {msg.get('model', 'unknown')}")
                else:
                    with st.chat_message("assistant"):
                        st.write(msg["content"])
                        st.caption(f"Model: {msg.get('model', 'unknown')}")
            
            if st.button("🗑️ Clear Chat History", use_container_width=True):
                st.session_state.chat_messages = []
                st.rerun()


if __name__ == "__main__":
    main()
