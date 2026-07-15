import streamlit as st
import requests
import json

# --- CONFIGURATION ---
FASTAPI_URL = "http://localhost:8000"

st.set_page_config(page_title="AI Meeting Assistant Portal", layout="wide", page_icon="🤖")
st.title("🤖 AI Meeting Assistant Portal")
st.caption("Upload meeting transcripts, review AI extractions, and generate final summaries.")

# --- PERSISTENT STATE ---
if "run_id" not in st.session_state:
    st.session_state.run_id = None
if "meeting_data" not in st.session_state:
    st.session_state.meeting_data = None

# --- STEP 1: UPLOAD TRANSCRIPT ---
st.sidebar.header("📁 Step 1: Ingest Meeting")
upload_option = st.sidebar.radio("Choose Input Method:", ["Upload File", "Paste File Path"])

payload = {
    "transcript_path": "",
    "transcript": {},
    "audience_role": "general",
    "force_continue": False
}

if upload_option == "Upload File":
    uploaded_file = st.sidebar.file_uploader("Upload Transcript JSON", type=["json"])
    if uploaded_file is not None:
        try:
            payload["transcript"] = json.load(uploaded_file)
        except Exception as e:
            st.sidebar.error(f"Invalid JSON: {e}")
else:
    file_path = st.sidebar.text_input("Local File Path", value="data/sample_transcripts/sprint_sync_001.json")
    payload["transcript_path"] = file_path

role = st.sidebar.selectbox("Audience Role", ["general", "internal", "executive"])
payload["audience_role"] = role

if st.sidebar.button("🚀 Process & Start Run", use_container_width=True):
    with st.spinner("AI is analyzing the transcript..."):
        try:
            response = requests.post(f"{FASTAPI_URL}/meetings", json=payload)
            if response.status_code == 200:
                res_data = response.json()
                st.session_state.run_id = res_data.get("run_id")
                st.session_state.meeting_data = res_data
                st.sidebar.success(f"Run started successfully!")
            else:
                st.sidebar.error(f"Error starting run: {response.status_code} - {response.text}")
        except Exception as e:
            st.sidebar.error(f"Could not connect to FastAPI server: {e}")

# --- HELPER FUNCTION: RE-FETCH MEETING STATE ---
def fetch_latest_state():
    if st.session_state.run_id:
        try:
            res = requests.get(f"{FASTAPI_URL}/meetings/{st.session_state.run_id}")
            if res.status_code == 200:
                st.session_state.meeting_data = res.json()
        except Exception as e:
            st.error(f"Error updating state: {e}")

# --- MAIN CONTENT INTERFACE ---
if st.session_state.run_id and st.session_state.meeting_data:
    run_id = st.session_state.run_id
    data = st.session_state.meeting_data
    record = data.get("record", {})
    status = record.get("status", "unknown")
    
    st.info(f"🧬 **Active Run ID:** `{run_id}` | Status: **{status.upper()}**")

    # Split screen: Left for Review Queue, Right for general details/summary
    col1, col2 = st.columns([1.5, 1])

    # ------------------ LEFT COLUMN: THE REVIEW QUEUE ------------------
    with col1:
        st.header("🔍 Human-in-the-Loop Review Queue")
        
        pending_items = [item for item in record.get("review_queue", []) if item.get("human_action") is None]
        pending_count = len(pending_items)
        st.metric(label="Items Pending Human Review", value=pending_count)

        if pending_count > 0:
            st.write("Please review the following low-confidence items extracted by the AI:")
            
            # Loop through only the pending items
            for idx, item in enumerate(pending_items):
                item_id = item["id"]
                item_type = item["item_type"]
                payload_data = item["payload"]
                reason = item["reason"]
                
                # Render an interactive visual card
                with st.container(border=True):
                    st.subheader(f"🏷️ {item_type.replace('_', ' ').title()} - `{item_id}`")
                    st.caption(f"**Flagged Reason:** {reason.upper()}")
                    
                    # Custom input fields based on item type
                    if item_type == "action_item":
                        task = st.text_area("Task Description", value=payload_data.get("task", ""), key=f"task_{item_id}")
                        owner = st.text_input("Owner", value=payload_data.get("owner", "") or "", placeholder="Enter owner's name", key=f"owner_{item_id}")
                        due_date = st.text_input("Due Date", value=payload_data.get("due_date", "") or "", placeholder="e.g. Friday", key=f"due_{item_id}")
                        
                        edited_payload = {
                            "id": item_id,
                            "task": task,
                            "owner": owner if owner else None,
                            "due_date": due_date if due_date else None,
                        }
                    else:
                        # For general escalations / followups
                        desc = st.text_area("Description / Topic", value=payload_data.get("description", payload_data.get("topic", "")), key=f"desc_{item_id}")
                        edited_payload = {
                            "id": item_id,
                            "description": desc
                        }

                    # Show Transcript Excerpt for Context
                    if payload_data.get("source_refs"):
                        with st.expander("👁️ Show original transcript context"):
                            for ref in payload_data["source_refs"]:
                                st.markdown(f"**{ref['speaker']}** ({ref['timestamp']}): *\"{ref['excerpt']}\"*")

                    # Review Actions
                    btn_col1, btn_col2 = st.columns(2)
                    
                    # Is this the very last item in the queue?
                    is_last = (idx == pending_count - 1)
                    force_continue_value = False
                    
                    if is_last:
                        st.warning("⚠️ This is the last item. Approving this will trigger final document generation!")
                        force_continue_value = True

                    with btn_col1:
                        if st.button("🟢 Approve & Save", key=f"app_{item_id}", use_container_width=True):
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
                                st.toast(f"Approved {item_id}!")
                                st.rerun()
                            else:
                                st.error(f"Error: {res.text}")

                    with btn_col2:
                        if st.button("🔴 Reject & Delete", key=f"rej_{item_id}", use_container_width=True):
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
                                st.toast(f"Rejected {item_id}!")
                                st.rerun()
                            else:
                                st.error(f"Error: {res.text}")
        else:
            st.success("🎉 All items have been reviewed! Human-in-the-loop stage completed.")
            if status != "completed" and data.get("paused_for_review"):
                if st.button("⚡ Force Finish Pipeline", type="primary"):
                    res = requests.post(
                        f"{FASTAPI_URL}/meetings/{run_id}/items/_force/review",
                        json={"action": "approve", "force_continue": True},
                    )
                    if res.status_code == 200:
                        st.session_state.meeting_data = res.json()
                    else:
                        fetch_latest_state()
                    st.rerun()

    # ------------------ RIGHT COLUMN: AUTO-APPROVED & RESULTS ------------------
    with col2:
        st.header("📋 Meeting Status Summary")
        
        with st.expander("📊 Meeting Info", expanded=True):
            st.markdown(f"**Title:** {record.get('title', 'Unknown')}")
            st.markdown(f"**Date:** {record.get('date', 'Unknown')}")
            st.markdown(f"**Meeting ID:** {record.get('meeting_id', 'Unknown')}")
        
        decisions = record.get("decisions", [])
        if decisions:
            with st.expander(f"✅ Decisions ({len(decisions)})"):
                for d in decisions:
                    st.markdown(
                        f"* **{d.get('description')}** "
                        f"(by *{d.get('decided_by')}*, status=`{d.get('status')}`)"
                    )

        actions = record.get("action_items", [])
        if actions:
            with st.expander(f"📌 Action items ({len(actions)})"):
                for a in actions:
                    st.markdown(
                        f"* **{a.get('task')}** — owner=`{a.get('owner')}` "
                        f"due=`{a.get('due_date')}` status=`{a.get('status')}`"
                    )

        blockers = record.get("blockers", [])
        if blockers:
            with st.expander(f"⚠️ Blockers ({len(blockers)})"):
                for b in blockers:
                    st.markdown(
                        f"* **{b.get('description')}** (Blocking: *{b.get('blocking')}*)"
                    )

        if status == "completed" or (
            not data.get("paused_for_review") and record.get("summary")
            and record.get("status") != "paused_for_review"
        ):
            st.success("✨ Final deliverables generated! Check your `artifacts/runs` folder.")
            paths = data.get("handback_paths") or []
            if paths:
                st.markdown("### 📥 Generated files")
                for p in paths:
                    st.code(p)
else:
    st.info("👈 Please start a run or paste a meeting path in the sidebar to load the dashboard.")