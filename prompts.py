"""
prompts.py - Prompt templates for Evoq test generation pipeline
"""

import os
from pathlib import Path
from typing import Optional, List


def get_priority_guidance(priority: str) -> str:
    """Get feature extraction guidance based on extension priority level."""
    priority_guidance = {
        "Top": """CRITICAL extension with the most customer issues. Extract EVERY capability:
  - All features, sub-features, and minor functionality
  - Every configuration option and setting
  - All edge case scenarios (empty states, max limits, special characters, permissions)
  - Error handling paths and validation rules
  - All CRUD operations for every entity
  - Integration points with other modules
  - Admin AND user-facing functionality separately
  (No ceiling - be as exhaustive as possible)""",
        
        "High": """Important extension requiring thorough extraction:
  - All main features and significant sub-features
  - Configuration options and settings
  - Common edge cases (empty states, validation)
  - Error scenarios for critical paths
  - All CRUD operations
  - Both admin and user-facing functionality
  DO NOT: Extract every minor sub-feature or obscure configuration. Focus on significant functionality.""",
        
        "Medium": """Standard extension - extract core functionality:
  - All primary features
  - Key configuration options
  - Main happy-path scenarios
  - Basic validation and error cases
  - Primary CRUD operations
  DO NOT: Extract edge case scenarios, permission variations, integration points, or minor sub-features. Those are for High/Top priority.""",
        
        "Low": """Lower priority - extract main features only:
  - Primary features that define the extension's purpose
  - Basic functionality verification
  - Core happy-path scenarios
  DO NOT: Extract configuration options, error scenarios, edge cases, or sub-features. Keep it to the essentials.""",
        
        "N/A": """Minimal extraction - likely covered by other extensions:
  - Only extract if there's unique, standalone functionality
  - Focus on any features NOT covered elsewhere
  DO NOT: Duplicate features covered by other extensions. Skip if nothing unique."""
    }
    return priority_guidance.get(priority, priority_guidance["Medium"])


def get_feature_test_depth_guidance(priority: str) -> str:
    """Get testing depth guidance based on feature priority level."""
    test_depth_guidance = {
        "Top": """EXHAUSTIVE testing required:
  - Test EVERY scenario listed plus any you discover
  - Test all edge cases: empty inputs, maximum lengths, special characters, boundary values
  - Test error paths: what happens when things go wrong? Invalid input? Network issues?
  - Test negative scenarios: unauthorized access, missing permissions, disabled states
  - Test all CRUD operations if applicable (Create, Read, Update, Delete)
  - Test with different data states: empty list, single item, many items
  - Verify all validation messages and error feedback
  - Test any keyboard shortcuts or alternative interaction methods
  (No ceiling - test everything you can think of)""",
        
        "High": """THOROUGH testing required:
  - Test all listed scenarios
  - Test common edge cases: empty inputs, validation errors, boundary values
  - Test primary error paths and how errors are displayed
  - Test all CRUD operations if applicable
  - Verify key validation messages
  - Test with at least empty and populated data states
  DO NOT: Test every possible edge case, permission variation, or alternative method. That's for Top priority.""",
        
        "Medium": """STANDARD testing required:
  - Test all listed scenarios (happy paths)
  - Test basic validation: required fields, format validation
  - Test at least one error scenario
  - Test primary CRUD operations if applicable
  - Verify the feature works as described
  DO NOT: Test edge cases beyond basic validation, test multiple data states, test negative scenarios, or explore beyond listed scenarios. That's for High/Top priority.""",
        
        "Low": """SMOKE testing required:
  - Verify the feature loads and is accessible
  - Test the primary/main action works
  - Confirm basic functionality operates
  - One happy-path test per scenario is sufficient
  DO NOT: Test validation, test error scenarios, test edge cases, or go beyond basic "does it work?" verification. That's for higher priorities.""",
        
        "N/A": """MINIMAL testing:
  - Verify the feature exists and loads
  - One basic functionality check
  DO NOT: Test functionality in depth. Just confirm it exists and loads."""
    }
    return test_depth_guidance.get(priority, test_depth_guidance["Medium"])


def sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe for use in filenames."""
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    result = name
    for char in invalid_chars:
        result = result.replace(char, '_')
    return result


def generate_feature_extraction_prompt(
    extension_name: str,
    extension_type: str,
    extension_priority: str,
    extension_repo: str,
    repos_base_path: Path
) -> str:
    """
    Generate a prompt for Step 1: Feature Extraction.
    This prompt asks Claude to analyze the extension code and output structured features.
    """
    priority_guidance = get_priority_guidance(extension_priority)
    
    prompt = f"""# Task: Extract Testable Features from Extension

You are analyzing the Evoq extension "{extension_name}" to identify all testable features.

## Extension Details
- **Name**: {extension_name}
- **Type**: {extension_type}
- **Priority**: {extension_priority} - {priority_guidance}
- **Repository**: {extension_repo}
- **Code Location**: {repos_base_path}/{extension_repo}

## Context: Evoq Architecture
Evoq is a private mirror of DNN (DotNetNuke) CMS with additional enterprise features.
- Built in layers: Evoq.Dnn.Platform → Dnn.Evoq.Basic → Dnn.Evoq.Content → Dnn.Evoq.Social
- Extensions add functionality without replacing existing features
- We are testing the v9 to v10 upgrade

## Your Task
Thoroughly analyze the extension's source code and identify ALL testable features.

For each feature, provide:
1. **name**: Clear, descriptive feature name
2. **description**: What the feature does (1-2 sentences)
3. **files**: List of relevant source files (controllers, views, services, etc.)
4. **ui_location**: Where to find/access this feature in the UI (e.g., "Admin > Settings > Feature Name")
5. **test_scenarios**: List of specific test cases (e.g., "Create new item", "Edit existing item", "Delete item", "Verify validation")
6. **dependencies**: Other features or modules this depends on
7. **priority**: Feature-level priority (Top/High/Medium/Low) based on importance

## Instructions
1. Read ALL relevant code files in {repos_base_path}/{extension_repo}
2. Identify controllers, views, services, API endpoints, database interactions
3. Group related functionality into logical features
4. For UI components, note the navigation path to access them
5. Consider edge cases and error scenarios for test_scenarios

## Output Format
Output ONLY a valid JSON object with this structure (no markdown, no explanation, just JSON):

{{
  "features": [
    {{
      "name": "Feature Name",
      "description": "What this feature does",
      "files": ["path/to/file1.cs", "path/to/file2.ascx"],
      "ui_location": "Admin > Section > Feature",
      "test_scenarios": ["Scenario 1", "Scenario 2", "Scenario 3"],
      "dependencies": ["Other Feature"],
      "priority": "High"
    }}
  ]
}}

Be thorough! For a {extension_priority} priority extension, we need comprehensive feature coverage.
Include ALL features you can identify, even small ones.

ULTRATHINK about the codebase structure before outputting the JSON.
"""
    return prompt


def generate_feature_test_prompt(
    extension_name: str,
    extension_type: str,
    extension_priority: str,
    extension_repo: str,
    feature_name: str,
    feature_description: str,
    feature_priority: str,
    feature_ui_location: Optional[str],
    feature_files: List[str],
    feature_test_scenarios: List[str],
    feature_dependencies: List[str],
    feature_index: int,
    total_features: int,
    repos_base_path: Path,
    v10_website_path: Path
) -> str:
    """
    Generate a prompt for Step 2: Testing a specific feature.
    """
    sanitized_feature_name = sanitize_filename(feature_name)
    feature_test_depth = get_feature_test_depth_guidance(feature_priority)
    
    prompt = f"""# Task: Test Feature "{feature_name}"

## Context
You are testing feature {feature_index + 1} of {total_features} for the Evoq extension "{extension_name}".

### Extension Info
- **Extension**: {extension_name} ({extension_type})
- **Extension Priority**: {extension_priority}
- **Repository**: {extension_repo}

### Feature Details
- **Feature Name**: {feature_name}
- **Description**: {feature_description}
- **Feature Priority**: {feature_priority}
- **UI Location**: {feature_ui_location or "Not specified - investigate in code"}
- **Relevant Files**: {', '.join(feature_files) if feature_files else "See repository"}

### Testing Depth for {feature_priority} Priority
{feature_test_depth}

### Suggested Test Scenarios
{chr(10).join(f"- {scenario}" for scenario in feature_test_scenarios) if feature_test_scenarios else "- Determine appropriate test scenarios from the code"}

### Dependencies
{', '.join(feature_dependencies) if feature_dependencies else "None specified"}

## Testing Environment
- **Website URL**: {v10_website_path}
- **Superuser Credentials**: Username: {os.getenv("EVOQ_USERNAME")} / Password: {os.getenv("EVOQ_PASSWORD")}
- **Code Location**: {repos_base_path}/{extension_repo}

## Testing Philosophy (READ THIS CAREFULLY)

### What Counts as a Test
A test MUST involve:
1. UI interaction (clicking, typing, navigating)
2. Observable verification (something changed, appeared, or behaved as expected)

A test is NOT:
- Logging in (that's setup - verify login with ONE screenshot, then move on)
- Reading code and saying "this should work"
- Confirming a feature exists in code without UI evidence

### Test Outcomes: PASS or FAIL Only
Every test has exactly two outcomes:
- **PASS**: The feature works as expected
- **FAIL**: The feature does not work as expected

"Blocked" is NOT a valid outcome. "N/A" is NOT a valid outcome.

If you cannot test something:
- **UI obstruction (popup/overlay)?** → Dismiss it, work around it, find alternative paths, or interact with underlying elements. Actually solve the problem.
- **Feature exists in code but not visible in UI?** → Do NOT create a test for it. Add a note in the report under "Observations": "Code suggests X feature exists, but no UI element found to test it."
- **Previous test failed?** → That does NOT block subsequent tests. Each test is independent. Reset state if needed and continue.

### No Cascading Failures
If Test A fails, Tests B/C/D are still tested independently. Do NOT mark tests as blocked because a prior test had issues. Find another path, reset the page, or start fresh. Every test gets a genuine attempt.

## CRITICAL: Browser Setup (DO THIS FIRST!)

Before ANY navigation or testing, you MUST resize the browser to ensure proper screenshots:

```
Use browser_resize tool with: width=1280, height=720
```

This ensures all screenshots are large and readable. DO NOT SKIP THIS STEP!

## Instructions

1. **FIRST: Resize Browser** - Use `browser_resize` to set viewport to 1280x720
2. **Login (Setup, NOT a test)** - Log in using the provided credentials. Take ONE screenshot to confirm login succeeded. This is setup, not a test - do not include it in test results.
3. **Review the Code**: Examine the relevant files to understand exactly how this feature works
4. **Navigate to Feature**: Use Playwright MCP to navigate to the feature's location in the UI
5. **Execute Test Scenarios**: Test each scenario systematically. Each test is independent.
6. **Take Screenshots**: Capture EVERY step - before, during, and after each action
7. **VERIFY Screenshots**: After EACH screenshot, use the Read tool to VIEW the image and confirm it captured the correct content
8. **Document Results**: Note what worked, what failed, any issues found

## Screenshot Requirements (CRITICAL!)

### Taking Screenshots
- **MANDATORY**: At least ONE screenshot per test step
- Screenshot file names should be descriptive: `{sanitized_feature_name}_step01_navigate.png`
- Save all screenshots to the `.playwright-mcp/` folder (default location)

### Verifying Screenshots (MANDATORY!)
After taking EACH screenshot, you MUST:
1. Use the **Read** tool to open and VIEW the screenshot image file
2. Analyze what the screenshot shows using your vision capabilities
3. Confirm the screenshot captures the intended state/action
4. If the screenshot is incorrect (wrong page, missing content, etc.), retake it

Example verification workflow:
```
1. Take screenshot: browser_take_screenshot with filename="Feature_step01.png"
2. Verify screenshot: Read the file ".playwright-mcp/Feature_step01.png"
3. Analyze: "The screenshot shows [describe what you see]. This correctly captures [the intended state]."
4. If incorrect: Retake the screenshot
```

This verification step ensures test evidence is valid and complete!

### Browser Testing Rules
- Use ONLY Playwright MCP tools for browser interaction (NO code-based browser automation)
- Handle popups gracefully - dismiss or select "don't show again"
- If a feature requires specific setup, document the prerequisites
- Remember: Screenshots without verification are INVALID evidence

## Output
Create a JSON file in the folder: `{extension_name}_result/`

Copy all screenshots from `.playwright-mcp/` to `{extension_name}_result/` so they are stored alongside the JSON.

The JSON MUST follow this EXACT structure:

```json
{{{{
  "metadata": {{{{
    "extension_name": "{extension_name}",
    "extension_type": "{extension_type}",
    "feature_name": "{feature_name}",
    "feature_description": "{feature_description}",
    "feature_priority": "{feature_priority}",
    "test_date": "<ISO 8601 timestamp>",
    "tester": "Claude"
  }}}},
  "test_scenarios": [
    {{{{
      "scenario_name": "<name of the test scenario>",
      "status": "PASS or FAIL",
      "steps": [
        {{{{
          "step_number": 1,
          "action": "<what action was taken>",
          "expected": "<what was expected to happen>",
          "actual": "<what actually happened>",
          "screenshot": "<filename.png>"
        }}}}
      ],
      "issues": ["<any issues found, empty array if none>"]
    }}}}
  ],
  "observations": [
    "<anything discovered but not testable via UI, e.g., 'Code suggests feature X exists but no UI element found'>"
  ],
  "summary": {{{{
    "total_scenarios": <number>,
    "passed": <number>,
    "failed": <number>,
    "pass_rate": "<percentage as string, e.g., '80%'>"
  }}}}
}}}}
```

Name the JSON file: `{sanitized_feature_name}_test_result.json`

IMPORTANT: The JSON file must be valid JSON. Do not include markdown formatting, code fences, or any text outside the JSON object in the file.

## Summary Checklist
- [ ] Browser resized to 1280x720
- [ ] Logged in (setup screenshot taken, NOT counted as a test)
- [ ] Code reviewed for feature understanding
- [ ] Each test scenario executed independently (PASS/FAIL only)
- [ ] Screenshot taken for each step
- [ ] Each screenshot VERIFIED using Read tool
- [ ] Screenshots copied to {extension_name}_result/ folder
- [ ] JSON result file created with all test data and Observations

ULTRATHINK about the test approach before starting!
"""
    return prompt

