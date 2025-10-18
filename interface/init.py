import streamlit as st

from chat_window import render_chat
from interface.sidebar.__init__ import render_sidebar

st.set_page_config(page_title='Healthcare Assistant', initial_sidebar_state='collapsed')

if not st.session_state:
    st.session_state.chats = dict()

sidebar_column, master_column = st.columns([1,3])

with sidebar_column:
    render_sidebar(st.session_state.chats)

with master_column:
    render_chat(st.session_state.chats)