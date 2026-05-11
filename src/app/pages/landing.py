"""Page: Landing. See specs/user-interface.md Section 4.1."""
import streamlit as st


def render():
    st.title("BrewMatch")
    st.subheader("Your Coffee Troubleshooting Tool")

    st.markdown("---")

    if st.session_state.user_id:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Get Started", use_container_width=True):
                st.session_state.page = "bean_input"
                st.rerun()
        with col2:
            if st.button("Demo Mode", use_container_width=True):
                st.session_state.demo_mode = True
                st.session_state.page = "demo"
                st.rerun()
    else:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Sign In", use_container_width=True):
                st.session_state.page = "auth"
                st.rerun()
        with col2:
            if st.button("Demo Mode", use_container_width=True):
                st.session_state.demo_mode = True
                st.session_state.page = "demo"
                st.rerun()

    st.markdown("---")
    st.markdown("### How It Works")
    st.markdown(
        "1. Tell us about your beans\n"
        "2. Get a starting recipe\n"
        "3. Brew and report what went wrong\n"
        "4. Get a specific diagnosis and fix\n"
    )
