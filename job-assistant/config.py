import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# 使用 litellm 格式，CrewAI v1.x 要求
SONNET = "anthropic/claude-sonnet-4-5"
HAIKU = "anthropic/claude-haiku-4-5-20251001"

OUTPUT_DIR = "output"
