"""
prompts.py - Prompt templates for Evoq test generation pipeline
"""

import os
from pathlib import Path
from typing import Optional, List


def get_priority_guidance(priority: str) -> str:
    """Get testing depth guidance based on priority level."""
    priority_guidance = {
        "Top": "CRITICAL extension requiring exhaustive coverage of absolutely everything. This has the most customer issues.",
        "High": "Important extension requiring thorough coverage. Test as much as practically possible.",
        "Medium": "Test the most important features and scenarios. Ensure critical functionality works.",
        "Low": "Basic smoke testing to verify the extension works as expected.",
        "N/A": "Should be covered by other extension tests."
    }
    return priority_guidance.get(priority, priority_guidance["Medium"])


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

### Suggested Test Scenarios
{chr(10).join(f"- {scenario}" for scenario in feature_test_scenarios) if feature_test_scenarios else "- Determine appropriate test scenarios from the code"}

### Dependencies
{', '.join(feature_dependencies) if feature_dependencies else "None specified"}

## Testing Environment
- **Website URL**: {v10_website_path}
- **Superuser Credentials**: Username: {os.getenv("EVOQ_USERNAME")} / Password: {os.getenv("EVOQ_PASSWORD")}
- **Code Location**: {repos_base_path}/{extension_repo}

## CRITICAL: Browser Setup (DO THIS FIRST!)

Before ANY navigation or testing, you MUST resize the browser to ensure proper screenshots:

```
Use browser_resize tool with: width=1280, height=720
```

This ensures all screenshots are large and readable. DO NOT SKIP THIS STEP!

## Instructions

1. **FIRST: Resize Browser** - Use `browser_resize` to set viewport to 1920x1080
2. **Review the Code**: Examine the relevant files to understand exactly how this feature works
3. **Navigate to Feature**: Use Playwright MCP to navigate to the feature's location in the UI
4. **Execute Test Scenarios**: Test each scenario systematically
5. **Take Screenshots**: Capture EVERY step - before, during, and after each action
6. **VERIFY Screenshots**: After EACH screenshot, use the Read tool to VIEW the image and confirm it captured the correct content
7. **Document Results**: Note what worked, what failed, any issues found

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
Create an HTML report in the folder: `{extension_name}_result/`

The HTML should include:
1. Feature name and description
2. Each test scenario with:
   - What was tested
   - Steps taken
   - Screenshots (using `<img>` tags - copy from .playwright-mcp/ to {extension_name}_result/)
   - Pass/Fail status
   - Any issues or observations

Name the HTML file: `{sanitized_feature_name}_test_report.html`

## Summary Checklist
- [ ] Browser resized to 1920x1080
- [ ] Code reviewed for feature understanding
- [ ] Each test scenario executed
- [ ] Screenshot taken for each step
- [ ] Each screenshot VERIFIED using Read tool
- [ ] HTML report created with all screenshots

ULTRATHINK about the test approach before starting!
"""
    return prompt

