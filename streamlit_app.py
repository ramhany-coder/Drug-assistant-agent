import json

import requests
import streamlit as st

st.set_page_config(page_title="Egyptian Drug Pipeline Tester", layout="wide")

st.sidebar.title("Settings")
api_base = st.sidebar.text_input("FastAPI base URL", "http://localhost:8000/api")

st.title("Egyptian Drug Database — Pipeline Tester")


def call(endpoint: str, payload: dict):
    try:
        r = requests.post(f"{api_base}{endpoint}", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError:
        try:
            detail = r.json().get("detail")
        except Exception:
            detail = r.text
        if isinstance(detail, dict):
            st.error(f"Failed at stage: **{detail.get('failed_stage')}** "
                     f"(ran for {detail.get('stage_latency_seconds')}s before failing)")
            if detail.get("completed_stage_timings"):
                st.caption(f"Stages completed before the failure: {detail['completed_stage_timings']}")
            st.code(detail.get("error", ""))
            if detail.get("state") is not None:
                with st.expander("Pipeline state going into the failed stage"):
                    st.json(detail["state"])
        else:
            st.error(f"Request failed ({r.status_code}): {detail}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Request failed: {e}")
        return None


tab_full, tab_translate, tab_extract, tab_filter, tab_respond = st.tabs(
    ["Full pipeline", "1. Translate", "2. Extract", "3. Filter", "4. Respond"]
)

with tab_full:
    st.subheader("Run the whole pipeline end to end")
    query = st.text_area("Query (any language)", "عايز حاجة للصداع تحت 20 جنيه")
    if st.button("Run full pipeline", type="primary"):
        with st.spinner("Running..."):
            result = call("/pipeline/run", {"query": query, "chat_hist": []})
        if result:
            st.subheader("Final response")
            st.write(result.get("response"))
            st.caption(f"is_academic: {result.get('is_academic')}")

            st.subheader("Latency")
            st.metric("Total", f"{result.get('total_latency_seconds', 0)}s")
            timings = result.get("stage_timings") or {}
            if timings:
                st.bar_chart(timings)
                st.caption(" · ".join(f"{k}: {v}s" for k, v in timings.items()))

            with st.expander("Full pipeline state"):
                st.json(result)
            if result.get("context"):
                st.subheader("Matched drugs")
                st.dataframe(result["context"])

with tab_translate:
    st.subheader("Translator agent — /translate")
    raw_query = st.text_input("Raw query", "عايز بنادول")
    if st.button("Translate", key="btn_translate"):
        result = call("/translate", {"query": raw_query})
        if result:
            st.caption(f"⏱ {result.get('latency_seconds')}s")
            st.json(result)

with tab_extract:
    st.subheader("Metadata extractor agent — /extract")
    eng_query = st.text_input("English query", "I want panadol under 20 EGP")
    if st.button("Extract metadata", key="btn_extract"):
        result = call("/extract", {"eng_query": eng_query})
        if result:
            st.caption(f"⏱ {result.get('latency_seconds')}s")
            st.json(result)

with tab_filter:
    st.subheader("Metadata filter agent — /filter")
    st.caption("Leave a field blank to skip it. price_egp accepts <20, 10-30, asc, desc.")
    c1, c2, c3 = st.columns(3)
    commercial_name_en = c1.text_input("commercial_name_en")
    commercial_name_ar = c2.text_input("commercial_name_ar")
    scientific_name = c3.text_input("scientific_name")
    manufacturer = c1.text_input("manufacturer")
    drug_class = c2.text_input("drug_class")
    route = c3.text_input("route")
    price_egp = st.text_input("price_egp")
    if st.button("Filter drugs", key="btn_filter"):
        payload = {
            "commercial_name_en": commercial_name_en or None,
            "commercial_name_ar": commercial_name_ar or None,
            "scientific_name": scientific_name or None,
            "manufacturer": manufacturer or None,
            "drug_class": drug_class or None,
            "route": route or None,
            "price_egp": price_egp or None,
        }
        result = call("/filter", payload)
        if result:
            st.caption(f"⏱ {result.get('latency_seconds')}s")
            matches = result.get("context", [])
            st.write(f"{len(matches)} match(es)")
            if matches:
                st.dataframe(matches)

with tab_respond:
    st.subheader("Early responder agent — /respond")
    eng_query2 = st.text_area("English query", "What is the price of Panadol?", key="eng_query2")
    user_language = st.selectbox(
        "User language",
        ["english", "egyptian_arabic", "msa", "arabizi", "mixed", "other"],
    )
    context_json = st.text_area("Context (JSON list of drug dicts)", "[]")
    if st.button("Generate response", key="btn_respond"):
        try:
            context = json.loads(context_json)
        except json.JSONDecodeError as e:
            st.error(f"Context must be valid JSON: {e}")
            context = None
        if context is not None:
            payload = {
                "eng_query": eng_query2,
                "user_language": user_language,
                "context": context,
                "chat_hist": [],
            }
            result = call("/respond", payload)
            if result:
                st.caption(f"⏱ {result.get('latency_seconds')}s")
                st.json(result)
