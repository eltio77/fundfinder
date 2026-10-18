import os

# Tests never touch Atlas; give settings a syntactically valid, unreachable URI.
os.environ.setdefault("MONGODB_URI", "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=100")
