# TODO: Agent 5 — Critic
# Model: Groq Llama 3.3 70B
# Input:  patch, plan, sandbox_result, retry_count
# Output: critic_scores {quality, coverage, security, overall}
# Logic:  overall > 0.8 → pass | retry_count < 4 → retry | else → give_up
