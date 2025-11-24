"""
Operational Risk Assessor - Streamlit UI
Main application interface for uploading Excel files and running risk assessments
"""

import os
import streamlit as st
import pandas as pd
import requests
from risk_assessor import (
    parse_excel,
    run_assessment,
    call_vllm
)

# Page configuration
st.set_page_config(
    page_title="Operational Risk Assessor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'df' not in st.session_state:
    st.session_state.df = None
if 'column_mapping' not in st.session_state:
    st.session_state.column_mapping = None
if 'assessment_results' not in st.session_state:
    st.session_state.assessment_results = {}


# ==================== HELPER FUNCTIONS ====================

def check_vllm_server(api_base: str) -> bool:
    """Check if vLLM server is available"""
    try:
        response = requests.get(f"{api_base}/models", timeout=5)
        return response.status_code == 200
    except:
        return False


# ==================== SIDEBAR CONFIGURATION ====================

with st.sidebar:
    st.header("Configuration")
    
    # vLLM Configuration
    st.subheader("vLLM Server")
    vllm_api_base = st.text_input(
        "vLLM API Base URL",
        value=os.getenv("VLLM_API_BASE", "http://localhost:8002/v1"),
        help="URL of your vLLM server"
    )
    
    vllm_model = st.text_input(
        "vLLM Model Name",
        value=os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-72B-Instruct"),
        help="Model name as configured in vLLM server"
    )
    
    # Check server status
    if st.button("Check vLLM Server"):
        if check_vllm_server(vllm_api_base):
            st.success("vLLM server is running")
        else:
            st.error("vLLM server is not accessible")
    
    st.divider()
    
    # Internet Search Configuration
    st.subheader("Internet Search")
    search_method = st.selectbox(
        "Search Method",
        options=["combined", "ddgs", "google", "searxng", "playwright"],
        index=0,
        help="'Combined' uses ALL available search methods (recommended). Individual methods use only that specific search engine."
    )
    
    searxng_url = None
    if search_method == "searxng":
        searxng_url = st.text_input(
            "SearXNG URL",
            value="",
            help="URL of your self-hosted SearXNG instance (e.g., http://localhost:8080)"
        )


# ==================== MAIN APP ====================

st.title("Operational Risk Assessor")
st.markdown("Upload an Excel file with company risk data and assess risk ratings using LLM analysis")

# Tabs
tab1, tab2 = st.tabs(["Upload & View", "Risk Assessment"])

# ==================== TAB 1: UPLOAD & VIEW ====================

with tab1:
    st.header("Upload Excel File")
    
    # Load default dummy file if not already loaded
    default_file_path = os.path.join(os.path.dirname(__file__), "dummy_companies.xlsx")
    use_default = st.checkbox("Use default sample data (15 companies)", value=True, help="Loads dummy_companies.xlsx by default")
    
    uploaded_file = st.file_uploader(
        "Or upload your own Excel file",
        type=['xlsx', 'xls'],
        help="Upload Excel file with columns: Company, Questionnaire columns, Comments, Risk Rating"
    )
    
    # Determine which file to use
    file_to_use = None
    file_source = None
    
    if uploaded_file is not None:
        file_to_use = uploaded_file
        file_source = "uploaded"
        st.info("📤 Using uploaded file")
    elif use_default and os.path.exists(default_file_path):
        file_to_use = default_file_path
        file_source = "default"
        st.info("📋 Using default sample data (dummy_companies.xlsx)")
    
    if file_to_use is not None:
        try:
            # parse_excel can handle both file paths and file objects
            df, column_mapping = parse_excel(file_to_use)
            st.session_state.df = df
            st.session_state.column_mapping = column_mapping
            
            st.success(f"File loaded successfully! Found {len(df)} rows")
            
            # Display column mapping
            st.subheader("Detected Columns")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Company Column", column_mapping.get('company', 'Not found'))
            with col2:
                st.metric("Comments Column", column_mapping.get('comments', 'Not found'))
            with col3:
                st.metric("Risk Rating Column", column_mapping.get('risk_rating', 'Not found'))
            with col4:
                st.metric("Questionnaire Columns", len(column_mapping.get('questionnaire', [])))
            
            # Display sample data
            st.subheader("Sample Data (First 20 Rows)")
            st.dataframe(df.head(20), use_container_width=True)
            
            # Show all companies
            if column_mapping.get('company'):
                st.subheader("Companies in Dataset")
                companies = df[column_mapping['company']].dropna().unique().tolist()
                st.write(f"Total companies: {len(companies)}")
                st.write(", ".join(companies[:50]))  # Show first 50
                if len(companies) > 50:
                    st.write(f"... and {len(companies) - 50} more")
        
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")
            st.session_state.df = None
            st.session_state.column_mapping = None

# ==================== TAB 2: RISK ASSESSMENT ====================

with tab2:
    st.header("Risk Assessment")
    
    if st.session_state.df is None or st.session_state.column_mapping is None:
        st.warning("Please upload an Excel file in the 'Upload & View' tab first")
    else:
        df = st.session_state.df
        column_mapping = st.session_state.column_mapping
        
        # Company selection
        company_col = column_mapping.get('company')
        if not company_col:
            st.error("Company column not found in the Excel file")
        else:
            companies = df[company_col].dropna().unique().tolist()
            selected_companies = st.multiselect(
                "Select Companies to Assess",
                options=companies,
                help="Select one or more companies to assess"
            )
            
            if selected_companies:
                # Assessment options
                st.subheader("Assessment Options")
                col1, col2, col3 = st.columns(3)
                with col1:
                    assess_questionnaire = st.checkbox("Assess based on questionnaire answers", value=True)
                with col2:
                    assess_comments = st.checkbox("Assess based on comments", value=True)
                with col3:
                    assess_internet = st.checkbox("Assess based on internet search", value=True)
                
                assessment_types = []
                if assess_questionnaire:
                    assessment_types.append("questionnaire")
                if assess_comments:
                    assessment_types.append("comments")
                if assess_internet:
                    assessment_types.append("internet")
                
                if not assessment_types:
                    st.warning("Please select at least one assessment type")
                else:
                    # Run assessment button
                    if st.button("Run Assessment", type="primary", use_container_width=True):
                        vllm_config = {
                            "api_base": vllm_api_base,
                            "model": vllm_model
                        }
                        
                        # Process each selected company
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        results_dict = {}
                        
                        for idx, company_name in enumerate(selected_companies):
                            status_text.text(f"Assessing {company_name} ({idx+1}/{len(selected_companies)})...")
                            progress_bar.progress((idx + 1) / len(selected_companies))
                            
                            # Get company data
                            company_row = df[df[company_col] == company_name].iloc[0]
                            
                            # Extract questionnaire data
                            questionnaire_data = {}
                            for col in column_mapping.get('questionnaire', []):
                                if col in company_row and pd.notna(company_row[col]):
                                    questionnaire_data[col] = str(company_row[col])
                            
                            # Extract comments
                            comments_col = column_mapping.get('comments')
                            comments = company_row[comments_col] if comments_col and comments_col in company_row else ""
                            
                            # Extract current rating
                            rating_col = column_mapping.get('risk_rating')
                            current_rating = str(company_row[rating_col]) if rating_col and rating_col in company_row else "Unknown"
                            
                            # Run assessment
                            try:
                                result = run_assessment(
                                    company_name=company_name,
                                    questionnaire_data=questionnaire_data,
                                    comments=comments,
                                    current_rating=current_rating,
                                    assessment_types=assessment_types,
                                    search_method=search_method,
                                    searxng_url=searxng_url if search_method == "searxng" else None,
                                    vllm_config=vllm_config
                                )
                                results_dict[company_name] = result
                            except Exception as e:
                                st.error(f"Error assessing {company_name}: {str(e)}")
                                results_dict[company_name] = {
                                    "company_name": company_name,
                                    "current_rating": current_rating,
                                    "error": str(e),
                                    "assessments": {}
                                }
                        
                        st.session_state.assessment_results = results_dict
                        status_text.text("Assessment complete!")
                        progress_bar.empty()
                        st.rerun()
                
                # Display results
                if st.session_state.assessment_results:
                    st.divider()
                    st.subheader("Assessment Results")
                    
                    for company_name in selected_companies:
                        if company_name in st.session_state.assessment_results:
                            result = st.session_state.assessment_results[company_name]
                            
                            with st.expander(f"{company_name} - Current Rating: {result.get('current_rating', 'Unknown')}", expanded=True):
                                # Summary table at top with all sources
                                assessments = result.get("assessments", {})
                                summary_data = []
                                
                                if "questionnaire" in assessments:
                                    q_result = assessments["questionnaire"]
                                    summary_data.append({
                                        "Source": "Questionnaire",
                                        "Rating from Source": q_result.get("recommended_rating", "Unknown"),
                                        "Rating from File": result.get("current_rating", "Unknown")
                                    })
                                
                                if "comments" in assessments:
                                    c_result = assessments["comments"]
                                    summary_data.append({
                                        "Source": "Comments",
                                        "Rating from Source": c_result.get("recommended_rating", "Unknown"),
                                        "Rating from File": result.get("current_rating", "Unknown")
                                    })
                                
                                if "internet" in assessments:
                                    i_result = assessments["internet"]
                                    summary_data.append({
                                        "Source": "Internet",
                                        "Rating from Source": i_result.get("recommended_rating", "Unknown"),
                                        "Rating from File": result.get("current_rating", "Unknown")
                                    })
                                
                                if summary_data:
                                    st.markdown("### Overall Assessment Summary")
                                    summary_df = pd.DataFrame(summary_data)
                                    st.dataframe(summary_df, use_container_width=True, hide_index=True)
                                    st.divider()
                                
                                # Assessment results
                                st.markdown("### Assessment Results")
                                
                                if "questionnaire" in assessments:
                                    q_result = assessments["questionnaire"]
                                    st.markdown("#### Questionnaire Assessment")
                                    recommended = q_result.get("recommended_rating", "Unknown")
                                    st.markdown(f"**Rating:** {recommended}")
                                    st.markdown("**Explanation:**")
                                    st.write(q_result.get("explanation", "No explanation provided"))
                                    st.divider()
                                
                                if "comments" in assessments:
                                    c_result = assessments["comments"]
                                    st.markdown("#### Comments Assessment")
                                    recommended = c_result.get("recommended_rating", "Unknown")
                                    st.markdown(f"**Rating:** {recommended}")
                                    st.markdown("**Explanation:**")
                                    st.write(c_result.get("explanation", "No explanation provided"))
                                    st.divider()
                                
                                if "internet" in assessments:
                                    i_result = assessments["internet"]
                                    st.markdown("#### Internet Search Assessment")
                                    recommended = i_result.get("recommended_rating", "Unknown")
                                    st.markdown(f"**Rating:** {recommended}")
                                    
                                    # Show table with extracted information
                                    url_details = i_result.get("url_details", [])
                                    if url_details:
                                        st.markdown("**Extracted Information Sources:**")
                                        table_data = []
                                        for ud in url_details:
                                            url = ud.get("url", "")
                                            title = ud.get("title", "No title")
                                            tool = ud.get("tool", "Unknown")
                                            content = ud.get("content", "")
                                            # Extract risk-related snippet
                                            risk_snippet = content[:200] + "..." if len(content) > 200 else content
                                            table_data.append({
                                                "Relevant Information": risk_snippet,
                                                "Portal/URL": url,  # Store URL for LinkColumn
                                                "Tool": tool
                                            })
                                        
                                        if table_data:
                                            df_table = pd.DataFrame(table_data)
                                            # Display as dataframe with clickable links showing full URL
                                            st.dataframe(
                                                df_table,
                                                use_container_width=True,
                                                hide_index=True,
                                                column_config={
                                                    "Portal/URL": st.column_config.LinkColumn(
                                                        "Portal/URL"
                                                    )
                                                }
                                            )
                                        st.divider()
                                    
                                    st.markdown("**Explanation:**")
                                    explanation = i_result.get("explanation", "No explanation provided")
                                    st.write(explanation)
                                    
                                    # External signals
                                    if "external_signals" in i_result:
                                        st.markdown("**External Signals:**")
                                        st.write(i_result["external_signals"])
                                    
                                    # Risk factors found
                                    if "risk_factors_found" in i_result:
                                        st.markdown("**Risk Factors Identified:**")
                                        st.write(i_result["risk_factors_found"])
                                    st.divider()
                                
                                # Summary
                                st.markdown("### Summary")
                                all_recommendations = []
                                if "questionnaire" in assessments:
                                    all_recommendations.append(f"Questionnaire: {assessments['questionnaire'].get('recommended_rating', 'N/A')}")
                                if "comments" in assessments:
                                    all_recommendations.append(f"Comments: {assessments['comments'].get('recommended_rating', 'N/A')}")
                                if "internet" in assessments:
                                    all_recommendations.append(f"Internet: {assessments['internet'].get('recommended_rating', 'N/A')}")
                                
                                if all_recommendations:
                                    st.write("\n".join(all_recommendations))

