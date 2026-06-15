# TODO: Memory Retrieval (runs before code_reader)
# Model: sentence-transformers all-MiniLM-L6-v2 (local)
# Input:  issue_title, issue_body
# Output: memory_lessons [list of lesson strings], memory_matches (int)
# Steps:  embed issue → query ChromaDB → return top 3 similar failures
