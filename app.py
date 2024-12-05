import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from datetime import datetime
import re
from collections import Counter
from plotly.subplots import make_subplots
from plotly.graph_objs import Scatter
from streamlit_plotly_events import plotly_events

# Configure Streamlit page for RTL support
st.set_page_config(
    page_title="ניתוח אירועי 7 באוקטובר - ynet",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Add custom CSS for RTL support
st.markdown("""
    <style>
        .stApp {
            direction: rtl;
            text-align: right;
        }
        .css-1d391kg {
            direction: rtl;
        }
        .stMarkdown {
            text-align: right;
        }
        div[data-testid="stMetricValue"] {
            direction: rtl;
        }
        .plot-container {
            direction: rtl;
        }
    </style>
""", unsafe_allow_html=True)

def classify_message_type(message, description):
    """Classify message type based on content analysis"""
    message = str(message).lower()
    description = str(description).lower() if description else ""
    
    keywords = {
        'אזעקה': ['אזעקה', 'צבע אדום', 'אזעקות'],
        'צבאי': ['צה"ל', 'חיילים', 'כוחות', 'צבא'],
        'פיגוע': ['מחבלים', 'פיגוע', 'חדירה', 'טרור'],
        'נפגעים': ['נפגעים', 'פצועים', 'הרוגים', 'נרצחו'],
        'חטופים': ['חטופים', 'חטיפה', 'בני ערובה'],
        'התרעה': ['התרעה', 'דיווח', 'עדכון']
    }
    
    message_types = []
    content = f"{message} {description}"
    
    for msg_type, terms in keywords.items():
        if any(term in content for term in terms):
            message_types.append(msg_type)
    
    return message_types if message_types else ['אחר']

def load_and_merge_data():
    """Load and merge data from multiple JSON sources"""
    try:
        # Load cleansed data
        cleansed_messages = []
        data_files = {
            'data/cleansed_data.json': 'cleansed',
            'final_cleaned_data.json': 'final',
            'cleaned_data_without_null_timestamps.json': 'cleaned'
        }
        
        dfs = []
        
        for file_path, source_name in data_files.items():
            try:
                if file_path.endswith('.jsonl') or file_path == 'data/cleansed_data.json':
                    # Handle line-by-line JSON files
                    messages = []
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            messages.append(json.loads(line))
                else:
                    # Handle regular JSON files
                    with open(file_path, 'r', encoding='utf-8') as f:
                        messages = json.load(f)
                
                if messages:
                    df = pd.DataFrame(messages)
                    df['source'] = source_name
                    dfs.append(df)
                    
            except FileNotFoundError:
                continue  # Skip if file doesn't exist
            except Exception as e:
                st.error(f"שגיאה בטעינת הקובץ {file_path}: {str(e)}")
                continue

        if not dfs:
            st.error('לא נמצאו קבצי נתונים')
            return pd.DataFrame()

        # Merge all DataFrames
        df = pd.concat(dfs, ignore_index=True)

        # Standardize column names
        column_mapping = {
            'Time': 'timestamp',
            'Timestamp': 'timestamp',
            'Author_Name': 'author',
            'sender': 'author',
            'Message': 'message',
            'content': 'message',
            'Description': 'description'
        }
        df = df.rename(columns=column_mapping)

        # Handle timestamps
        df['timestamp'] = df['timestamp'].replace('כעת', None)
        df['time'] = pd.to_datetime(df['timestamp'], format='%H:%M', errors='coerce').dt.time
        
        # Add message classification
        df['message_types'] = df.apply(
            lambda x: classify_message_type(
                x.get('message', ''), 
                x.get('description', '')
            ), 
            axis=1
        )
        
        # Add hour for analysis
        df['hour'] = pd.to_datetime(df['timestamp'], format='%H:%M', errors='coerce').dt.hour
        
        # Remove duplicates based on timestamp and message content
        df = df.drop_duplicates(subset=['timestamp', 'message'])
        
        # Sort by timestamp
        df = df.sort_values('timestamp')
        
        return df

    except Exception as e:
        st.error(f"שגיאה בטעינת הנתונים: {str(e)}")
        return pd.DataFrame()

def main():
    # Title with link to source
    st.title('ניתוח דיווחי ynet - 7 באוקטובר 2023')
    st.markdown("""
        <div style="direction: rtl; text-align: right;">
            <a href="https://www.ynet.co.il/news/100days" target="_blank">
                לצפייה במקור: ynet - 100 ימים למלחמה
            </a>
        </div>
        <br>
    """, unsafe_allow_html=True)

    df = load_and_merge_data()
    
    if df.empty:
        st.error('לא נמצאו נתונים לניתוח')
        return

    # Create three columns for filters
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    
    with filter_col1:
        # Time range filter
        hours = st.select_slider(
            'טווח שעות',
            options=list(range(24)),
            value=(6, 23)
        )
        st.write(f'מציג נתונים בין השעות {hours[0]}:00 - {hours[1]}:00')
    
    with filter_col2:
        # Author filter
        authors = ['הכל'] + sorted(df['author'].dropna().unique().tolist())
        selected_author = st.selectbox('סינון לפי כותב', authors)

    # Apply filters
    mask = (df['hour'] >= hours[0]) & (df['hour'] <= hours[1])
    if selected_author != 'הכל':
        mask &= (df['author'] == selected_author)
    
    filtered_df = df.loc[mask]

    # Add some spacing
    st.markdown("<br>", unsafe_allow_html=True)

    # Display metrics
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    with metric_col1:
        st.metric("סה\"כ הודעות", len(filtered_df))
    with metric_col2:
        st.metric("מספר כותבים", filtered_df['author'].nunique())
    with metric_col3:
        st.metric("ממוצע הודעות לשעה", f"{len(filtered_df)/(hours[1]-hours[0]+1):.1f}")

    # Message types analysis with interactive filtering
    st.subheader('ניתוח סוגי ההודעות')
    
    # Create two columns for chart and filtered messages with messages on the left
    messages_col, chart_col = st.columns([1, 1])  # Reversed order
    
    with chart_col:
        all_types = [t for types in filtered_df['message_types'] for t in types]
        type_counts = Counter(all_types)
        
        # Create pie chart with custom colors
        colors = {
            'אזעקה': '#FF4B4B',  # Red
            'צבאי': '#466964',   # Military green
            'פיגוע': '#FF8C00',  # Dark orange
            'נפגעים': '#800000', # Maroon
            'חטופים': '#4B0082', # Indigo
            'התרעה': '#1E90FF', # Dodger blue
            'אחר': '#808080'     # Gray
        }
        
        fig1 = px.pie(
            values=list(type_counts.values()),
            names=list(type_counts.keys()),
            title='התפלגות סוגי ההודעות',
            color=list(type_counts.keys()),
            color_discrete_map=colors
        )
        fig1.update_layout(
            title_x=0.5,
            font_family="Arial",
            title_font_family="Arial",
            showlegend=True
        )
        
        # Display the chart and get the clicked data
        selected_type = plotly_events(fig1, click_event=True)
    
    with messages_col:  # Now on the left
        # Initialize with default type
        current_type = 'אחר'
        
        # Update if a type is selected
        if selected_type and len(selected_type) > 0:
            current_type = selected_type[0].get('label', 'אחר')
        
        st.subheader(f'הודעות מסוג: {current_type}')
        # Filter messages by selected type
        type_messages = filtered_df[filtered_df['message_types'].apply(lambda x: current_type in x)]
        
        if len(type_messages) > 0:
            st.dataframe(
                type_messages[['timestamp', 'author', 'message', 'description']]
                .sort_values('timestamp'),
                height=400
            )
        else:
            st.write("לא נמצאו הודעות מסוג זה בטווח הזמן הנבחר")

    # Timeline analysis with source breakdown
    st.subheader('ניתוח זמנים')
    hourly_source_counts = filtered_df.groupby(['hour', 'source']).size().reset_index(name='count')
    fig2 = px.line(
        hourly_source_counts,
        x='hour',
        y='count',
        color='source',
        title='מספר הודעות לפי שעה ומקור'
    )
    fig2.update_layout(
        title_x=0.5,
        font_family="Arial",
        title_font_family="Arial",
        xaxis_title="שעה",
        yaxis_title="מספר הודעות"
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Author analysis
    if len(filtered_df['author'].dropna()) > 0:
        st.subheader('ניתוח לפי כותבים')
        author_counts = filtered_df['author'].value_counts().head(10)
        fig3 = px.bar(
            x=author_counts.index,
            y=author_counts.values,
            title='כותבים מובילים'
        )
        fig3.update_layout(
            title_x=0.5,
            font_family="Arial",
            title_font_family="Arial",
            xaxis_title="כותב",
            yaxis_title="מספר הודעות",
            bargap=0.2
        )
        st.plotly_chart(fig3, use_container_width=True)

    # Message content analysis
    st.subheader('תוכן ההודעות')
    search_term = st.text_input('חיפוש בהודעות')
    if search_term:
        mask = filtered_df['message'].str.contains(search_term, case=False, na=False)
        search_results = filtered_df[mask]
        st.write(f"נמצאו {len(search_results)} תוצאות:")
        st.dataframe(search_results[['timestamp', 'author', 'message', 'description', 'source']])
    
    # Always show all data at the bottom
    st.markdown("""---""")  # Add separator
    st.subheader('כל ההודעות')
    st.dataframe(
        filtered_df[['timestamp', 'author', 'message', 'description']]
        .sort_values('timestamp'),
        height=400  # Fixed height for better layout
    )

if __name__ == '__main__':
    main()