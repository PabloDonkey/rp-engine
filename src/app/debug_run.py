from llm.client import LMStudioClient
from memory.session import SessionMemory
from engine.orchestrator import Orchestrator

def main():
    print("\n=== RP ENGINE DEBUG START ===\n")

        # 1. Setup components
    llm = LMStudioClient(api_url="http://127.0.0.1:1234/v1")
    session = SessionMemory(session_id="debug-session")

    orch = Orchestrator(
        llm_client=llm,
        session=session,
        model="qwen/qwen2.5-coder-14b",
    )

# 2. Run test loop
    while True:
        user_input = input("\nYou: ")

        if user_input in {"exit", "quit"}:
            break

        print("\n--- STEP ---")
        response = orch.step(user_input)
        print("\nAssistant:", response)

        print("\n[SESSION]")
        print(orch.get_session_summary())


if __name__ == "__main__":
    main()
