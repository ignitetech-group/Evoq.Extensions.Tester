import json
from typing import Dict, Any, Union, List


def format_claude_output_line(line: Union[str, Dict[str, Any]]) -> tuple[str, Dict[str, Any]]:
    """
    Format a line of output from Claude Code.
    
    Args:
        line: The raw JSON line from Claude Code output (string or dict)
        
    Returns:
        Tuple of (formatted_line, raw_data_dict)
        - formatted_line: Human-readable formatted string with proper newlines
        - raw_data_dict: Parsed JSON data (empty dict if parse failed)
    """
    output_parts: List[str] = []
    raw_data = {}
    
    # Handle dict input directly
    if isinstance(line, dict):
        raw_data = line
    else:
        # Handle string input
        line = line.strip()
        if not line:
            return "", {}
        
        try:
            raw_data = json.loads(line)
        except json.JSONDecodeError:
            return f"❌ JSON error: {line[:100]}...\n", {"error": "json_decode_error", "raw_line": line}
    
    # Process the raw_data
    try:
        msg_type = raw_data.get("type", "")
        
        if msg_type == "assistant":
            content = raw_data.get("message", {}).get("content", [])
            for block in content:
                block_type = block.get("type", "")
                
                if block_type == "text":
                    text = block.get("text", "").strip()
                    if text:
                        # Truncate very long text for display
                        display_text = text[:500] + "..." if len(text) > 500 else text
                        output_parts.append(f"🤖 {display_text}")
                        
                elif block_type == "tool_use":
                    tool_name = block.get("name", "unknown")
                    tool_input = block.get("input", {})
                    
                    # Extract relevant info based on tool type
                    if tool_name == "Bash":
                        detail = tool_input.get("command", "")[:80]
                    elif tool_name in ["Read", "Write", "Edit"]:
                        detail = tool_input.get("file_path", "")
                    elif tool_name == "Grep":
                        pattern = tool_input.get("pattern", "")[:30]
                        path = tool_input.get("path", "")
                        detail = f"'{pattern}' in {path}"
                    elif tool_name == "Glob":
                        detail = tool_input.get("pattern", "")
                    elif tool_name == "TodoWrite":
                        todos = tool_input.get("todos", [])
                        detail = f"{len(todos)} items"
                    elif tool_name.startswith("mcp__playwright__"):
                        # Playwright MCP tools - extract action
                        short_name = tool_name.replace("mcp__playwright__", "")
                        if "url" in tool_input:
                            detail = f"{short_name}: {tool_input['url']}"
                        elif "element" in tool_input:
                            detail = f"{short_name}: {tool_input['element'][:50]}"
                        elif "filename" in tool_input:
                            detail = f"{short_name}: {tool_input['filename']}"
                        else:
                            detail = short_name
                        tool_name = "Playwright"
                    else:
                        detail = str(tool_input)[:80]
                    
                    output_parts.append(f"  🔧 {tool_name}: {detail}")
        
        elif msg_type == "user":
            # Tool results - usually verbose, just show summary
            content = raw_data.get("message", {}).get("content", [])
            for block in content:
                if block.get("type") == "tool_result":
                    tool_use_id = block.get("tool_use_id", "")[:8]
                    is_error = block.get("is_error", False)
                    status = "❌" if is_error else "✓"
                    output_parts.append(f"  {status} Tool result [{tool_use_id}...]")
        
        elif msg_type == "result":
            cost = raw_data.get("total_cost_usd", 0)
            duration = raw_data.get("duration_ms", 0) / 1000
            output_parts.append(f"\n💰 Cost: ${cost:.4f} | Duration: {duration:.1f}s")
            
    except Exception as e:
        output_parts.append(f"⚠️ Parse error: {str(e)[:50]}")
        
    # Join with newlines for proper display
    formatted_line = "\n".join(output_parts) if output_parts else ""
    return formatted_line, raw_data


def format_extension_header(extension_name: str, feature_name: str = None) -> str:
    """Format a header for extension/feature output."""
    if feature_name:
        return f"\n{'='*60}\n📦 {extension_name} > {feature_name}\n{'='*60}"
    return f"\n{'='*60}\n📦 {extension_name}\n{'='*60}"
