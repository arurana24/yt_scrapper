import os
import re
import time
import isodate
import pandas as pd
import streamlit as st
from googleapiclient.discovery import build

# ==========================================
# CUSTOM THEME & DESIGN CONFIGURATION
# ==========================================
st.set_page_config(page_title="Video Metrics Auditor", layout="centered")

# CSS Injection for #81d8d0 App Background and #008080 (Dark Turquoise) UI Controls
st.markdown(
    """
    <style>
    .stApp {
        background-color: #81d8d0;
    }
    h1, h2, h3, p, label, .stMarkdown {
        color: #1e293b !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    /* Action Buttons Styles Override */
    div.stButton > button, div.stDownloadButton > button {
        background-color: #008080 !important;
        color: #ffffff !important;
        border-radius: 6px;
        border: 1px solid #005a5a;
        padding: 0.6rem 2.5rem;
        font-weight: bold;
        font-size: 16px;
        transition: background-color 0.3s ease;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        background-color: #005a5a !important;
        color: #ffffff !important;
        border-color: #004040;
    }
    .stFileUploader section {
        background-color: rgba(255, 255, 255, 0.5) !important;
        border: 2px dashed #008080 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ==========================================
# BRANDING LOGO COMPONENT LAYOUT
# ==========================================
if os.path.exists("logo.jpeg"):
    st.image("logo.jpeg", width=140)
else:
    st.markdown("### 📊 Platform Metrics Tracker")

# Hardcoded Secure API access token definition
API_KEY = "AIzaSyCRyoLF6fe9jZ5ozZWRNar-E6YmPw6JBZI"
youtube = build("youtube", "v3", developerKey=API_KEY)

# ==========================================
# UTILITY HELPER RUNTIME FUNCTIONS
# ==========================================
def extract_handle_from_url(url):
    if pd.isna(url) or not isinstance(url, str): 
        return None
    url_clean = url.strip().rstrip('/')
    match = re.search(r'(?:youtube\.com/)(@[^/?#&]+)', url_clean)
    if match:
        return match.group(1)
    if url_clean.startswith('@'):
        return url_clean
    return None

def format_iso_duration(duration_iso):
    """Translates YouTube's complex ISO strings into highly readable clean text formats"""
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
# INTERFACE FRONT-END LAYOUT
# ==========================================
st.title("YouTube Performance Metrics Auditor")
st.write("Upload your spreadsheet tracking matrix to analyze organic content tier metrics directly from the API.")

uploaded_file = st.file_uploader("Select Ingestion Spreadsheet Tracker (.xlsx)", type=["xlsx"])

if uploaded_file:
    df_inputs = pd.read_excel(uploaded_file)
    URL_COLUMN_NAME = "Channel Link" if "Channel Link" in df_inputs.columns else df_inputs.columns[0]
    
    st.write(f"Detected file containing {len(df_inputs)} rows. Column layout target maps to: `{URL_COLUMN_NAME}`")
    
    st.write("### 1. Select Content Tiers to Analyze")
    col1, col2 = st.columns(2)
    with col1:
        want_shorts = st.checkbox("Shorts Form Content (<= 60s)", value=True)
    with col2:
        want_longform = st.checkbox("Long-form Videos (> 60s)", value=False)
        
    st.write("### 2. Select Summary Performance Filters")
    m_views = st.checkbox("Average Views", value=True)
    m_likes = st.checkbox("Average Likes", value=True)
    m_comments = st.checkbox("Average Comments", value=True)
    m_er = st.checkbox("Engagement Rate (ER) %", value=True, help="Calculated as ((Likes + Comments) / Subscribers) * 100")
    
    st.info("Note: Average watch time and traffic conversion values require private owner OAuth2 credentials.")

    if st.button("Run Audit Pipeline"):
        if not want_shorts and not want_longform:
            st.error("Please select at least one content tier checkbox (Shorts or Long-form) to proceed.")
        else:
            status_box = st.empty()
            status_box.info("Initializing connection to Google Cloud API layer...")
            
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
                    status_box.warning(f"Row {idx + 1}: Skipping invalid channel handle profile link layout.")
                    continue
                    
                status_box.info(f"Processing Handle: {handle} [{idx + 1}/{total_creators}]")
                
                try:
                    # API Query 1: Extract basic stats + New deep channel-level dimensions
                    channel_response = youtube.channels().list(
                        part="id,statistics,contentDetails,snippet", 
                        forHandle=handle
                    ).execute()
                    
                    if not channel_response.get("items"):
                        continue
                        
                    channel_data = channel_response["items"][0]
                    channel_id = channel_data["id"]
                    
                    # Core Channel Dimensions Harvest
                    sub_count = int(channel_data["statistics"].get("subscriberCount", 0))
                    total_lifetime_views = int(channel_data["statistics"].get("viewCount", 0))
                    total_videos_uploaded = int(channel_data["statistics"].get("videoCount", 0))
                    
                    # Isolate clean date from raw datetime string layout
                    raw_create_time = channel_data["snippet"].get("publishedAt", "")
                    channel_creation_date = raw_create_time.split("T")[0] if "T" in raw_create_time else "Unknown"
                    
                    uploads_playlist_id = channel_data["contentDetails"]["relatedPlaylists"]["uploads"]
                    
                    # API Query 2: Collect recent items sequentially (bypassing channel pinned items)
                    playlist_response = youtube.playlistItems().list(
                        part="contentDetails",
                        playlistId=uploads_playlist_id,
                        maxResults=30
                    ).execute()
                    
                    video_ids = [item["contentDetails"]["videoId"] for item in playlist_response.get("items", [])]
                    
                    if not video_ids:
                        continue
                        
                    # API Query 3: Multi-video payload parameters download layer
                    video_response = youtube.videos().list(
                        part="statistics,snippet,contentDetails",
                        id=",".join(video_ids)
                    ).execute()
                    
                    temp_profile_metrics = []
                    
                    for video in video_response.get("items", []):
                        stats = video["statistics"]
                        title = video["snippet"]["title"]
                        v_id = video["id"]
                        
                        # Fetch video runtime configurations
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
                            
                        if len(temp_profile_metrics) >= 10:
                            continue
                            
                        temp_profile_metrics.append({
                            "Channel Link": profile_url, "Handle": handle, "Video URL": video_url,
                            "Title": title, "Views": v_views, "Likes": v_likes, "Comments": v_comments,
                            "Duration": duration_text, "Publish Date": video_publish_date
                        })

                    # Perform Anomaly Mitigation Filters (IQR)
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
                            "Channel Link": profile_url, 
                            "Handle": handle, 
                            "Subscribers": sub_count, 
                            "Channel Creation Date": channel_creation_date,
                            "Total Videos Uploaded": total_videos_uploaded,
                            "Total Lifetime Views": total_lifetime_views,
                            "Recent Videos Processed": len(df_organic)
                        }
                        
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
            st.success("Campaign data parsing complete! Your multi-sheet file ready for export.")
            
            with open(output_file_path, "rb") as file_bytes:
                st.download_button(
                    label="📥 Download Performance Report",
                    data=file_bytes,
                    file_name="youtube_metrics_audit_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
