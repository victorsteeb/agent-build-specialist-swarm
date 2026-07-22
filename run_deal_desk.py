"""
Run the Deal Desk swarm against the synthetic RFP.

Inlines the RFP + past-wins + product-overview into the user message (simpler
than Files API for hackathon-scale content). Streams events as they come in so
you can watch the parallel thread fan-out — this is the demo, narrate it live.

Saves the final transcript to outputs/.

Usage:
    python run_deal_desk.py
"""

import time
from pathlib import Path

from _common import create_session_or_explain, drive_session, get_client, read_id

RFP_PATH = Path("synthetic-data/rfp-acme-corp.md")
# product-overview.md is no longer inlined — it ships to the Technical Fit
# specialist as the technical-fit skill (see skills/technical-fit/).
SUPPORTING_FILES = [
    Path("synthetic-data/past-wins.json"),
]
OUTPUT_DIR = Path("outputs")


def load_inputs_as_context() -> str:
    blocks = []
    for path in [RFP_PATH, *SUPPORTING_FILES]:
        if not path.exists():
            print(f"  WARNING: {path} missing — skipping")
            continue
        print(f"  including {path.name}")
        blocks.append(f"=====  DOCUMENT: {path.name}  =====\n{path.read_text()}")
    return "\n\n".join(blocks)


def main() -> None:
    client = get_client()

    order_hint = (
        "Run, in order: setup_environment.py, create_specialists.py, "
        "upload_skills.py, create_coordinator.py."
    )
    coordinator_id = read_id(".coordinator_id", order_hint)
    environment_id = read_id(".environment_id", order_hint)

    print("Loading RFP + supporting docs...")
    context = load_inputs_as_context()

    print(f"\nStarting session against coordinator {coordinator_id}...")
    session = create_session_or_explain(
        client,
        [".coordinator_id", ".environment_id"],
        agent=coordinator_id,
        environment_id=environment_id,
        title="Deal Desk — Acme Corp RFP",
    )
    Path(".last_session_id").write_text(session.id)

    user_message = (
        "An RFP has just landed. Please run the standard Deal Desk process:\n"
        "1. Read the RFP yourself.\n"
        "2. Delegate to all four specialists in parallel.\n"
        "3. Synthesise their replies.\n"
        "4. Produce the final proposal response as a branded Word document "
        "using your docx skill, and save it to "
        "/mnt/session/outputs/proposal-response.docx — files saved anywhere "
        "else cannot be retrieved after the session.\n\n"
        "Specialists have their own skills attached for their respective "
        "domains. Move fast — the RFP deadline is real.\n\n"
        f"{context}"
    )

    # Stream the events — this is the demo. Watch for parallel thread spawns.
    print("\n=== EVENT STREAM (this is the demo) ===\n")
    final_text_parts: list = []

    def on_event(event):
        t = event.type
        if t == "session.thread_created":
            print(f"  [thread spawned]   {event.agent_name}", flush=True)
        elif t == "session.thread_status_running":
            print(f"  [thread running]   {getattr(event, 'agent_name', '?')}", flush=True)
        elif t == "agent.thread_message_received":
            print(f"  [reply ←]          {event.from_agent_name}", flush=True)
        elif t == "agent.thread_message_sent":
            print(f"  [delegate →]       {event.to_agent_name}", flush=True)
        elif t == "agent.message":
            for block in event.content:
                if getattr(block, "type", None) == "text":
                    final_text_parts.append(block.text)
                    print(block.text, end="", flush=True)
        elif t == "agent.tool_use":
            print(f"\n  [tool: {getattr(event, 'name', '?')}]", flush=True)

    drive_session(
        client,
        session,
        kickoff_events=[
            {
                "type": "user.message",
                "content": [{"type": "text", "text": user_message}],
            }
        ],
        on_event=on_event,
        timeout_s=600,
    )
    print("\n\n[swarm finished]")

    OUTPUT_DIR.mkdir(exist_ok=True)
    transcript_path = OUTPUT_DIR / "coordinator-transcript.txt"
    transcript_path.write_text("".join(final_text_parts))
    print(f"\nCoordinator transcript saved to {transcript_path}")

    # Pull every file the agents produced in the container.
    # Outputs land in /mnt/session/outputs/ and take a few seconds to index
    # after the session goes idle — retry a few times before giving up.
    print("\nDownloading deliverables from the session container...")
    file_count = 0
    for attempt in range(4):
        if attempt:
            time.sleep(3)
        file_count = 0
        for f in client.beta.files.list(
            scope_id=session.id,
            betas=["managed-agents-2026-04-01"],
        ):
            out_path = OUTPUT_DIR / f.filename
            print(f"  {f.filename}  ->  {out_path}")
            content = client.beta.files.download(f.id)
            content.write_to_file(str(out_path))
            file_count += 1
        if file_count:
            break
        print("  (nothing indexed yet — retrying...)")

    if file_count == 0:
        print("  (no files found — did the coordinator save to /mnt/session/outputs/?)")
        print("  Re-check later with:  python download_deliverable.py")
    else:
        print(f"\nDownloaded {file_count} file(s) to {OUTPUT_DIR}/")
        print("\nNext: grade it —  python check_deliverable.py")
        print("  (checks the docx against the Great-when bar; no API call, ~2s)")

    from _common import console_url
    print(f"\nView the full session (including all sub-agent threads) at:")
    print(f"  {console_url(session.id)}")


if __name__ == "__main__":
    main()
