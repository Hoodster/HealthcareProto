import streamlit as st

from interface.sidebar.__init__ import Sidebar

st.set_page_config(page_title="Echo Chat", layout="wide")

    # Initialize chat history if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = []


    # Create two columns - one for chat history (smaller) and one for active chat (larger)
col1, col2 = st.columns([1, 3])

# Side panel for chat history
with col1:
    Sidebar(st).component()

    # Main chat area
    with col2:
        col_1, col_2 = st.columns([3,1])
        with col_1:
            st.title("Echo Chat")
        with col_2:
           if st.button("New chat"):
              history = st.session_state.messages
              archived_chat = { 'chat': history, 'title': st.title}

        # Display full chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Handle user input
        if prompt := st.chat_input("Say something..."):
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)

            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Create echo response
            response = f"Echo: {prompt}"

            # Display assistant response
            with st.chat_message("assistant"):
                st.markdown(response)

            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": response})