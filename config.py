"""
config.py - Configuration for Evoq test generation pipeline
"""

from pathlib import Path
import os

# =============================================================================
# PATH CONFIGURATION
# =============================================================================

BASE_DIR = Path(__file__).parent
REPOS_BASE_PATH = BASE_DIR / "repos"  # Adjust to your repos location
# REPOS_BASE_PATH = Path("C:/DNN")

# Input/Output
INPUT_CSV = BASE_DIR / "evoq_extensions.csv"
OUTPUT_TESTS_DIR = BASE_DIR / "generated_tests"
TRACKING_CSV = BASE_DIR / "test_tracking.csv"

# =============================================================================
# CSV COLUMN NAMES (adjust to match your actual CSV headers)
# =============================================================================

COL_REPO = "Repository"
COL_EXTENSION = "Extension Name"
COL_PRIORITY = "Priority for E2E Testing"
COL_WORKS_V9 = "Works in Evoq 9?"
COL_DECISION = "Decision for Evoq 10"

# =============================================================================
# REPOSITORY PATH MAPPING
# =============================================================================

REPO_PATHS = {
    # Core repos
    "Evoq.Dnn.Platform": REPOS_BASE_PATH / "Evoq.Dnn.Platform",
    "Dnn.Evoq.Basic": REPOS_BASE_PATH / "Dnn.Evoq.Basic",
    "Dnn.Evoq.Content": REPOS_BASE_PATH / "Dnn.Evoq.Content",
    "Dnn.Evoq.Social": REPOS_BASE_PATH / "Dnn.Evoq.Social",
    
    # Admin Experience repos
    "Dnn.AdminExperience.Evoq.Basic": REPOS_BASE_PATH / "Dnn.AdminExperience.Evoq.Basic",
    "Dnn.AdminExperience.Evoq.Engage": REPOS_BASE_PATH / "Dnn.AdminExperience.Evoq.Engage",
    
    # Add more repos as needed
}

# =============================================================================
# CLAUDE PROVIDER CONFIGURATION
# =============================================================================
# 
# Available providers:
#   "bedrock"  - AWS Bedrock (requires AWS credentials configured in environment)
#   "api_key"  - Anthropic API Key (requires ANTHROPIC_API_KEY env var)
#   "console"  - Anthropic Console login (run `claude /login` before starting tester)
#
# To use "console" provider:
#   1. Run `claude /login` in your terminal first
#   2. Complete the browser-based authentication
#   3. Then run the tester
#
PROVIDER = "console"  # Change this to switch providers

# -----------------------------------------------------------------------------
# Model names per provider (Bedrock uses different naming than Anthropic direct)
# -----------------------------------------------------------------------------
MODELS = {
    "bedrock": {
        "primary": "global.anthropic.claude-opus-4-5-20251101-v1:0",
        "fast": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    },
    "api_key": {
        "primary": "claude-opus-4-5-20251101",
        "fast": "claude-sonnet-4-5-20250929",
    },
    "console": {
        "primary": "claude-opus-4-5-20251101",
        "fast": "claude-sonnet-4-5-20250929",
    },
}

# -----------------------------------------------------------------------------
# Auto-configured based on PROVIDER selection
# -----------------------------------------------------------------------------
def _get_provider_env() -> dict:
    """Returns environment variables required for the selected provider."""
    if PROVIDER == "bedrock":
        return {"CLAUDE_CODE_USE_BEDROCK": "1"}
    elif PROVIDER == "api_key":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is required when using 'api_key' provider.\n"
                "Set it with: export ANTHROPIC_API_KEY='your-key-here'"
            )
        return {}  # API key is read from env automatically by claude CLI
    elif PROVIDER == "console":
        # Console provider uses interactive login - no env vars needed
        # User must run `claude /login` before starting
        return {}
    else:
        raise ValueError(f"Unknown PROVIDER: {PROVIDER}. Use 'bedrock', 'api_key', or 'console'")


# Exported config values (used by tester.py)
CLAUDE_MODEL = MODELS[PROVIDER]["primary"]
CLAUDE_ENV = _get_provider_env()

# Legacy aliases for backwards compatibility
BEDROCK_MODEL = CLAUDE_MODEL
BEDROCK_ENV = CLAUDE_ENV

# =============================================================================
# CLAUDE CODE SETTINGS
# =============================================================================

# Timeout per extension (in seconds)
CLAUDE_TIMEOUT = 1800  # 15 minutes for thorough analysis with ULTRATHINK

# Maximum conversation turns
CLAUDE_MAX_TURNS = 300

# Tools allowed for test generation (read-only for safety)
ALLOWED_TOOLS = [
    "Read",
    "Grep", 
    "Glob",
    "Bash(find:*)",
    "Bash(ls:*)",
    "Bash(cat:*)",
    "Bash(head:*)",
    "Bash(tail:*)",
    "Bash(wc:*)",
]

# Delay between runs (seconds) - prevents rate limiting
DELAY_BETWEEN_RUNS = 3

# The folder containing all repos - Claude will run from here
REPOS_WORKING_DIR = REPOS_BASE_PATH  # This is repos/ folder