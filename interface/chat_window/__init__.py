import streamlit as st

def create_new_chat():
    pass


def render_chat(chats):
    current_chat = []
    [left, right] = st.columns([1,1])
    with left:
        st.title("New chat")
    with right:
        new_c = st.button("Start new conversation")
        if new_c:
            st.session_state.chats =
    if prompt := st.chat_input("Cwelu"):
        chats.append(prompt)
        with st.chat_message("user"):
            st.write(prompt)

def run():
    try:
