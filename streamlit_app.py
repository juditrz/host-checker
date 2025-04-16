import streamlit as st
import pandas as pd
from io import StringIO
from hosting_checker import check_hosting, extract_links_with_context, normalize_url, save_to_excel
import tempfile
import os

st.set_page_config(page_title="Website Hosting Checker", layout="centered")
st.title("🌐 Website Hosting & NS Checker")

# --- Input selection ---
input_type = st.radio("Select input method:", ["Upload .md file", "Upload .csv file", "Paste URLs manually"])

links_with_context = []
raw_urls = []
input_mode = None

# --- Option 1: Markdown Upload ---
if input_type == "Upload .md file":
    uploaded_md = st.file_uploader("Upload a Markdown (.md) file", type=["md"])
    if uploaded_md:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".md") as tmp:
            tmp.write(uploaded_md.read())
            tmp_path = tmp.name
        links_with_context = extract_links_with_context(tmp_path)
        input_mode = "md"

# --- Option 2: CSV Upload ---
elif input_type == "Upload .csv file":
    uploaded_csv = st.file_uploader("Upload a CSV file", type=["csv"])
    if uploaded_csv:
        df = pd.read_csv(uploaded_csv)
        url_column = st.selectbox("Select the column containing URLs:", df.columns)
        raw_urls = df[url_column].dropna().astype(str).tolist()
        links_with_context = [("CSV Entry", "N/A", normalize_url(url)) for url in raw_urls]
        input_mode = "csv"

# --- Option 3: Manual Input ---
elif input_type == "Paste URLs manually":
    textarea = st.text_area("Paste one URL per line:")
    if textarea:
        raw_urls = [normalize_url(url.strip()) for url in textarea.splitlines() if url.strip()]
        links_with_context = [("Manual Entry", "N/A", url) for url in raw_urls]
        input_mode = "manual"

# --- Run Analysis ---
if links_with_context:
    if st.button("Run Hosting Check"):
        with st.spinner("Checking websites... This may take a minute..."):
            results = check_hosting(links_with_context)
            if input_mode == "md":
                df_results = pd.DataFrame(results, columns=["Name", "Profile", "URL", "Host", "NS Provider"])
            else:
                df_results = pd.DataFrame([(url, host, ns) for _, _, url, host, ns in results],
                                          columns=["URL", "Host", "NS Provider"])
            st.success("✅ Done!")
            st.dataframe(df_results)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_excel:
                save_to_excel(results, input_mode, tmp_excel.name)
                tmp_excel.seek(0)
                st.download_button(
                    label="📥 Download Excel Report",
                    data=tmp_excel.read(),
                    file_name="hosting_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
