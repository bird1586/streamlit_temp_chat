import streamlit as st
import redis
import json
import uuid
from datetime import datetime

# --- Configuration loaded from secrets ---
# The st.secrets object automatically loads the contents of secrets.toml
try:
    REDIS_HOST = st.secrets["redis"]["host"]
    REDIS_PORT = st.secrets["redis"]["port"]
    REDIS_DB = st.secrets["redis"]["db"]
    # password is an optional key
    REDIS_PASSWORD = st.secrets["redis"].get("password", None)
except KeyError:
    st.error("Redis credentials not found in `.streamlit/secrets.toml`. Please configure your secrets.")
    st.stop()

CHAT_TTL_SECONDS = 3 * 60  # 3 minutes

# --- Redis Connection ---
@st.cache_resource
def get_redis_connection():
    try:
        r = redis.StrictRedis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        r.ping()
        return r
    except redis.exceptions.ConnectionError as e:
        st.error(f"Could not connect to Redis: {e}")
        st.stop()

# --- Functions to interact with Redis ---
def add_message(room_id, user, message):
    """Adds a new message to the chatroom and sets its TTL."""
    r = get_redis_connection()
    message_data = {
        "user": user,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "type": "code" if message.strip().startswith("`") and message.strip().endswith("`") else "text"
    }
    r.rpush(room_id, json.dumps(message_data))
    r.expire(room_id, CHAT_TTL_SECONDS)

def get_messages(room_id):
    """Retrieves all messages for a given chatroom."""
    r = get_redis_connection()
    messages_json = r.lrange(room_id, 0, -1)
    messages = [json.loads(msg) for msg in messages_json]
    return messages

# --- Streamlit UI ---
st.title("Temporary Chatroom 💬")

# Use session_state to manage user's name and room ID
if "username" not in st.session_state:
    st.session_state.username = ""
if "room_id" not in st.session_state:
    st.session_state.room_id = ""

# --- User Input Section ---
col1, col2 = st.columns(2)
with col1:
    username = st.text_input("Your Name", value=st.session_state.username)
with col2:
    if st.session_state.room_id:
        room_id = st.text_input("Enter Chatroom ID", value=st.session_state.room_id)
    else:
        if st.button("Generate Room ID"):
            room_id = str(uuid.uuid4())[:4]
            st.session_state.room_id = room_id
            st.rerun()
        room_id = st.text_input("Enter Chatroom ID", value=st.session_state.room_id)

# Only show the chat interface if a user and room ID are entered
if username and room_id:
    st.session_state.username = username
    st.session_state.room_id = room_id

    st.divider()

    col_button, col_gap = st.columns([1, 4])
    with col_button:
        if st.button("Refresh 🔄"):
            st.rerun()

    chat_history_container = st.container()
    
    with chat_history_container:
        messages = get_messages(room_id)
        for msg in messages:
            with st.chat_message(msg["user"]):
                if msg["type"] == "code":
                    st.code(msg["message"].strip("`"))
                else:
                    st.write(msg["message"])
                st.caption(f"Sent at: {datetime.fromisoformat(msg['timestamp']).strftime('%H:%M')}")
    
    if user_message := st.chat_input("Say something..."):
        add_message(room_id, username, user_message)
        st.rerun()
else:
    st.warning("Please enter your name and a chatroom ID or generate a new one.")
