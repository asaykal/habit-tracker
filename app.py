import streamlit as st
import pandas as pd
import altair as alt
import datetime, os, gspread
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe

st.set_page_config(
    page_title="Habit Tracker",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.title("Habit Tracker")

safety_settings = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
}

FILE_PATH = "journal.csv"
JSON_PATH = "journal.json"

scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scopes
)
client = gspread.authorize(creds)

api_key = st.secrets.default.gemini_api_key
genai.configure(api_key=api_key)


def llm_analysis(data):
    model = genai.GenerativeModel("gemini-pro", safety_settings=safety_settings)

    prompt = f"""
        Analyze the data and generate insights on the user's habit. This is for educational and health purposes only.
        Data Fields are: Date, Time, Emotion Before, Situation, Urge Intensity, Mood Rating, Coping Mechanism, Emotion After, Behavioural Thoughts, Coping Mechanism Score

        Data:
               {data}

        Output:
    """

    response = model.generate_content(prompt)
    return response.text


def connect_google_sheet():
    try:
        spreadsheet_url = st.secrets["default"]["spreadsheet_url"]
        sheet_name = "Journal"
        sh = client.open_by_url(spreadsheet_url).worksheet(sheet_name)
        sh.clear()
        df = pd.read_csv(FILE_PATH)
        existing = pd.DataFrame(sh.get_all_records())
        updated = pd.concat([existing, df], ignore_index=True)
        set_with_dataframe(sh, updated)
        st.success("Data uploaded to Google Sheets successfully")
    except Exception as e:
        st.error(f"An error occurred: {e}")


with st.sidebar:
    st.title("Settings")
    with st.expander("Emotion Tags (Optional)"):
        emotion_tags = []
        with open("emotions.md", "r") as f:
            emotions = f.readlines()
            for tag in emotions:
                tag = tag.strip()
                tag = tag[1:-2]
                if st.checkbox(tag, key=f"emotion_{tag}"):
                    emotion_tags.append(tag)

    with st.expander("Coping Mechanism Tags (Optional)"):
        coping_tags = []
        with open("cope.md", "r") as f:
            mechanisms = f.readlines()
            for tag in mechanisms:
                tag = tag.strip()
                tag = tag[1:-2]
                if st.checkbox(tag, key=f"coping_{tag}"):
                    coping_tags.append(tag)

    with st.expander("Emotion After Tags (Optional)"):
        emotion_after_tags = []
        with open("after_emotions.md", "r") as f:
            emotions = f.readlines()
            for tag in emotions:
                tag = tag.strip()
                tag = tag[1:-2]
                if st.checkbox(tag, key=f"emotion_after_{tag}"):
                    emotion_after_tags.append(tag)

    if "show_df" not in st.session_state:
        st.session_state["show_df"] = False

    if st.button("Edit Dataframe", key="dataframe"):
        st.session_state["show_df"] = not st.session_state["show_df"]

    if st.session_state["show_df"]:
        try:
            df = pd.read_csv(FILE_PATH)
            edited_df = st.data_editor(data=df)
            edited_rows = edited_df.to_dict("records")
            new_df = pd.DataFrame(edited_rows)
            new_df.to_csv(FILE_PATH, index=False)
        except FileNotFoundError:
            st.write("No data available")

    if "llm_analysis" not in st.session_state:
        st.session_state.llm_analysis = ""

    if st.button("Gemini Analysis"):
        try:
            df = pd.read_csv(FILE_PATH)
            st.session_state.llm_analysis = llm_analysis(df.to_dict("records"))
        except FileNotFoundError:
            st.write("No data available")

    if st.button("Clear Data"):
        try:
            os.remove(FILE_PATH)
            st.success("Data cleared successfully")
        except FileNotFoundError:
            st.warning("No data to clear")

st.header("Add Journal Entry")

today = datetime.date.today()
time_now = datetime.datetime.now().time()

with st.form("journal_entry"):
    date = st.date_input(
        "Date",
        value=today,
        max_value=today,
        min_value=today - datetime.timedelta(days=6),
    )
    time = st.time_input("Time", value=time_now)
    emotion_before = st.text_input("Emotion before", value=", ".join(emotion_tags))
    situation = st.text_input("Situation")
    urge_intensity = st.slider("Urge Intensity (1-10)", 1, 10, 5)
    mood_rating = st.slider("Mood Rating (1-10)", 1, 10, 5)
    coping_mechanism = st.text_input("Coping Mechanism", value=", ".join(coping_tags))
    emotion_after = st.text_input("Emotion after", value=", ".join(emotion_after_tags))
    behavioural_thoughts = st.text_area("Behavioural Thoughts")
    coping_mechanism_score = st.slider("Coping Mechanism Score (1-10)", 1, 10, 5)
    submitted = st.form_submit_button("Submit Entry")

    if submitted:
        with st.spinner("Submitting entry..."):
            new_entry = {
                "Date": date,
                "Time": time,
                "Emotion Before": emotion_before,
                "Situation": situation,
                "Urge Intensity": urge_intensity,
                "Mood Rating": mood_rating,
                "Coping Mechanism": coping_mechanism,
                "Emotion After": emotion_after,
                "Behavioural Thoughts": behavioural_thoughts,
                "Coping Mechanism Score": coping_mechanism_score,
            }

            try:
                df = pd.read_csv(FILE_PATH)
            except FileNotFoundError:
                df = pd.DataFrame(columns=new_entry.keys())

            df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
            df.to_csv(FILE_PATH, index=False)
            df.to_json(JSON_PATH, orient="records")
            st.success("Entry submitted successfully")

            connect_google_sheet()

st.header("Data Analysis")

if "loaded_data" not in st.session_state:
    st.session_state.loaded_data = None

load_data = st.button("Load & Analyze Data")
try:
    if load_data or st.session_state.loaded_data is not None:
        if load_data:
            st.session_state.loaded_data = pd.read_csv(FILE_PATH)

        df = st.session_state.loaded_data
        df.fillna("", inplace=True)

        st.subheader("Filter by Emotion Before")
        st.write("Select an emotion to filter:")
        if "emotion_filter" not in st.session_state:
            st.session_state.emotion_filter = df["Emotion Before"].unique()[0]
        selected_emotion = st.selectbox(
            "Emotion Filter",
            df["Emotion Before"].unique(),
            index=list(df["Emotion Before"].unique()).index(
                st.session_state.emotion_filter
            ),
        )
        st.session_state.emotion_filter = selected_emotion
        filtered_df = df[df["Emotion Before"] == st.session_state.emotion_filter]
        st.write(filtered_df)

        st.subheader("Coping Mechanism Effectiveness")
        avg_urge_intensity = (
            df.groupby("Coping Mechanism")["Urge Intensity"].mean().reset_index()
        )
        avg_urge_intensity_chart = (
            alt.Chart(avg_urge_intensity)
            .mark_bar()
            .encode(
                x=alt.X("Coping Mechanism:N", title="Coping Mechanism"),
                y=alt.Y("Urge Intensity:Q", title="Average Urge Intensity"),
                tooltip=["Coping Mechanism", "Urge Intensity"],
            )
            .properties(title="Average Urge Intensity by Coping Mechanism")
        )
        st.altair_chart(avg_urge_intensity_chart, use_container_width=True)

        st.subheader("Time of Day Analysis")
        df["Hour"] = pd.to_datetime(df["Time"]).dt.hour
        time_chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("Hour:Q", title="Hour of Day"),
                y=alt.Y("count():Q", title="Number of Entries"),
                tooltip=["Hour", "count()"],
            )
            .properties(title="Distribution of Entries by Hour of Day")
        )
        st.altair_chart(time_chart, use_container_width=True)

        st.subheader("Coping Mechanism Score Analysis vs Coping Mechanism")
        coping_score_chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("Coping Mechanism:N", title="Coping Mechanism"),
                y=alt.Y("Coping Mechanism Score:Q", title="Coping Mechanism Score"),
                tooltip=["Coping Mechanism", "Coping Mechanism Score"],
            )
            .properties(
                title="Distribution of Coping Mechanism Scores by Coping Mechanism"
            )
        )
        st.altair_chart(coping_score_chart, use_container_width=True)

        st.subheader("Analysis of The Gemini")
        st.markdown(st.session_state.llm_analysis, unsafe_allow_html=True)

except FileNotFoundError:
    st.warning("No data available")
