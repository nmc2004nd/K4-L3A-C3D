import streamlit as st
from dotenv import load_dotenv

from src.task10_generation import generate_with_citation

load_dotenv()

st.set_page_config(
    page_title="RAG Chatbot — Du lịch Việt Nam",
    page_icon="🏖️",
    layout="wide",
)

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("🏖️ RAG Chatbot")
    st.caption(
        "Chatbot hỏi đáp về **du lịch Việt Nam** — "
        "Luật Du lịch 2017, Nghị định 168, Chiến lược phát triển du lịch 2030 "
        "và các bài viết du lịch ẩm thực."
    )
    top_k = st.slider("Số chunks truy xuất", 3, 10, 5)
    st.divider()
    st.markdown(
        "**Retrieval:** hybrid (dense + BM25 → RRF) với PageIndex fallback"
    )

st.title("🏖️ Du lịch Việt Nam — RAG Chatbot")
st.caption("Đặt câu hỏi về luật du lịch, chính sách hoặc ẩm thực Việt Nam.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("sources"):
            with st.expander(
                f"📚 Nguồn tham khảo ({len(message['sources'])} chunks "
                f"— {message.get('retrieval_source', 'N/A')})"
            ):
                for idx, src in enumerate(message["sources"], 1):
                    score_display = f"{src['score']:.4f}" if isinstance(src.get("score"), (int, float)) else "N/A"
                    st.markdown(
                        f"**[S{idx}]** `{src['metadata'].get('title', 'N/A')}` "
                        f"— *{src['metadata'].get('source', 'N/A')}* "
                        f"(score: `{score_display}`, method: `{src.get('retrieval_method', 'N/A')}`)"
                    )

query = st.chat_input("Nhập câu hỏi...")

if query:
    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Đang truy xuất và tạo câu trả lời..."):
            result = generate_with_citation(query, top_k=top_k)

        answer = result["answer"]
        sources = result.get("sources", [])
        retrieval_source = result.get("retrieval_source", "none")

        st.markdown(answer)

        if sources:
            with st.expander(
                f"📚 Nguồn tham khảo ({len(sources)} chunks — {retrieval_source})"
            ):
                for idx, src in enumerate(sources, 1):
                    score_display = f"{src['score']:.4f}" if isinstance(src.get("score"), (int, float)) else "N/A"
                    st.markdown(
                        f"**[S{idx}]** `{src['metadata'].get('title', 'N/A')}` "
                        f"— *{src['metadata'].get('source', 'N/A')}* "
                        f"(score: `{score_display}`, method: `{src.get('retrieval_method', 'N/A')}`)"
                    )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "retrieval_source": retrieval_source,
        }
    )
