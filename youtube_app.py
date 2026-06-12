import os
import re
import time
import base64
import isodate
import pandas as pd
import streamlit as st
from googleapiclient.discovery import build

# ==========================================
# CUSTOM THEME & DESIGN CONFIGURATION
# ==========================================
st.set_page_config(page_title="Video Metrics Auditor", layout="centered")

# Helper function to convert local image to secure Base64 for HTML injection
def get_base64_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return None

# Check for both jpeg and jpg variations safely
logo_base64 = get_base64_image("logo.jpeg") or get_base64_image("logo.jpg")

# Advanced CSS Injection for Background, Solid Black Lines, and Dark Turquoise (#008080) Overrides
st.markdown(
    """
    <style>
    .stApp {
        background-color: #81d8d0;
    }
    h1, h2, h3, p, label, .stMarkdown, .stText {
        color: #1e293b !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* 🛠️ ACTION BUTTONS STYLES (RUN AUDIT & DOWNLOAD) */
    div.stButton > button, div.stDownloadButton > button {
        background-color: #008080 !important;
        color: #ffffff !important;
        border-radius: 6px;
        border: 1px solid #005a5a !important;
        padding: 0.6rem 2.5rem;
        font-weight: bold;
        font-size: 16px;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        background-color: #005a5a !important;
        color: #ffffff !important;
    }
    .stCheckbox label p, .stRadio label p {
        color: #1e293b !important;
    }
    
    /* 🛠️ BULLETPROOF FILE UPLOADER STYLE OVERRIDES */
    .stFileUploader section {
        background-color: rgba(255, 255, 255, 0.5) !important;
        border: 2px dashed #008080 !important;
    }
    /* Forces the inner black browse button to turn Dark Turquoise */
    .stFileUploader data-testid="stFileUploaderButton" button,
    .stFileUploader button,
    .stFileUploader [data-testid="baseButton-secondary"] {
        background-color: #008080 !important;
        color: #ffffff !important;
        border: 1px solid #005a5a !important;
    }
    /* Forces the '200MB per file • XLSX' guidelines lines to be solid black */
    .stFileUploader [data-testid="stFileUploadDropzoneInstructions"] div, 
    .stFileUploader [data-testid="stWidgetLabel"] p,
    .stFileUploader span,
    .stFileUploader small,
    .stFileUploader div {
        color: #000000 !important;
    }
    
    /* 🛠️ CENTERED BOTTOM LOGO CONTAINER STYLE */
    .bottom-logo-container {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        margin-top: 50px;
        padding-top: 20px;
        margin-bottom: 20px;
    }
    .bottom-logo-container img {
        width: 140px;
        border-radius: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Hardcoded Secure API access token definition
API_KEY = "AIzaSyCRyoLF6fe9jZ5ozZWRNar-E6YmPw6JBZI"
youtube = build("youtube", "v3", developerKey=API_KEY)

# ==========================================
# UTILITY HELPER RUNTIME FUNCTIONS
# ==========================================
def extract_handle_from_url(url):
    if pd.isna(url) or not isinstance(url, str): 
        return None
    
    # Clean up whitespace and any trailing forward slashes
    url_clean = url.strip().rstrip('/')
    
    # Match the '@' handle and capture everything up until the next slash, question mark, or hash
    match = re.search(r'(?:youtube\.com/|si=)(@[a-zA-Z0-9_\-\.]+)', url_clean)
    if match:
        return match.group(1)
        
    # If the user just typed raw '@handle' without the domain prefix, check and clean it
    if url_clean.startswith('@'):
        return url_clean.split('/')[0].split('?')[0]
        
    return None

def extract_video_id_from_url(url):
    if pd.isna(url):
        return None
    url_str = str(url).strip()
    
    if "v=" in url_str:
        match = re.search(r'v=([a-zA-Z0-9_-]{11})', url_str)
        if match: return match.group(1)
        
    if "shorts/" in url_str:
        match = re.search(r'shorts/([a-zA-Z0-9_-]{11})', url_str)
        if match: return match.group(1)
        
    if "youtu.be/" in url_str:
        match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url_str)
        if match: return match.group(1)
        
    if "embed/" in url_str:
        match = re.search(r'embed/([a-zA-Z0-9_-]{11})', url_str)
        if match: return match.group(1)
        
    match = re.search(r'^([a-zA-Z0-9_-]{11})$', url_str)
    if match: 
        return match.group(1)
        
    return None

def format_iso_duration(duration_iso):
    try:
        duration = isodate.parse_duration(duration_iso)
        total_seconds = int(duration.total_seconds())
        is_short = total_seconds <= 60
        
        if total_seconds < 60:
            return f"{total_seconds}s", is_short
        
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds}s", is_short
    except Exception:
        return "Unknown", False

# ==========================================
# INTERFACE MASTER ROUTER LAYOUT
# ==========================================
st.title("YouTube Performance Metrics Auditor")

# Master operational mode switch selector
audit_mode = st.radio(
    "What mode would you like to run today?",
    options=["Track Specific Campaign Video Links", "Get Average Channel Metrics of YouTubers"],
    index=0
)

st.write("---")
st.write("### Configure Column Targets")

# Dynamic Column Name Mapping Input Box
if audit_mode == "Track Specific Campaign Video Links":
    target_column_input = st.text_input(
        "Enter the exact column name containing your Video Links:", 
        value="Video Link",
        help="Type the exact header case-sensitive text string from your Excel file (e.g., 'URL', 'Video Link', 'Shorts URL')."
    )
else:
    target_column_input = st.text_input(
        "Enter the exact column name containing your Channel Links:", 
        value="Channel Link",
        help="Type the exact header case-sensitive text string from your Excel file (e.g., 'Channel Link', 'Youtubers')."
    )

if audit_mode == "Get Average Channel Metrics of YouTubers":
    st.write("### 1. Select Content Tiers to Analyze")
    col1, col2 = st.columns(2)
    with col1:
        want_shorts = st.checkbox("Shorts Form Content (<= 60s)", value=True)
    with col2:
        want_longform = st.checkbox("Long-form Videos (> 60s)", value=False)
        
    st.write("### 2. Configure Dynamic Analysis Thresholds")
    max_videos_to_scan = st.slider(
        "Maximum videos/shorts to analyze per profile:", 
        min_value=1, max_value=50, value=10, step=1
    )
        
    st.write("### 3. Select Summary Performance Filters")
    c_left, c_right = st.columns(2)
    with c_left:
        m_views = st.checkbox("Average Views", value=True)
        m_likes = st.checkbox("Average Likes", value=True)
        m_comments = st.checkbox("Average Comments", value=True)
        m_er = st.checkbox("Engagement Rate (ER) %", value=True)
    with c_right:
        m_creation = st.checkbox("Channel Creation Date", value=True)
        m_uploads = st.checkbox("Total Videos Uploaded", value=True)
        m_lifetime = st.checkbox("Total Channel Lifetime Views", value=True)

st.write("---")
st.write("### Upload Campaign Input Sheet")
uploaded_file = st.file_uploader("Select Ingestion Spreadsheet Tracker (.xlsx)", type=["xlsx"])

# Execution Pipeline Logic Flow Routing Engine
if uploaded_file:
    df_inputs = pd.read_excel(uploaded_file)
    
    # Validation step to ensure user's typed column name actually exists
    if target_column_input not in df_inputs.columns:
        st.error(f"The column '{target_column_input}' was not found in your uploaded file. Available columns are: {list(df_inputs.columns)}")
    else:
        URL_COLUMN_NAME = target_column_input
        st.write(f"📂 **Target Registered:** Successfully identified column `{URL_COLUMN_NAME}` with `{len(df_inputs)}` entries.")
        
        if st.button("Run Audit Pipeline"):
            status_box = st.empty()
            
            # ==============================================================================
            # RUNNING ROUTE A: TRACK DIRECT VIDEO LINKS
            # ==============================================================================
            if audit_mode == "Track Specific Campaign Video Links":
                status_box.info("Querying individual campaign video metrics layout...")
                granular_video_rows = []
                
                raw_urls = df_inputs[URL_COLUMN_NAME].dropna().tolist()
                url_map = {extract_video_id_from_url(url): url for url in raw_urls if extract_video_id_from_url(url)}
                video_ids = list(url_map.keys())
                
                if not video_ids:
                    st.error("Could not parse any valid 11-character YouTube video IDs from your specified column. Double check your data rows.")
                else:
                    for i in range(0, len(video_ids), 50):
                        batch_ids = video_ids[i:i+50]
                        status_box.info(f"Extracting video statistics batch [{min(i+50, len(video_ids))}/{len(video_ids)}]...")
                        
                        try:
                            video_response = youtube.videos().list(
                                part="statistics,snippet,contentDetails", id=",".join(batch_ids)
                            ).execute()
                            
                            for video in video_response.get("items", []):
                                v_id = video["id"]
                                stats = video["statistics"]
                                snippet = video["snippet"]
                                
                                duration_iso = video["contentDetails"]["duration"]
                                raw_pub_time = snippet.get("publishedAt", "")
                                video_publish_date = raw_pub_time.split("T")[0] if "T" in raw_pub_time else "Unknown"
                                duration_text, _ = format_iso_duration(duration_iso)
                                
                                granular_video_rows.append({
                                    "Video Link": url_map[v_id],
                                    "Channel Title": snippet.get("channelTitle", "Unknown"),
                                    "Title": snippet.get("title", ""),
                                    "Views": int(stats.get("viewCount", 0)),
                                    "Likes": int(stats.get("likeCount", 0)),
                                    "Comments": int(stats.get("commentCount", 0)),
                                    "Duration": duration_text,
                                    "Publish Date": video_publish_date
                                })
                        except Exception as e:
                            st.error(f"Execution batch query aborted by server: {str(e)}")
                    
                    if granular_video_rows:
                        output_file_path = "audited_youtube_metrics.xlsx"
                        with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
                            pd.DataFrame(granular_video_rows).to_excel(writer, sheet_name="Shorts Campaign Metrics", index=False)
                        
                        status_box.empty()
                        st.success("Analysis complete! Export report sheet compiled below.")
                        
                        with open(output_file_path, "rb") as file_bytes:
                            st.download_button(
                                label="📥 Download Campaign Report", data=file_bytes,
                                file_name="youtube_campaign_shorts_report.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                    else:
                        st.error("No data recovered from the API queries.")

            # ==============================================================================
            # RUNNING ROUTE B: GET CHANNELS AVERAGES 
            # ==============================================================================
            else:
                if not want_shorts and not want_longform:
                    st.error("Please select at least one content configuration type checkbox to proceed.")
                else:
                    status_box.info("Connecting to Google API data endpoints...")
                    profile_summary_rows = []
                    granular_video_rows = []
                    skipped_video_rows = []
                    total_creators = len(df_inputs)
                    
                    for idx, row in df_inputs.iterrows():
                        profile_url = row[URL_COLUMN_NAME]
                        if pd.isna(profile_url): 
                            continue
                            
                        handle = extract_handle_from_url(profile_url)
                        if not handle: 
                            continue
                            
                        status_box.info(f"Processing Handle: {handle} [{idx + 1}/{total_creators}]")
                        
                        try:
                            channel_response = youtube.channels().list(
                                part="id,statistics,contentDetails,snippet", 
                                forHandle=handle
                            ).execute()
                            
                            if not channel_response.get("items"): 
                                continue
                                
                            channel_data = channel_response["items"][0]
                            channel_id = channel_data["id"]
                            
                            sub_count = int(channel_data["statistics"].get("subscriberCount", 0))
                            total_lifetime_views = int(channel_data["statistics"].get("viewCount", 0))
                            total_videos_uploaded = int(channel_data["statistics"].get("videoCount", 0))
                            
                            raw_create_time = channel_data["snippet"].get("publishedAt", "")
                            channel_creation_date = raw_create_time.split("T")[0] if "T" in raw_create_time else "Unknown"
                            
                            uploads_playlist_id = channel_data["contentDetails"]["relatedPlaylists"]["uploads"]
                            fetch_limit = min(50, max(30, max_videos_to_scan * 3))
                            
                            playlist_response = youtube.playlistItems().list(
                                part="contentDetails", playlistId=uploads_playlist_id, maxResults=fetch_limit
                            ).execute()
                            
                            video_ids = [item["contentDetails"]["videoId"] for item in playlist_response.get("items", [])]
                            if not video_ids: 
                                continue
                                
                            video_response = youtube.videos().list(
                                part="statistics,snippet,contentDetails", id=",".join(video_ids)
                            ).execute()
                            
                            temp_profile_metrics = []
                            
                            for video in video_response.get("items", []):
                                stats = video["statistics"]
                                title = video["snippet"]["title"]
                                v_id = video["id"]
                                
                                duration_iso = video["contentDetails"]["duration"]
                                raw_pub_time = video["snippet"].get("publishedAt", "")
                                video_publish_date = raw_pub_time.split("T")[0] if "T" in raw_pub_time else "Unknown"
                                
                                duration_text, is_short = format_iso_duration(duration_iso)
                                video_url = f"https://www.youtube.com/shorts/{v_id}" if is_short else f"https://www.youtube.com/watch?v={v_id}"
                                
                                v_views = int(stats.get("viewCount", 0))
                                v_likes = int(stats.get("likeCount", 0))
                                v_comments = int(stats.get("commentCount", 0))
                                
                                if is_short and not want_shorts: 
                                    continue
                                if not is_short and not want_longform:
                                    skipped_video_rows.append({
                                        "Channel Link": profile_url, "Handle": handle, "Video URL": video_url,
                                        "Title": title, "Views": v_views, "Likes": v_likes, "Comments": v_comments,
                                        "Duration": duration_text, "Publish Date": video_publish_date,
                                        "Skip Reason": "Filtered Out: Content Type is Long-form"
                                    })
                                    continue
                                    
                                if len(temp_profile_metrics) >= max_videos_to_scan: 
                                    continue
                                    
                                temp_profile_metrics.append({
                                    "Channel Link": profile_url, "Handle": handle, "Video URL": video_url,
                                    "Title": title, "Views": v_views, "Likes": v_likes, "Comments": v_comments,
                                    "Duration": duration_text, "Publish Date": video_publish_date
                                })

                            if temp_profile_metrics:
                                df_temp = pd.DataFrame(temp_profile_metrics)
                                
                                if len(df_temp) >= 4:
                                    q1 = df_temp["Views"].quantile(0.25)
                                    q3 = df_temp["Views"].quantile(0.75)
                                    iqr = q3 - q1
                                    upper_bound = q3 + (1.5 * iqr)
                                    
                                    df_organic = df_temp[df_temp["Views"] <= upper_bound]
                                    df_boosted = df_temp[df_temp["Views"] > upper_bound]
                                    
                                    for _, b_row in df_boosted.iterrows():
                                        skipped_video_rows.append({
                                            "Channel Link": b_row["Channel Link"], "Handle": b_row["Handle"], "Video URL": b_row["Video URL"],
                                            "Title": b_row["Title"], "Views": b_row["Views"], "Likes": b_row["Likes"], "Comments": b_row["Comments"],
                                            "Duration": b_row["Duration"], "Publish Date": b_row["Publish Date"],
                                            "Skip Reason": "Boosted Ad Outlier (IQR Filter)"
                                        })
                                else:
                                    df_organic = df_temp
                                    
                                for _, o_row in df_organic.iterrows():
                                    granular_video_rows.append(dict(o_row))
                                    
                                raw_avg_v = df_organic["Views"].mean() if not df_organic.empty else 0
                                raw_avg_l = df_organic["Likes"].mean() if not df_organic.empty else 0
                                raw_avg_c = df_organic["Comments"].mean() if not df_organic.empty else 0
                                
                                summary_card = {
                                    "Channel Link": profile_url, "Handle": handle, "Subscribers": sub_count, "Recent Videos Processed": len(df_organic)
                                }
                                
                                if m_creation: summary_card["Channel Creation Date"] = channel_creation_date
                                if m_uploads: summary_card["Total Videos Uploaded"] = total_videos_uploaded
                                if m_lifetime: summary_card["Total Lifetime Views"] = total_lifetime_views
                                if m_views: summary_card["Avg Views"] = round(raw_avg_v, 2)
                                if m_likes: summary_card["Avg Likes"] = round(raw_avg_l, 2)
                                if m_comments: summary_card["Avg Comments"] = round(raw_avg_c, 2)
                                if m_er:
                                    calculated_er = ((raw_avg_l + raw_avg_c) / sub_count * 100) if sub_count > 0 else 0.0
                                    summary_card["Avg Engagement Rate (%)"] = round(calculated_er, 2)
                                
                                summary_card["Status"] = "Success"
                                profile_summary_rows.append(summary_card)
                            else:
                                profile_summary_rows.append({
                                    "Channel Link": profile_url, "Handle": handle, "Subscribers": sub_count, "Recent Videos Processed": 0, "Status": "No Content Found"
                                })
                            time.sleep(0.1)
                        except Exception as e:
                            status_box.warning(f"Error handling channel {handle}: {str(e)}")

                df_skipped_sheet = pd.DataFrame(skipped_video_rows)
                if df_skipped_sheet.empty:
                    df_skipped_sheet = pd.DataFrame(columns=["Channel Link", "Handle", "Video URL", "Title", "Views", "Likes", "Comments", "Duration", "Publish Date", "Skip Reason"])

                output_file_path = "audited_youtube_metrics.xlsx"
                with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
                    pd.DataFrame(profile_summary_rows).to_excel(writer, sheet_name="Channel Summary", index=False)
                    pd.DataFrame(granular_video_rows).to_excel(writer, sheet_name="Video Metrics", index=False)
                    df_skipped_sheet.to_excel(writer, sheet_name="Skipped Content", index=False)

                status_box.empty()
                st.success("Campaign data parsing complete! Report compiled successfully.")
                
                with open(output_file_path, "rb") as file_bytes:
                    st.download_button(
                        label="📥 Download Performance Report", data=file_bytes,
                        file_name="youtube_metrics_audit_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

# ==========================================
# BRANDING LOGO COMPONENT (BOTTOM MIDDLE)
# ==========================================
if logo_base64:
    st.markdown(f'<div class="bottom-logo-container"><img src="data:image/jpeg;base64,{logo_base64}"></div>', unsafe_allow_html=True)
