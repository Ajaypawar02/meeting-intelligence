import streamlit as st
import requests
import json

# --- CONFIGURATION ---
FASTAPI_URL = "http://localhost:8000"

st.set_page_config(page_title="The Meeting Desk", layout="wide", page_icon="🖋️")

# =====================================================================================
# DESIGN SYSTEM — "The Copy Desk"
# An AI proofs a transcript the way a copy editor proofs a manuscript: it flags what
# it isn't sure of, and a human reads those flags before anything goes to print.
# The visual language borrows from an editorial desk — slab display type, a mono
# face for IDs and timestamps, a paper-on-ink palette, and a proofmark spine that
# runs down the side of every item still waiting on a human read.
# =====================================================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    :root {
        --ink: #12161D;
        --panel: #1B212B;
        --panel-raised: #212938;
        --paper: #ECE7DA;
        --muted: #8A93A3;
        --rule: #313B49;
        --green: #4F9668;
        --green-soft: rgba(79, 150, 104, 0.14);
        --red: #BB4B3C;
        --red-soft: rgba(187, 75, 60, 0.14);
        --amber: #D8A23E;
        --amber-soft: rgba(216, 162, 62, 0.16);
    }

    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background-color: var(--ink) !important;
        color: var(--paper) !important;
        font-family: 'IBM Plex Sans', sans-serif;
    }

    h1, h2, h3, h4 {
        font-family: 'Zilla Slab', serif !important;
        color: var(--paper) !important;
        letter-spacing: 0.2px;
    }

    p, span, label, div, li { color: var(--paper); }

    code, .stCode, pre {
        font-family: 'IBM Plex Mono', monospace !important;
    }

    /* ---------- Masthead ---------- */
    .desk-masthead {
        border-bottom: 3px solid var(--paper);
        padding-bottom: 14px;
        margin-bottom: 6px;
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
    }
    .desk-masthead h1 {
        font-size: 2.4rem;
        margin: 0;
        line-height: 1;
    }
    .desk-masthead .kicker {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.72rem;
        letter-spacing: 2.5px;
        color: var(--amber);
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    .desk-masthead .dateline {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.78rem;
        color: var(--muted);
        text-align: right;
    }

    /* ---------- Sidebar ---------- */
    [data-testid="stSidebar"] {
        background-color: var(--panel) !important;
        border-right: 1px solid var(--rule);
    }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.95rem !important;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        color: var(--amber) !important;
    }

    /* ---------- Stepper ---------- */
    .stepper { display: flex; align-items: center; margin: 10px 0 22px 0; }
    .step { display: flex; align-items: center; flex: 1; }
    .step-dot {
        width: 26px; height: 26px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-family: 'IBM Plex Mono', monospace; font-size: 0.75rem; font-weight: 500;
        border: 2px solid var(--rule); color: var(--muted); flex-shrink: 0;
        background: var(--panel);
    }
    .step-dot.done { background: var(--green); border-color: var(--green); color: var(--ink); }
    .step-dot.active { background: var(--amber); border-color: var(--amber); color: var(--ink); }
    .step-label {
        margin-left: 8px; font-size: 0.82rem; color: var(--muted); white-space: nowrap;
    }
    .step-label.done, .step-label.active { color: var(--paper); font-weight: 500; }
    .step-line { flex: 1; height: 2px; background: var(--rule); margin: 0 10px; }
    .step-line.done { background: var(--green); }

    /* ---------- Cards / expanders ---------- */
    [data-testid="stExpander"] {
        background-color: var(--panel);
        border: 1px solid var(--rule);
        border-radius: 6px;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: var(--panel);
        border: 1px solid var(--rule) !important;
        border-radius: 4px;
    }

    /* ---------- Proof slip (review card) ---------- */
    .proof-slip {
        border-left: 4px solid var(--amber);
        padding: 2px 4px 2px 16px;
        margin-bottom: -6px;
    }
    .proof-slip .tag {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.7rem;
        color: var(--ink);
        background: var(--amber);
        padding: 2px 7px;
        border-radius: 3px;
        letter-spacing: 0.5px;
    }
    .proof-slip .item-id {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.78rem;
        color: var(--muted);
    }
    .proof-slip .reason {
        font-size: 0.78rem;
        color: var(--amber);
        margin-top: 2px;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }

    /* ---------- Metric ---------- */
    [data-testid="stMetric"] {
        background: var(--panel-raised);
        border: 1px solid var(--rule);
        border-radius: 6px;
        padding: 12px 16px;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'IBM Plex Mono', monospace !important;
        text-transform: uppercase;
        font-size: 0.7rem !important;
        letter-spacing: 1.2px;
        color: var(--muted) !important;
    }
    [data-testid="stMetricValue"] { color: var(--amber) !important; }

    /* ---------- Buttons ---------- */
    .stButton button {
        font-family: 'IBM Plex Mono', monospace;
        border-radius: 4px;
        border: 1px solid var(--rule);
        transition: transform 0.08s ease;
    }
    .stButton button:hover { transform: translateY(-1px); }
    [data-testid="baseButton-primary"] {
        background-color: var(--green) !important;
        border-color: var(--green) !important;
        color: var(--ink) !important;
        font-weight: 600 !important;
    }
    [data-testid="baseButton-secondary"] {
        background-color: transparent !important;
        border-color: var(--red) !important;
        color: var(--red) !important;
    }
    [data-testid="baseButton-secondary"]:hover {
        background-color: var(--red-soft) !important;
    }

    /* ---------- Alerts ---------- */
    [data-testid="stAlertContentInfo"], [data-testid="stAlertContentSuccess"],
    [data-testid="stAlertContentWarning"], [data-testid="stAlertContentError"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    /* ---------- Transcript viewer ---------- */
    .transcript-turn {
        display: flex;
        gap: 14px;
        padding: 10px 0;
        border-bottom: 1px solid var(--rule);
    }
    .transcript-turn .who {
        flex: 0 0 150px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.76rem;
        color: var(--amber);
    }
    .transcript-turn .who .ts {
        display: block;
        color: var(--muted);
        font-size: 0.7rem;
        margin-top: 2px;
    }
    .transcript-turn .said {
        font-family: 'Zilla Slab', serif;
        font-size: 1rem;
        line-height: 1.5;
        color: var(--paper);
    }
    .transcript-turn mark {
        background: var(--amber-soft);
        color: var(--paper);
        padding: 0 2px;
        border-radius: 2px;
    }
    .transcript-empty {
        text-align: center;
        color: var(--muted);
        padding: 40px 0;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.85rem;
    }

    /* ---------- Colophon ---------- */
    .colophon {
        margin-top: 40px;
        padding-top: 10px;
        border-top: 1px solid var(--rule);
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.7rem;
        color: var(--muted);
        letter-spacing: 0.5px;
        text-align: center;
    }

    /* ---------- Empty state ---------- */
    .empty-state {
        border: 1px dashed var(--rule);
        border-radius: 8px;
        padding: 48px 32px;
        text-align: center;
        margin-top: 20px;
    }
    .empty-state .glyph {
        font-size: 2.4rem;
        color: var(--amber);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- MASTHEAD ---
st.markdown(
    """
    <div class="desk-masthead">
        <div>
            <div class="kicker">Human-in-the-loop review</div>
            <h1>The Meeting Desk</h1>
        </div>
        <div class="dateline">AI proofs the transcript.<br>You approve what goes to print.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- PERSISTENT STATE ---
if "run_id" not in st.session_state:
    st.session_state.run_id = None
if "meeting_data" not in st.session_state:
    st.session_state.meeting_data = None
if "transcript_preview" not in st.session_state:
    st.session_state.transcript_preview = None
if "transcript_preview_error" not in st.session_state:
    st.session_state.transcript_preview_error = None

# --- STEP 1: UPLOAD TRANSCRIPT ---
st.sidebar.markdown("### New submission")
upload_option = st.sidebar.radio(
    "How is the transcript arriving?", ["Upload File", "Paste File Path"], label_visibility="visible"
)

payload = {
    "transcript_path": "",
    "transcript": {},
    "audience_role": "general",
    "force_continue": False,
}

pending_transcript_preview = None
pending_transcript_preview_error = None

if upload_option == "Upload File":
    uploaded_file = st.sidebar.file_uploader("Transcript JSON", type=["json"])
    if uploaded_file is not None:
        try:
            payload["transcript"] = json.load(uploaded_file)
            pending_transcript_preview = payload["transcript"]
        except Exception as e:
            st.sidebar.error(f"Invalid JSON: {e}")
else:
    file_path = st.sidebar.text_input(
        "Local file path", value="data/sample_transcripts/sprint_sync_001.json"
    )
    payload["transcript_path"] = file_path
    try:
        with open(file_path, "r") as f:
            pending_transcript_preview = json.load(f)
    except Exception as e:
        pending_transcript_preview_error = f"Preview unavailable ({e}). It may only be readable by the server."

role = st.sidebar.selectbox("Written for", ["general", "internal", "executive"])
payload["audience_role"] = role

if st.sidebar.button("Send to the desk →", use_container_width=True, type="primary"):
    with st.spinner("Reading the transcript and flagging anything uncertain…"):
        try:
            response = requests.post(f"{FASTAPI_URL}/meetings", json=payload)
            if response.status_code == 200:
                res_data = response.json()
                st.session_state.run_id = res_data.get("run_id")
                st.session_state.meeting_data = res_data
                st.session_state.transcript_preview = pending_transcript_preview
                st.session_state.transcript_preview_error = pending_transcript_preview_error
                st.sidebar.success("Run started.")
            else:
                st.sidebar.error(f"Couldn't start the run: {response.status_code} — {response.text}")
        except Exception as e:
            st.sidebar.error(f"Couldn't reach the server: {e}")

st.sidebar.markdown(
    '<div class="colophon">THE MEETING DESK · v2<br>proofed by human eyes</div>',
    unsafe_allow_html=True,
)


# --- HELPER FUNCTION: RE-FETCH MEETING STATE ---
def fetch_latest_state():
    if st.session_state.run_id:
        try:
            res = requests.get(f"{FASTAPI_URL}/meetings/{st.session_state.run_id}")
            if res.status_code == 200:
                st.session_state.meeting_data = res.json()
        except Exception as e:
            st.error(f"Couldn't refresh the run: {e}")


def extract_turns(transcript_json):
    """Best-effort normalization of an arbitrary transcript JSON shape into
    a flat list of {speaker, timestamp, text} dicts. Returns None if no
    recognizable list of turns is found."""
    if not isinstance(transcript_json, dict):
        if isinstance(transcript_json, list):
            candidate = transcript_json
        else:
            return None
    else:
        candidate = None
        for key in ("turns", "segments", "utterances", "lines", "transcript", "messages"):
            val = transcript_json.get(key)
            if isinstance(val, list) and val:
                candidate = val
                break
        if candidate is None:
            return None

    turns = []
    for item in candidate:
        if not isinstance(item, dict):
            return None
        speaker = item.get("speaker") or item.get("name") or item.get("role") or "Unknown"
        timestamp = item.get("timestamp") or item.get("time") or item.get("ts") or ""
        text = (
            item.get("text")
            or item.get("utterance")
            or item.get("content")
            or item.get("excerpt")
            or item.get("line")
            or ""
        )
        turns.append({"speaker": speaker, "timestamp": timestamp, "text": text})
    return turns if turns else None


def render_stepper(stage_index: int, labels):
    """stage_index: 0-based index of the current (active) stage."""
    parts = ['<div class="stepper">']
    for i, label in enumerate(labels):
        if i < stage_index:
            dot_cls, label_cls = "done", "done"
            dot_content = "✓"
        elif i == stage_index:
            dot_cls, label_cls = "active", "active"
            dot_content = str(i + 1)
        else:
            dot_cls, label_cls = "", ""
            dot_content = str(i + 1)
        parts.append(
            f'<div class="step"><div class="step-dot {dot_cls}">{dot_content}</div>'
            f'<div class="step-label {label_cls}">{label}</div></div>'
        )
        if i < len(labels) - 1:
            line_cls = "done" if i < stage_index else ""
            parts.append(f'<div class="step-line {line_cls}"></div>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


# --- MAIN CONTENT INTERFACE ---
if st.session_state.run_id and st.session_state.meeting_data:
    run_id = st.session_state.run_id
    data = st.session_state.meeting_data
    record = data.get("record", {})
    status = record.get("status", "unknown")

    pending_items_all = [item for item in record.get("review_queue", []) if item.get("human_action") is None]
    pending_count = len(pending_items_all)
    total_items = len(record.get("review_queue", []))
    is_finalized = status == "completed" or (
        not data.get("paused_for_review") and record.get("summary") and status != "paused_for_review"
    )

    if is_finalized:
        stage_index = 3
    elif pending_count == 0 and total_items > 0:
        stage_index = 2  # review complete, awaiting finalization
    else:
        stage_index = 2 if total_items > 0 else 1

    render_stepper(stage_index, ["Ingested", "Extraction", "Human review", "Finalized"])

    top_l, top_r = st.columns([3, 1])
    with top_l:
        st.markdown(
            f'<span class="proof-slip"><span class="item-id">RUN {run_id}</span></span>',
            unsafe_allow_html=True,
        )
    with top_r:
        st.caption(f"Status: **{status.upper()}**")

    col1, col2 = st.columns([1.5, 1])

    # ------------------ LEFT COLUMN: THE REVIEW QUEUE ------------------
    with col1:
        st.header("Review queue")

        m1, m2 = st.columns(2)
        m1.metric(label="Awaiting your read", value=pending_count)
        m2.metric(label="Total flagged", value=total_items)
        if total_items > 0:
            st.progress((total_items - pending_count) / total_items)

        if pending_count > 0:
            st.caption("The AI wasn't confident about these. Read each, edit if needed, then approve or reject.")

            for idx, item in enumerate(pending_items_all):
                item_id = item["id"]
                item_type = item["item_type"]
                payload_data = item["payload"]
                reason = item["reason"]

                with st.container(border=True):
                    st.markdown(
                        f'<div class="proof-slip">'
                        f'<span class="tag">{item_type.replace("_", " ").upper()}</span> '
                        f'<span class="item-id">{item_id}</span>'
                        f'<div class="reason">Flagged — {reason}</div>'
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    st.write("")

                    if item_type == "action_item":
                        task = st.text_area(
                            "Task", value=payload_data.get("task", ""), key=f"task_{item_id}"
                        )
                        owner = st.text_input(
                            "Owner",
                            value=payload_data.get("owner", "") or "",
                            placeholder="Who owns this?",
                            key=f"owner_{item_id}",
                        )
                        due_date = st.text_input(
                            "Due",
                            value=payload_data.get("due_date", "") or "",
                            placeholder="e.g. Friday",
                            key=f"due_{item_id}",
                        )

                        edited_payload = {
                            "id": item_id,
                            "task": task,
                            "owner": owner if owner else None,
                            "due_date": due_date if due_date else None,
                        }
                    else:
                        desc = st.text_area(
                            "Description",
                            value=payload_data.get("description", payload_data.get("topic", "")),
                            key=f"desc_{item_id}",
                        )
                        edited_payload = {"id": item_id, "description": desc}

                    if payload_data.get("source_refs"):
                        with st.expander("Show transcript context"):
                            for ref in payload_data["source_refs"]:
                                st.markdown(
                                    f'<span class="item-id">{ref["speaker"]} · {ref["timestamp"]}</span><br>'
                                    f'<em>"{ref["excerpt"]}"</em>',
                                    unsafe_allow_html=True,
                                )

                    is_last = idx == pending_count - 1
                    force_continue_value = False

                    if is_last:
                        st.warning("Last item — approving this sends the run to final assembly.")
                        force_continue_value = True

                    btn_col1, btn_col2 = st.columns(2)

                    with btn_col1:
                        if st.button(
                            "Approve",
                            key=f"app_{item_id}",
                            use_container_width=True,
                            type="primary",
                        ):
                            review_body = {
                                "action": "edit" if item_type == "action_item" else "approve",
                                "edited_payload": edited_payload if item_type == "action_item" else None,
                                "force_continue": force_continue_value,
                            }
                            res = requests.post(
                                f"{FASTAPI_URL}/meetings/{run_id}/items/{item_id}/review",
                                json=review_body,
                            )
                            if res.status_code == 200:
                                st.session_state.meeting_data = res.json()
                                st.toast(f"Approved {item_id}")
                                st.rerun()
                            else:
                                st.error(f"Couldn't save: {res.text}")

                    with btn_col2:
                        if st.button(
                            "Reject",
                            key=f"rej_{item_id}",
                            use_container_width=True,
                            type="secondary",
                        ):
                            review_body = {
                                "action": "reject",
                                "edited_payload": None,
                                "force_continue": force_continue_value,
                            }
                            res = requests.post(
                                f"{FASTAPI_URL}/meetings/{run_id}/items/{item_id}/review",
                                json=review_body,
                            )
                            if res.status_code == 200:
                                st.session_state.meeting_data = res.json()
                                st.toast(f"Rejected {item_id}")
                                st.rerun()
                            else:
                                st.error(f"Couldn't save: {res.text}")
        else:
            st.success("Every flagged item has been read. Human review is complete.")
            if status != "completed" and data.get("paused_for_review"):
                if st.button("Finish the run →", type="primary"):
                    res = requests.post(
                        f"{FASTAPI_URL}/meetings/{run_id}/items/_force/review",
                        json={"action": "approve", "force_continue": True},
                    )
                    if res.status_code == 200:
                        st.session_state.meeting_data = res.json()
                    else:
                        fetch_latest_state()
                    st.rerun()

    # ------------------ RIGHT COLUMN: THE LEDGER ------------------
    with col2:
        st.header("The ledger")

        with st.expander("Meeting info", expanded=True):
            st.markdown(f"**Title** — {record.get('title', 'Unknown')}")
            st.markdown(f"**Date** — {record.get('date', 'Unknown')}")
            st.markdown(
                f'**Meeting ID** — <span class="item-id">{record.get("meeting_id", "Unknown")}</span>',
                unsafe_allow_html=True,
            )

        decisions = record.get("decisions", [])
        if decisions:
            with st.expander(f"Decisions ({len(decisions)})"):
                for d in decisions:
                    st.markdown(
                        f"**{d.get('description')}**  \n"
                        f"decided by *{d.get('decided_by')}* · status `{d.get('status')}`"
                    )
                    st.markdown("---")

        actions = record.get("action_items", [])
        if actions:
            with st.expander(f"Action items ({len(actions)})"):
                for a in actions:
                    st.markdown(
                        f"**{a.get('task')}**  \n"
                        f"owner `{a.get('owner')}` · due `{a.get('due_date')}` · status `{a.get('status')}`"
                    )
                    st.markdown("---")

        blockers = record.get("blockers", [])
        if blockers:
            with st.expander(f"Blockers ({len(blockers)})"):
                for b in blockers:
                    st.markdown(f"**{b.get('description')}**  \nblocking *{b.get('blocking')}*")
                    st.markdown("---")

        if is_finalized:
            st.success("Final deliverables are ready.")
            paths = data.get("handback_paths") or []
            if paths:
                st.markdown("**Generated files**")
                for p in paths:
                    st.code(p)

    # ------------------ FULL TRANSCRIPT ------------------
    st.divider()
    with st.expander("📖 Read the full transcript", expanded=False):
        preview = st.session_state.transcript_preview
        preview_error = st.session_state.transcript_preview_error

        if preview_error and not preview:
            st.warning(preview_error)
        elif not preview:
            st.markdown('<div class="transcript-empty">No transcript preview available for this run.</div>', unsafe_allow_html=True)
        else:
            turns = extract_turns(preview)
            if turns:
                query = st.text_input(
                    "Find in transcript", placeholder="Search by speaker or keyword…", key="transcript_search"
                )
                q = query.strip().lower()

                def highlight(text):
                    if not q:
                        return text
                    idx = text.lower().find(q)
                    if idx == -1:
                        return text
                    return text[:idx] + f"<mark>{text[idx:idx+len(q)]}</mark>" + text[idx + len(q):]

                shown = 0
                for t in turns:
                    haystack = f"{t['speaker']} {t['text']}".lower()
                    if q and q not in haystack:
                        continue
                    shown += 1
                    st.markdown(
                        f'<div class="transcript-turn">'
                        f'<div class="who">{t["speaker"]}<span class="ts">{t["timestamp"]}</span></div>'
                        f'<div class="said">{highlight(t["text"])}</div>'
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                if shown == 0:
                    st.markdown('<div class="transcript-empty">No lines match that search.</div>', unsafe_allow_html=True)
            else:
                st.caption("Couldn't identify individual speaker turns — showing the raw file instead.")
                st.json(preview)

else:
    st.markdown(
        """
        <div class="empty-state">
            <div class="glyph">🖋️</div>
            <h3>Nothing on the desk yet</h3>
            <p style="color: var(--muted);">
                Upload a transcript or point to a file path in the sidebar to start a run.
                The AI will read it, flag anything it isn't sure of, and hand those items to you here.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )