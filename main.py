import os
from dotenv import load_dotenv
import streamlit as st
import google.generativeai as genai

# Set up the API key
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Create the model configuration
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 5000,
    "response_mime_type": "text/plain",
}

# Initialize the Streamlit app
st.title("SP AI Chatbot")
st.write("Ask a question, and I'll provide a response!")

# User input
user_input = st.text_input("Ask Anything:")

# If user submits a question
if st.button("Get AI Response"):
    if user_input:
        # Create the model
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            generation_config=generation_config,
        )

        # Start a chat session
        chat_session = model.start_chat(history=[])

        # Send user input to the model
        response = chat_session.send_message(user_input)

        # Display the AI-generated response
        st.write("**AI Response:**")
        st.write(response.text)
    else:
        st.write("Please enter a question to get a response.")
