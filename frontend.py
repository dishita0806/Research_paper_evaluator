import streamlit as st
import requests

BACKEND_URL = "http://127.0.0.1:8000/review-paper"

st.set_page_config(
    page_title="Research Paper Reviewer",
    layout="wide"
)

st.title("📄 Research Paper Reviewer Bot")
st.write(
    "Upload a research paper (PDF) to receive a summary, reviewer scores, "
    "and improvement suggestions."
)

uploaded_file = st.file_uploader(
    "Upload a research paper PDF",
    type=["pdf"]
)

if uploaded_file is not None:
    if st.button("Review Paper"):
        with st.spinner("Reviewing paper... This may take a moment."):
            files = {
                "file": (
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    "application/pdf"
                )
            }

            response = requests.post(BACKEND_URL, files=files)

        if response.status_code != 200:
            st.error("Backend error. Please check FastAPI server.")
        else:
            data = response.json()

            st.success("Review completed successfully.")
            
            # -------------------------
            # Summary
            # -------------------------
            st.header("🧠 Paper Summary")
            
            st.write(data.get("summaries", "No summary available."))

            # -------------------------
            # Scores & Decision
            # -------------------------
            st.header("📊 Review Outcome")

            col1, col2 = st.columns(2)

            with col1:
                st.metric("Average Score", data["average_score"])

            with col2:
                st.metric("Decision", data["decision"])

            st.header("📊 Detailed Scores")

            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
                ["Novelty", "Originality" , "Technical Quality", "Methodology", "Experiments", "Clarity"]
            )

            scores = data["scores"]

            with tab1:
                st.metric("Score", scores["Novelty"])
                st.write(scores["justification"]["Novelty"])

            with tab2:
                st.metric("Score", scores["Originality"])
                st.write(scores["justification"]["Originality"])

            with tab3:
                st.metric("Score", scores["Technical_quality"])
                st.write(scores["justification"]["Technical_quality"])

            with tab4:
                st.metric("Score", scores["Methodology"])
                st.write(scores["justification"]["Methodology"])

            with tab5:
                st.metric("Score", scores["Experimental_validation"])
                st.write(scores["justification"]["Experimental_validation"])

            with tab6:
                st.metric("Score", scores["Clarity"])
                st.write(scores["justification"]["Clarity"])


            # -------------------------
            # Observations
            # -------------------------
            st.header("📝 Reviewer Observations")
            with st.expander("View Justifications"):
                for section, text in data.get("scores", {}).get("justification", {}).items():
                    st.markdown(f"**{section.capitalize()}**")
                    st.write(text)

            # -------------------------
            # Suggestions
            # -------------------------
            st.header("💡 Suggestions for Improvement")
            with st.expander("View Suggestions"):
                st.write(data.get("suggestions", "No suggestions generated."))
