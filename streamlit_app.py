import json
import os
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
import streamlit as st

# Page config should be the first Streamlit command
st.set_page_config(
    page_title="Egyptian Drug Pipeline Assistant",
    page_icon="💊",
    layout="wide",
)


# Load local .env safely
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def load_streamlit_secrets():
    secret_keys = ["GROQ_API", "GPT_API", "GEMINI_API", "OLLAMA_PATH"]

    try:
        for key in secret_keys:
            try:
                value = st.secrets.get(key, None)
                if value:
                    os.environ[key] = str(value)
            except Exception:
                continue
    except Exception:
        pass


load_streamlit_secrets()

# Base URL of the FastAPI app in api/app.py. It is started automatically, in-process,
# the first time this app runs (see start_embedded_api_server below) -- no separate
# `uvicorn api.app:app` command needed. Used by the API Agent Tester tab below.
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")

USER_AVATAR = "🧑‍💻"
ASSISTANT_AVATAR = "💊"

# Import the instrumented pipeline runner AFTER secrets are loaded. This is the same
# run_pipeline used by the FastAPI app (see api/workflow.py) -- it wraps every agent
# node with a timer and returns the full final state plus per-agent ("stage_timings")
# and overall ("total_latency_seconds") latency, so the Chat Demo tab and the API
# Agent Tester tab report identical traces.
try:
    from api.workflow import run_pipeline, PipelineStageError
except Exception as e:
    st.error("Could not import the pipeline runner from api/workflow.py")
    st.exception(e)
    st.stop()


# -----------------------------
# Embedded FastAPI/uvicorn server
# -----------------------------
def _api_is_reachable(base_url: str) -> bool:
    try:
        return requests.get(f"{base_url}/health", timeout=1).ok
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def start_embedded_api_server(base_url: str):
    """
    Launch the FastAPI app (api/app.py) with uvicorn in a background daemon thread
    inside this same Streamlit process, so the user never has to run
    `uvicorn api.app:app --reload` separately.

    st.cache_resource makes this run exactly once per Streamlit server process, even
    though the script re-executes on every rerun.
    """
    if _api_is_reachable(base_url):
        # Something (e.g. a manually started uvicorn) is already serving here.
        return None

    import uvicorn

    from api.app import app as fastapi_app

    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8000

    config = uvicorn.Config(fastapi_app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="embedded-uvicorn", daemon=True)
    thread.start()

    deadline = time.time() + 15
    while time.time() < deadline:
        if _api_is_reachable(base_url):
            break
        time.sleep(0.25)

    return server


start_embedded_api_server(API_BASE_URL)

st.title("💊 Egyptian Drug Database Pipeline Assistant")
st.caption(
    "Multilingual (Arabic / Egyptian Arabic / Arabizi / English) demo for the "
    "translate → extract → filter → respond drug lookup pipeline."
)


# -----------------------------
# Helpers
# -----------------------------
def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_result" not in st.session_state:
        st.session_state.last_result = None


def get_user_facing_response(result: Dict[str, Any]) -> str:
    return result.get("response") or "No response was generated."


def is_flagged_result(result: Dict[str, Any]) -> bool:
    """A response is flagged when the responder found the retrieved catalogue
    content insufficient (is_academic=True) and produced no response text."""
    return bool(result.get("is_academic")) and not result.get("response")


def stream_words(text: str, delay: float = 0.02):
    """Yield text word-by-word so st.write_stream can render a typing effect."""
    words = text.split(" ")
    for i, word in enumerate(words):
        yield word + (" " if i < len(words) - 1 else "")
        time.sleep(delay)


def render_chat_message(message: Dict[str, Any], streaming: bool = False):
    """Render one chat turn (history replay or the just-generated turn)."""
    role = message["role"]
    avatar = USER_AVATAR if role == "user" else ASSISTANT_AVATAR

    with st.chat_message(role, avatar=avatar):
        if role == "assistant" and message.get("flagged"):
            st.warning(
                "The retrieved catalogue content was insufficient to answer confidently. "
                "Showing a safe fallback response instead."
            )
        elif role == "assistant" and message.get("result"):
            st.success("Answer generated from the drug catalogue.")

        if streaming:
            st.write_stream(stream_words(message["content"]))
        else:
            st.write(message["content"])

        result = message.get("result")
        if result:
            with st.expander("Details & developer trace"):
                render_result_metadata(result)
                if message.get("show_debug"):
                    render_debug_panel(result)


def render_result_metadata(result: Dict[str, Any]):
    """Render compact metadata after assistant response."""
    extracted = result.get("extracted") or {}
    matches = result.get("context") or []
    total_latency = result.get("total_latency_seconds")

    cols = st.columns(5)
    cols[0].metric("Source", "Commercial catalogue")
    cols[1].metric("Matches", str(len(matches)))
    cols[2].metric("Language", result.get("user_language") or "N/A")
    cols[3].metric("Flagged insufficient", "Yes" if result.get("is_academic") else "No")
    cols[4].metric(
        "Total latency",
        f"{total_latency:.2f}s" if total_latency is not None else "N/A",
    )

    active_filters = {k: v for k, v in extracted.items() if v}
    if active_filters:
        st.caption("Extracted filters: " + ", ".join(f"{k}={v}" for k, v in active_filters.items()))

    if result.get("failed_stage"):
        st.error(
            f"Pipeline aborted at stage '{result['failed_stage']}' after "
            f"{result.get('stage_latency_seconds', 'N/A')}s: {result.get('error')}"
        )


def render_stage_timings(result: Dict[str, Any]):
    """Per-agent latency (each timed node in workflow.py) plus overall latency."""
    timings: Dict[str, float] = result.get("stage_timings") or {}
    total_latency = result.get("total_latency_seconds")

    if not timings and total_latency is None:
        st.caption("No latency data on this result (pipeline runner may have failed before timing started).")
        return

    st.markdown("#### Latency — per agent and overall")
    st.metric("Overall pipeline latency", f"{total_latency:.3f}s" if total_latency is not None else "N/A")

    if timings:
        ordered = dict(sorted(timings.items(), key=lambda kv: kv[1], reverse=True))
        st.bar_chart(ordered)
        st.table([{"agent": name, "latency_seconds": seconds} for name, seconds in ordered.items()])


def render_debug_panel(result: Dict[str, Any]):
    """Optional developer/debug panel for portfolio demo transparency."""
    with st.expander("Developer Trace / Internal State", expanded=False):
        render_stage_timings(result)
        st.divider()

        st.markdown("#### English Query")
        st.code(result.get("eng_query") or "N/A")

        st.markdown("#### Extracted Filters")
        st.json(result.get("extracted") or {})

        matches = result.get("context") or []
        if matches:
            st.markdown("#### Matched Drugs")
            st.dataframe(matches)

        st.divider()
        st.markdown("#### Full pipeline state")
        st.json(result, expanded=False)


# -----------------------------
# API Agent Tester helpers (calls the FastAPI app in api/app.py)
# -----------------------------
def call_agent_api(base_url: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST payload to {base_url}{path} and return {"ok", "status_code", "data"}."""
    try:
        resp = requests.post(f"{base_url}{path}", json=payload, timeout=120)
    except requests.exceptions.RequestException as e:
        return {"ok": False, "status_code": None, "data": {"error": str(e)}}

    try:
        data = resp.json()
    except ValueError:
        data = {"error": resp.text}

    return {"ok": resp.ok, "status_code": resp.status_code, "data": data}


# -----------------------------
# Session Initialization
# -----------------------------
init_session_state()


# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.header("Demo Settings")

    show_debug = st.toggle(
        "Show developer trace",
        value=True,
        help="Shows the translation, extracted filters, matched drugs, and per-agent latency.",
    )

    clear_chat = st.button("Clear chat")
    if clear_chat:
        st.session_state.messages = []
        st.session_state.last_result = None
        st.rerun()

    st.divider()
    st.markdown("### Suggested demo prompts")
    st.markdown(
        """
- عايز حاجة للصداع تحت 20 جنيه
- 3ayez a3raf se3r Panadol Extra
- What is the price of Cataflam?
- هل يوجد بديل لدواء النيكسيوم بنفس المادة الفعالة؟
        """
    )


tab_chat, tab_api = st.tabs(["💬 Chat Demo", "🧪 API Agent Tester"])


with tab_chat:
    # -----------------------------
    # Chat History
    # -----------------------------
    for message in st.session_state.messages:
        render_chat_message(message)

    # -----------------------------
    # Input Area
    # -----------------------------
    query = st.chat_input("Ask about a drug in Arabic, Egyptian Arabic, Arabizi, or English...")

    # -----------------------------
    # Main Execution
    # -----------------------------
    if query:
        user_message = {"role": "user", "content": query}
        st.session_state.messages.append(user_message)
        render_chat_message(user_message)

        chat_history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
        ]

        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            with st.spinner("Running drug lookup pipeline..."):
                try:
                    # run_pipeline (api/workflow.py) times every agent node and
                    # returns the full final state plus stage_timings /
                    # total_latency_seconds alongside it.
                    result = run_pipeline(query, chat_history)
                    st.session_state.last_result = result

                    response = get_user_facing_response(result)
                    flagged = is_flagged_result(result)

                    if flagged:
                        st.warning(
                            "The retrieved catalogue content was insufficient to answer confidently. "
                            "Showing a safe fallback response instead."
                        )
                    else:
                        st.success("Answer generated from the drug catalogue.")

                except PipelineStageError as e:
                    # A stage raised, but every stage that completed before it was
                    # still timed and its output is still in e.state -- keep that
                    # trace instead of throwing it away.
                    result = {
                        "stage_timings": e.stage_timings,
                        "total_latency_seconds": None,
                        "failed_stage": e.stage,
                        "stage_latency_seconds": round(e.elapsed, 3),
                        "error": str(e.original),
                        **e.state,
                    }
                    st.session_state.last_result = result
                    response = (
                        f"The pipeline failed at the '{e.stage}' stage after {e.elapsed:.2f}s. "
                        "See the developer trace below for the partial state and per-agent timings."
                    )
                    flagged = False
                    st.error(response)
                    with st.expander("Error details"):
                        st.exception(e.original)

                except Exception as e:
                    response = (
                        "The demo encountered a runtime error while processing the request. "
                        "Please check the workflow, API keys, and the drug data files."
                    )
                    flagged = False
                    result = None
                    st.error(response)
                    with st.expander("Error details"):
                        st.exception(e)

            # Streamed outside the spinner so the typing effect is visible.
            st.write_stream(stream_words(response))

            if result:
                with st.expander("Details & developer trace"):
                    render_result_metadata(result)
                    if show_debug:
                        render_debug_panel(result)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response,
                "result": result,
                "flagged": flagged,
                "show_debug": show_debug,
            }
        )

    # -----------------------------
    # Footer
    # -----------------------------
    st.divider()
    st.caption(
        "Portfolio demo: multilingual Egyptian drug lookup with query translation, "
        "metadata extraction, catalogue filtering, and grounded response generation."
    )


with tab_api:
    st.caption(
        f"Calls the FastAPI app in `api/app.py` over HTTP at `{API_BASE_URL}` "
        "(started automatically, in-process, when this Streamlit app launches). "
        "Each agent can be exercised in isolation here, independently of the "
        "in-process chat demo on the other tab."
    )

    api_reachable = _api_is_reachable(API_BASE_URL)
    if not api_reachable:
        st.warning(
            f"Could not reach the embedded API at {API_BASE_URL} yet. It may still be "
            "starting up -- reload this page in a moment. If it keeps failing, check the "
            "terminal running Streamlit for startup errors (e.g. the port may be in use)."
        )

    api_base = st.text_input("FastAPI base URL", f"{API_BASE_URL}/api")

    def call(endpoint: str, payload: dict):
        outcome = call_agent_api(api_base, endpoint, payload)
        if outcome["ok"]:
            return outcome["data"]

        data = outcome["data"]
        detail = data.get("detail") if isinstance(data, dict) else data
        if isinstance(detail, dict):
            st.error(
                f"Failed at stage: **{detail.get('failed_stage')}** "
                f"(ran for {detail.get('stage_latency_seconds')}s before failing)"
            )
            if detail.get("completed_stage_timings"):
                st.caption(f"Stages completed before the failure: {detail['completed_stage_timings']}")
            st.code(detail.get("error", ""))
            if detail.get("state") is not None:
                with st.expander("Pipeline state going into the failed stage"):
                    st.json(detail["state"])
        else:
            st.error(f"Request failed (HTTP {outcome['status_code']}): {detail}")
        return None

    tab_full, tab_translate, tab_extract, tab_filter, tab_respond = st.tabs(
        ["Full pipeline", "1. Translate", "2. Extract", "3. Filter", "4. Respond"]
    )

    with tab_full:
        st.subheader("Run the whole pipeline end to end")
        pipeline_query = st.text_area("Query (any language)", "عايز حاجة للصداع تحت 20 جنيه")
        if st.button("Run full pipeline", type="primary"):
            with st.spinner("Running..."):
                result = call("/pipeline/run", {"query": pipeline_query, "chat_hist": []})
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
