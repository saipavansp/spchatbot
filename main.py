import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import asyncio

# Load environment variables from the .env file
load_dotenv()
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# Configure the API key
genai.configure(api_key=GEMINI_API_KEY)

# Set up the model configuration
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 500,  # Reduced output tokens to optimize speed
    "response_mime_type": "text/plain",
}

# Initialize the model once (to avoid re-creation on every input)
model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    generation_config=generation_config,
)

# Initialize a Streamlit app
st.title("SP AI Chatbot")
st.write("Ask a question, and I'll provide a response!")

# Text input for user query
user_input = st.text_input("Ask Anything:")

# Reuse chat session across user inputs (store it in session state)
if 'chat_session' not in st.session_state:
    st.session_state.chat_session = model.start_chat(history=[])


# Define an async function to send a message and get a response
async def get_chat_response_async(user_input):
    return await asyncio.to_thread(st.session_state.chat_session.send_message, user_input)


# Caching the response to prevent repeated API calls for the same input
@st.cache_data
def get_chat_response_cached(user_input):
    response = asyncio.run(get_chat_response_async(user_input))
    return response.text


# Button for submitting user input
if st.button("Get AI Response"):
    if user_input:
        # Measure API call duration
        with st.spinner('Getting AI response...'):
            response_text = get_chat_response_cached(user_input)

        # Display the AI response
        st.write("**AI Response:**")
        st.write(response_text)
    else:
        st.write("Please enter a question to get a response.")
