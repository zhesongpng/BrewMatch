"""Page: Landing. See specs/user-interface.md Section 4.1."""
import streamlit as st

_HERO_CSS = """
<style>
.bm-hero {
    text-align: center;
    padding: 2rem 1rem 1.5rem 1rem;
}
.bm-hero-title {
    font-size: 2.8rem;
    font-weight: 800;
    color: #C87941;
    margin-bottom: 0.25rem;
    letter-spacing: -0.5px;
}
.bm-hero-sub {
    font-size: 1.15rem;
    color: #5a5a5a;
    font-weight: 400;
}
.bm-step-box {
    background: #F0EDE8;
    border-radius: 0.75rem;
    padding: 1.25rem;
    text-align: center;
    height: 100%;
}
.bm-step-num {
    font-size: 1.5rem;
    font-weight: 700;
    color: #C87941;
}
.bm-step-title {
    font-size: 1rem;
    font-weight: 600;
    color: #2C2C2C;
    margin: 0.25rem 0;
}
.bm-step-desc {
    font-size: 0.85rem;
    color: #6b6b6b;
}
</style>
"""


def render():
    st.markdown(_HERO_CSS, unsafe_allow_html=True)

    # --- Hero ---
    st.markdown(
        '<div class="bm-hero">'
        '<div class="bm-hero-title">BrewMatch</div>'
        '<div class="bm-hero-sub">Get a better cup. Every brew.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # --- CTA buttons ---
    if st.session_state.user_id:
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            if st.button("Start Brewing", type="primary", use_container_width=True):
                st.session_state.page = "bean_input"
                st.rerun()
    else:
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            if st.button("Get Started", type="primary", use_container_width=True):
                st.session_state.page = "auth"
                st.rerun()
        with col3:
            if st.button("Try Demo Account", use_container_width=True):
                st.session_state.page = "auth"
                st.rerun()
        st.caption(
            "Want to explore first? Sign in with "
            "**demo@brewmatch.com** / **brewmatch** to try a pre-built profile."
        )

    st.markdown("---")

    # --- How It Works ---
    st.markdown("### How It Works")
    cols = st.columns(4)
    steps = [
        ("1", "Describe Your Beans", "Tell us the roast, origin, and flavors."),
        ("2", "Get a Recipe", "BrewMatch picks the best pour-over method and parameters."),
        ("3", "Brew & Feedback", "Follow the steps, then rate what went right or wrong."),
        ("4", "Get a Fix", "Specific diagnosis tells you exactly what to adjust."),
    ]
    for col, (num, title, desc) in zip(cols, steps):
        with col:
            st.markdown(
                f'<div class="bm-step-box">'
                f'<div class="bm-step-num">{num}</div>'
                f'<div class="bm-step-title">{title}</div>'
                f'<div class="bm-step-desc">{desc}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # --- Value prop ---
    st.markdown("### Why BrewMatch?")
    vcol1, vcol2, vcol3 = st.columns(3)
    with vcol1:
        st.markdown(
            '**Diagnosis-first**\n\n'
            'Most apps recommend recipes. BrewMatch also tells you *why* a cup '
            'tastes off and exactly what to change.'
        )
    with vcol2:
        st.markdown(
            '**Gets Smarter**\n\n'
            'Every brew you log teaches the model your palate. '
            'After 10 brews it blends your taste with similar coffee drinkers.'
        )
    with vcol3:
        st.markdown(
            '**Science-Backed**\n\n'
            'Adjustments are grounded in extraction theory — grind size, '
            'water temperature, brew time, and dose — not guesswork.'
        )
