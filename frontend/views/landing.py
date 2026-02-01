# This project was developed with assistance from AI tools.
"""
Landing page view - public page with calculator and anonymous chat.
"""
import streamlit as st

from agents import get_chat_agent
from frontend.auth import get_authenticator
from frontend.components import render_logo


def render_landing_sidebar():
    """Render the sidebar with login form for the landing page."""
    with st.sidebar:
        render_logo()
        
        st.markdown("### Sign In")
        authenticator = get_authenticator()
        authenticator.login(location="main")
        
        if st.session_state.get("authentication_status") is False:
            st.error("Invalid credentials")
        elif st.session_state.get("authentication_status") is None:
            st.markdown("---")
            st.caption("**Demo Credentials**")
            st.code("admin / admin123", language=None)
            st.code("borrower / borrower123", language=None)


def render_mortgage_calculator():
    """Render an interactive mortgage calculator."""
    st.markdown("### Mortgage Calculator")
    
    col1, col2 = st.columns(2)
    
    with col1:
        home_price = st.number_input(
            "Home Price ($)", 
            min_value=50000, 
            max_value=10000000, 
            value=350000, 
            step=5000,
            format="%d"
        )
        down_payment_pct = st.slider(
            "Down Payment (%)", 
            min_value=0, 
            max_value=50, 
            value=20
        )
        interest_rate = st.number_input(
            "Interest Rate (%)", 
            min_value=0.1, 
            max_value=15.0, 
            value=6.5, 
            step=0.125,
            format="%.3f"
        )
    
    with col2:
        loan_term = st.selectbox(
            "Loan Term", 
            options=[30, 20, 15, 10], 
            index=0,
            format_func=lambda x: f"{x} years"
        )
        property_tax_rate = st.number_input(
            "Property Tax Rate (%/year)", 
            min_value=0.0, 
            max_value=5.0, 
            value=1.2, 
            step=0.1
        )
        insurance_annual = st.number_input(
            "Home Insurance ($/year)", 
            min_value=0, 
            max_value=20000, 
            value=1500, 
            step=100
        )
    
    # Calculate values
    down_payment = home_price * (down_payment_pct / 100)
    loan_amount = home_price - down_payment
    monthly_rate = (interest_rate / 100) / 12
    num_payments = loan_term * 12
    
    # Monthly principal & interest (standard amortization formula)
    if monthly_rate > 0:
        monthly_pi = loan_amount * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)
    else:
        monthly_pi = loan_amount / num_payments
    
    monthly_tax = (home_price * (property_tax_rate / 100)) / 12
    monthly_insurance = insurance_annual / 12
    monthly_total = monthly_pi + monthly_tax + monthly_insurance
    
    total_interest = (monthly_pi * num_payments) - loan_amount
    
    # Display results
    st.markdown("---")
    
    result_cols = st.columns(4)
    with result_cols[0]:
        st.metric("Monthly Payment", f"${monthly_total:,.0f}")
    with result_cols[1]:
        st.metric("Principal & Interest", f"${monthly_pi:,.0f}")
    with result_cols[2]:
        st.metric("Loan Amount", f"${loan_amount:,.0f}")
    with result_cols[3]:
        st.metric("Down Payment", f"${down_payment:,.0f}")
    
    # Payment breakdown
    with st.expander("Payment Breakdown", expanded=True):
        breakdown_cols = st.columns(3)
        with breakdown_cols[0]:
            st.markdown(f"**Principal & Interest:** ${monthly_pi:,.2f}/mo")
        with breakdown_cols[1]:
            st.markdown(f"**Property Tax:** ${monthly_tax:,.2f}/mo")
        with breakdown_cols[2]:
            st.markdown(f"**Insurance:** ${monthly_insurance:,.2f}/mo")
        
        st.markdown(f"**Total Interest Over Loan:** ${total_interest:,.0f}")
        st.markdown(f"**Total Cost (Principal + Interest):** ${loan_amount + total_interest:,.0f}")


def render_anonymous_chat():
    """Render a chat panel for anonymous (non-authenticated) users."""
    # Initialize anonymous chat state
    if "anon_messages" not in st.session_state:
        st.session_state.anon_messages = []
    
    st.markdown("### Have questions?")
    
    # Display existing chat messages
    for msg in st.session_state.anon_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about mortgage regulations, rates, loan process and more...", key="anon_chat_input"):
        # Immediately display the user's message
        st.session_state.anon_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Show assistant response with spinner
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    chat_agent = get_chat_agent()
                    response = chat_agent.chat_anonymous(
                        message=prompt,
                        session_messages=st.session_state.anon_messages[:-1]
                    )
                except Exception as e:
                    print(f"Anonymous chat error: {e}")
                    response = "I apologize, but I'm having trouble responding. Please try again."
            
            st.markdown(response)
        
        st.session_state.anon_messages.append({"role": "assistant", "content": response})


def render_landing_page():
    """Render the public landing page with mortgage calculator and anonymous chat."""
    render_landing_sidebar()
    
    # Single column layout: calculator on top, chat below
    render_mortgage_calculator()
    st.markdown("---")
    render_anonymous_chat()
