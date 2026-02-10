# Task: Test Feature "Web API Services"

## Context
You are testing feature 14 of 17 for the Evoq extension "DNN_HTML".

### Extension Info
- **Extension**: DNN_HTML (Module)
- **Extension Priority**: High
- **Repository**: Dnn.Evoq.Basic

### Feature Details
- **Feature Name**: Web API Services
- **Description**: RESTful API endpoints for programmatic content management
- **Feature Priority**: Low
- **UI Location**: API: /DesktopModules/HtmlPro/API/
- **Relevant Files**: Evoq Content/Modules/HTMLPro/Services/HtmlTextProController.cs, Evoq Content/Modules/HTMLPro/Services/ServiceRouteMapper.cs

### Testing Depth for Low Priority
SMOKE testing required:
  - Verify the feature loads and is accessible
  - Test the primary/main action works
  - Confirm basic functionality operates
  - One happy-path test per scenario is sufficient
  DO NOT: Test validation, test error scenarios, test edge cases, or go beyond basic "does it work?" verification. That's for higher priorities.

### Suggested Test Scenarios
- Save content via API
- Create module via API
- Update module content via API
- Set master content via API
- Test API authentication
- Handle API errors
- Validate API input
- Test API response format

### Dependencies
DNN Web API Framework

## Testing Environment
- **Website URL**: http:\localhost:8081
- **Superuser Credentials**: Username: host / Password: Pass123456
- **Code Location**: C:\DNN\Evoq.Extensions.Tester\repos/Dnn.Evoq.Basic

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

### CRITICAL: No Retroactive Test Creation (READ THIS!)

**DO NOT rationalize unexpected behavior as "expected."**

If you encounter an unexpected error, warning dialog, or failure during a planned test:
1. **PAUSE** - Do not immediately assume it's "working correctly"
2. **RESEARCH** - Examine the code to understand if this behavior is intentional
3. **DECIDE** - Based on evidence, determine if this is a bug or expected behavior

**Bad Example (DO NOT DO THIS):**
```
You're testing "Publish content" and an error dialog appears saying "Another user has changed the page state."
WRONG: Create a new test "Handle publish conflicts" → status: PASS → "System correctly detected conflict"
```
This is WRONG because:
1. You didn't plan to test conflict handling
2. You assumed the error was expected without researching
3. You retrofitted a test scenario to justify the error

**Correct Approach:**
```
You're testing "Publish content" and an unexpected error dialog appears.

STEP 1: Research the code
- Look at the controller/service handling publish
- Check if this error is intentionally thrown under specific conditions
- Determine: Was this error SUPPOSED to happen in this context?

STEP 2: Make an informed decision
- If code shows this error is a BUG or shouldn't occur in your test context:
  → Mark "Publish content" as FAIL → actual: "Unexpected error: [message]" → issue: "Publish failed with error that should not occur in this context"

- If code CONFIRMS this is intentional behavior for your exact scenario:
  → Mark "Publish content" as FAIL → actual: "Error dialog appeared: [message]" → Add to Observations: "Code confirms [error] is intentional when [condition]. Consider adding explicit test scenario for this in future."
  → Do NOT create a new PASS test for it. Note it, but the original test still failed its objective.
```

**The Rule:** Never assume unexpected behavior is correct. Always research first. Even if research confirms the behavior is intentional, do NOT create retroactive test scenarios to inflate pass rates. Document findings in Observations instead.

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
5. **Explore and Execute Tests**: Based on the suggested scenarios, code review, AND what you observe in the UI, execute appropriate tests. Each test is independent.
6. **Take Screenshots**: Capture EVERY step - before, during, and after each action
7. **VERIFY Screenshots**: After EACH screenshot, use the Read tool to VIEW the image and confirm it captured the correct content
8. **Document Results**: Note what worked, what failed, any issues found

## Screenshot Requirements (CRITICAL!)

### Taking Screenshots
- **MANDATORY**: At least ONE screenshot per test step
- Screenshot file names should be descriptive: `Web API Services_step01_navigate.png`
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
Create a JSON file in the folder: `DNN_HTML_result/`

Copy all screenshots from `.playwright-mcp/` to `DNN_HTML_result/` so they are stored alongside the JSON.

The JSON MUST follow this EXACT structure:

```json
{{
  "metadata": {{
    "extension_name": "DNN_HTML",
    "extension_type": "Module",
    "feature_name": "Web API Services",
    "feature_description": "RESTful API endpoints for programmatic content management",
    "feature_priority": "Low",
    "test_date": "<ISO 8601 timestamp>",
    "tester": "Claude"
  }},
  "test_scenarios": [
    {{
      "scenario_name": "<name of the test scenario>",
      "status": "PASS or FAIL",
      "steps": [
        {{
          "step_number": 1,
          "action": "<what action was taken>",
          "expected": "<what was expected to happen>",
          "actual": "<what actually happened>",
          "screenshot": "<filename.png>"
        }}
      ],
      "issues": ["<any issues found, empty array if none>"]
    }}
  ],
  "observations": [
    "<anything discovered but not testable via UI, e.g., 'Code suggests feature X exists but no UI element found'>"
  ],
  "summary": {{
    "total_scenarios": <number>,
    "passed": <number>,
    "failed": <number>,
    "pass_rate": "<percentage as string, e.g., '80%'>"
  }}
}}
```

Name the JSON file: `Web API Services_test_result.json`

IMPORTANT: The JSON file must be valid JSON. Do not include markdown formatting, code fences, or any text outside the JSON object in the file.

## Summary Checklist
- [ ] Browser resized to 1280x720
- [ ] Logged in (setup screenshot taken, NOT counted as a test)
- [ ] Code reviewed for feature understanding
- [ ] Each test scenario executed independently (PASS/FAIL only)
- [ ] Screenshot taken for each step
- [ ] Each screenshot VERIFIED using Read tool
- [ ] Screenshots copied to DNN_HTML_result/ folder
- [ ] JSON result file created with all test data and Observations

ULTRATHINK about the test approach before starting!
