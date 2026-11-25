pyinstaller --onefile --name agent --add-data "agent\knowledge;agent\knowledge" --collect-all langgraph --collect-all langchain_openai run_agent.py
