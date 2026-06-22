from engine.orchestrator import Orchestrator

def main():
    orch = Orchestrator()

    result = orch.step(
        user_input="Hello, test",
        session_id="debug",
    )

    print(result)

if __name__ == "__main__":
    main()
