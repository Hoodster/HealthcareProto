import streamlit as st

def render_sidebar(chats):
    st.sidebar.title("Heartcare assistant")

    st.sidebar.subheader("History")
    if len(chats) > 0:
        for chat in enumerate(chats.keys()):
            st.sidebar.text(chat)
    else:
        st.sidebar.text("No records yet.")

def run():
    st.sidebar.title("Heartcare Assistant")
    st.sidebar.subheader("Patient History")