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
# BEDROCK CONFIGURATION
# =============================================================================

# Model ID for Bedrock
# BEDROCK_MODEL = "us.anthropic.claude-opus-4-1-20250805-v1:0"  # Use for final test runs
# BEDROCK_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"  # Faster for testing
BEDROCK_MODEL = "global.anthropic.claude-opus-4-5-20251101-v1:0"  # Global model

# Environment variables for Bedrock (set before running)
BEDROCK_ENV = {
    "CLAUDE_CODE_USE_BEDROCK": "1",
    # AWS credentials should already be configured in your environment
    # "AWS_REGION": "us-east-1",  # Uncomment if needed
    # "AWS_PROFILE": "your-profile",  # Uncomment if needed
}

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