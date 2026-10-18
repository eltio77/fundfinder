import os

# Tests never touch Atlas; give settings a syntactically valid, unreachable URI.
os.environ.setdefault("MONGODB_URI", "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=100")
# Never call a real LLM from tests, even if .env has a key (env beats .env).
os.environ["ANTHROPIC_API_KEY"] = ""
