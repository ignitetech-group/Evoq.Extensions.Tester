from nicegui import ui, app
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

# Your imports
from parallelizer import Parallelizer
from utils import format_claude_output_line
from evoq_types import ExtensionInfo

# Modern dark theme CSS
DARK_THEME_CSS = """
:root {
    --bg-primary: #0f0f13;
    --bg-secondary: #16161d;
    --bg-card: #1c1c26;
    --bg-card-hover: #252532;
    --bg-elevated: #222230;
    --border-subtle: #2a2a3a;
    --border-accent: #3d3d52;
    --text-primary: #e8e8ed;
    --text-secondary: #9898a8;
    --text-muted: #68687a;
    --accent-cyan: #22d3ee;
    --accent-emerald: #34d399;
    --accent-amber: #fbbf24;
    --accent-rose: #fb7185;
    --accent-violet: #a78bfa;
    --gradient-glow: linear-gradient(135deg, #22d3ee20, #a78bfa20);
}

body {
    background: var(--bg-primary) !important;
    color: var(--text-primary) !important;
    font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace !important;
}

.q-card {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 12px !important;
}

.q-header {
    background: linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%) !important;
    border-bottom: 1px solid var(--border-subtle) !important;
}

.q-badge {
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 600 !important;
    letter-spacing: 0.5px !important;
}

.q-btn {
    border-radius: 8px !important;
    font-weight: 500 !important;
    text-transform: none !important;
    letter-spacing: 0.3px !important;
}

.q-select {
    background: var(--bg-elevated) !important;
    border-radius: 8px !important;
}

.q-field__control {
    background: var(--bg-elevated) !important;
    border-radius: 8px !important;
}

.q-toggle__inner {
    background: var(--bg-elevated) !important;
}

/* Scrollbar styling */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-track {
    background: var(--bg-secondary);
    border-radius: 4px;
}
::-webkit-scrollbar-thumb {
    background: var(--border-accent);
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: var(--text-muted);
}

/* Custom card animations */
@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 20px rgba(34, 211, 238, 0.1); }
    50% { box-shadow: 0 0 30px rgba(34, 211, 238, 0.25); }
}

.card-running {
    animation: pulse-glow 2s ease-in-out infinite;
}

/* Glass morphism effect */
.glass-card {
    background: rgba(28, 28, 38, 0.8) !important;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
}

/* Stat card gradient borders */
.stat-card-cyan { border-left: 3px solid var(--accent-cyan) !important; }
.stat-card-amber { border-left: 3px solid var(--accent-amber) !important; }
.stat-card-emerald { border-left: 3px solid var(--accent-emerald) !important; }
.stat-card-violet { border-left: 3px solid var(--accent-violet) !important; }

/* Extension dropdown */
.ext-dropdown .q-item { padding: 8px 12px; }
.ext-dropdown .q-item:hover { background: #252532; }
"""


@dataclass
class ExtensionState:
    """Tracks the state of each extension during testing."""
    name: str
    display_name: str
    priority: str = "Medium"  # Top, High, Medium, Low
    status: str = "idle"  # idle, running, completed, error
    current_cost: float = 0.0
    latest_message: str = "Not started"
    message_history: List[Dict[str, Any]] = field(default_factory=list)
    start_time: Optional[datetime] = None
    # Token tracking
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    # Additional info
    model: str = ""
    current_activity: str = ""  # thinking, tool_use, text


class EvoqExtensionTestUI:
    
    def __init__(self) -> None:
        self.parallelizer: Parallelizer = Parallelizer(
            extension_csv_path=Path("evoq_extensions.csv"),
            repos_base_path=Path("C:\\DNN\\Evoq.Extensions.Tester\\repos"),
            v9_website_path=Path("http://localhost:8091"),
            v10_website_path=Path("http://localhost:8094")
        )
        self.extension_list: List[ExtensionInfo] = self.parallelizer.extension_list
        
        # State tracking for each extension
        self.extension_states: Dict[str, ExtensionState] = {
            ext.name: ExtensionState(
                name=ext.name,
                display_name=getattr(ext, 'display_name', ext.name),
                priority=getattr(ext, 'priority', 'Medium')
            )
            for ext in self.extension_list
        }
        
        # UI state
        self.selected_extensions: set = set()
        self.grid_container = None
        self.cards: Dict[str, 'ExtensionCard'] = {}
        
        # Thread pool for running tests
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    def on_output_callback(self, extension_or_msg: Any, raw_line_or_result: Any) -> None:
        """Callback that receives real-time updates from the parallelizer.
        
        Handles two call signatures:
        1. (ExtensionInfo, str) - streaming output from tester
        2. (str, dict) - completion message from parallelizer
        
        Note: This runs in a background thread, so we only update state here.
        The card timers (running on main thread) will pick up changes automatically.
        """
        print(extension_or_msg, raw_line_or_result)
        # Handle completion callback from parallelizer: on_output("✅ Completed: ...", result_dict)
        if isinstance(extension_or_msg, str):
            # This is a completion message, extract extension name from result
            result = raw_line_or_result
            if isinstance(result, dict):
                ext_name = result.get('extension', '')
                if ext_name in self.extension_states:
                    state = self.extension_states[ext_name]
                    state.status = "completed"
                    state.current_activity = "completed"
                    # Extract final cost if available
                    if 'total_cost_usd' in result:
                        state.current_cost = result.get('total_cost_usd', 0)
                    # Don't call refresh() here - runs in background thread
                    # Card timers will pick up the state change
            return
        
        # Handle streaming callback from tester: on_output(extension, line)
        extension = extension_or_msg
        raw_line = raw_line_or_result
        
        if not hasattr(extension, 'name') or extension.name not in self.extension_states:
            return
        
        state = self.extension_states[extension.name]
        
        # Parse JSON line
        raw_data = {}
        try:
            if isinstance(raw_line, str) and raw_line.strip():
                raw_data = json.loads(raw_line.strip())
        except json.JSONDecodeError:
            pass  # Not valid JSON, skip parsing
        
        formatted_line, parsed_data = format_claude_output_line(raw_line)
        
        # Update state
        if formatted_line:
            state.latest_message = formatted_line
            state.message_history.append({
                "timestamp": datetime.now().isoformat(),
                "formatted": formatted_line,
                "raw": raw_data
            })
        
        # Extract token and activity info from raw data
        if isinstance(raw_data, dict) and raw_data:
            # Handle assistant messages with usage data
            if raw_data.get("type") == "assistant":
                message = raw_data.get("message", {})
                usage = message.get("usage", {})
                
                # Accumulate tokens
                state.input_tokens += usage.get("input_tokens", 0)
                state.output_tokens += usage.get("output_tokens", 0)
                state.cache_read_tokens += usage.get("cache_read_input_tokens", 0)
                state.cache_write_tokens += usage.get("cache_creation_input_tokens", 0)
                
                # Extract model info
                if message.get("model") and not state.model:
                    state.model = message.get("model", "")
                
                # Detect current activity from content
                content = message.get("content", [])
                if content and isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "thinking":
                                state.current_activity = "thinking"
                            elif item.get("type") == "tool_use":
                                tool_name = item.get("name", "tool")
                                state.current_activity = f"using {tool_name}"
                            elif item.get("type") == "text":
                                state.current_activity = "responding"
            
            # Handle system init
            elif raw_data.get("type") == "system" and raw_data.get("subtype") == "init":
                state.model = raw_data.get("model", state.model)
                state.current_activity = "initializing"
            
            # Update cost if present (final result)
            elif raw_data.get("type") == "result":
                state.current_cost = raw_data.get("total_cost_usd", state.current_cost)
                state.status = "completed"
                state.current_activity = "completed"
        
        # Note: Don't call refresh() here - this runs in a background thread
        # The card's own timer (0.5s interval) will pick up state changes automatically
    
    async def run_tests(self, extension_names: List[str]) -> None:
        """Run tests for selected extensions."""
        for name in extension_names:
            if name in self.extension_states:
                state = self.extension_states[name]
                state.status = "running"
                state.start_time = datetime.now()
                state.message_history = []
                state.current_cost = 0.0
                # Reset token counts
                state.input_tokens = 0
                state.output_tokens = 0
                state.cache_read_tokens = 0
                state.cache_write_tokens = 0
                state.model = ""
                state.current_activity = "initializing"
                if name in self.cards:
                    self.cards[name].refresh()
        
        # Run in thread pool to not block UI
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            lambda: self.parallelizer.test_extensions(
                extensions_to_test_name_list=extension_names,
                on_output=self.on_output_callback
            )
        )
    
    def show_extension_detail_dialog(self, extension_name: str) -> None:
        """Show detailed view of an extension in a dialog."""
        state = self.extension_states[extension_name]
        
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-4xl max-h-[80vh]').style(
            'background: #1c1c26; border: 1px solid #3d3d52; border-radius: 16px;'
        ):
            # Header with gradient accent
            with ui.element('div').classes('w-full').style(
                'background: linear-gradient(135deg, #22d3ee10, #a78bfa10); '
                'border-bottom: 1px solid #2a2a3a; padding: 20px; margin: -16px -16px 16px -16px; '
                'border-radius: 16px 16px 0 0;'
            ):
                with ui.row().classes('w-full justify-between items-center'):
                    with ui.row().classes('items-center gap-3'):
                        ui.icon('extension', size='28px').style('color: #22d3ee;')
                        ui.label(state.display_name).classes('text-2xl font-bold').style('color: #e8e8ed;')
                    ui.button(icon='close', on_click=dialog.close).props('flat round').style(
                        'color: #9898a8;'
                    )
            
            # Status bar
            with ui.row().classes('w-full gap-4 mb-4 px-2 flex-wrap'):
                status_styles = {
                    'idle': ('gray-600', '#68687a'),
                    'running': ('cyan-500', '#22d3ee'),
                    'completed': ('emerald-500', '#34d399'),
                    'error': ('rose-500', '#fb7185')
                }
                _, color = status_styles.get(state.status, ('gray-600', '#68687a'))
                
                with ui.element('div').classes('flex items-center gap-2'):
                    ui.element('div').style(
                        f'width: 10px; height: 10px; border-radius: 50%; background: {color}; '
                        f'box-shadow: 0 0 10px {color}80;'
                    )
                    ui.label(state.status.upper()).classes('text-sm font-semibold tracking-wider').style(
                        f'color: {color};'
                    )
                
                # Cost (shown if available)
                if state.current_cost > 0:
                    with ui.element('div').classes('flex items-center gap-2'):
                        ui.icon('payments', size='20px').style('color: #34d399;')
                        ui.label(f'${state.current_cost:.4f}').classes('text-lg font-bold').style('color: #34d399;')
                
                # Token breakdown
                total_tokens = state.input_tokens + state.output_tokens
                if total_tokens > 0:
                    with ui.element('div').classes('flex items-center gap-2'):
                        ui.icon('token', size='20px').style('color: #22d3ee;')
                        ui.label(f'{total_tokens:,} tokens').style('color: #22d3ee;')
                    
                    # Detailed token breakdown
                    with ui.element('div').classes('flex items-center gap-1').style('font-size: 11px;'):
                        ui.label(f'In: {state.input_tokens:,}').style('color: #68687a;')
                        ui.label('•').style('color: #3d3d52;')
                        ui.label(f'Out: {state.output_tokens:,}').style('color: #68687a;')
                        if state.cache_read_tokens > 0:
                            ui.label('•').style('color: #3d3d52;')
                            ui.label(f'Cache: {state.cache_read_tokens:,}').style('color: #68687a;')
                
                if state.start_time:
                    with ui.element('div').classes('flex items-center gap-2'):
                        ui.icon('schedule', size='20px').style('color: #9898a8;')
                        ui.label(f'{state.start_time.strftime("%H:%M:%S")}').style('color: #9898a8;')
                
                # Model info
                if state.model:
                    with ui.element('div').classes('flex items-center gap-2'):
                        ui.icon('smart_toy', size='18px').style('color: #68687a;')
                        model_short = state.model.split('/')[-1][:20] if '/' in state.model else state.model[:20]
                        ui.label(model_short).classes('text-xs').style('color: #68687a;')
            
            # Message history section
            with ui.element('div').classes('px-2 w-full').style('overflow: hidden;'):
                with ui.row().classes('items-center gap-2 mb-3'):
                    ui.icon('terminal', size='20px').style('color: #a78bfa;')
                    ui.label('Output Log').classes('text-lg font-semibold').style('color: #e8e8ed;')
                
                with ui.scroll_area().classes('w-full h-96').style(
                    'background: #0f0f13; border: 1px solid #2a2a3a; border-radius: 8px; '
                    'max-width: 100%;'
                ):
                    history_container = ui.column().classes('w-full p-3 gap-2').style(
                        'max-width: 100%; overflow: hidden;'
                    )
                    
                    # Flag to prevent updates after dialog closes
                    dialog_state = {'active': True}
                    
                    def update_history():
                        # Skip if dialog is no longer active
                        if not dialog_state['active']:
                            return
                        try:
                            history_container.clear()
                            with history_container:
                                if not state.message_history:
                                    with ui.row().classes('items-center gap-2 py-8 justify-center'):
                                        ui.icon('hourglass_empty', size='24px').style('color: #68687a;')
                                        ui.label('Waiting for output...').style('color: #68687a; font-style: italic;')
                                else:
                                    for entry in state.message_history:
                                        with ui.element('div').classes('w-full p-3').style(
                                            'background: #16161d; border-radius: 6px; border-left: 2px solid #3d3d52; '
                                            'overflow: hidden;'
                                        ):
                                            ui.label(entry['timestamp']).classes('text-xs mb-1').style('color: #68687a;')
                                            ui.label(entry['formatted']).classes('text-sm').style(
                                                'color: #e8e8ed; font-family: "JetBrains Mono", monospace; '
                                                'white-space: pre-wrap; word-break: break-word; overflow-wrap: break-word; '
                                                'width: 100%; display: block;'
                                            )
                        except Exception:
                            # Client may have been deleted, stop trying to update
                            dialog_state['active'] = False
                    
                    update_history()
                    timer = ui.timer(1.0, update_history)
                    
                    def on_close():
                        dialog_state['active'] = False
                        timer.cancel()
        
        dialog.on('close', on_close)
        dialog.open()
    
    def build_ui(self) -> None:
        """Build the main UI."""
        
        # Inject dark theme CSS
        ui.add_head_html(f'<style>{DARK_THEME_CSS}</style>')
        ui.add_head_html(
            '<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">'
        )
        
        # Header with sleek design
        with ui.header().classes('items-center justify-between px-6 py-4').style(
            'background: linear-gradient(180deg, #16161d 0%, #0f0f13 100%); '
            'border-bottom: 1px solid #2a2a3a;'
        ):
            with ui.row().classes('items-center gap-4'):
                # Logo/Icon
                with ui.element('div').style(
                    'width: 42px; height: 42px; border-radius: 10px; '
                    'background: linear-gradient(135deg, #22d3ee, #a78bfa); '
                    'display: flex; align-items: center; justify-content: center;'
                ):
                    ui.icon('science', size='24px').style('color: #0f0f13;')
                
                with ui.column().classes('gap-0'):
                    ui.label('Evoq Extension Tester').classes('text-xl font-bold tracking-tight').style(
                        'color: #e8e8ed; line-height: 1.2;'
                    )
                    ui.label('Automated Testing Dashboard').classes('text-xs').style(
                        'color: #68687a; letter-spacing: 1px; text-transform: uppercase;'
                    )
            
            # Header stats
            with ui.row().classes('items-center gap-6'):
                with ui.element('div').classes('text-right'):
                    ui.label('Extensions').classes('text-xs').style('color: #68687a;')
                    ui.label(str(len(self.extension_list))).classes('text-lg font-bold').style('color: #22d3ee;')
        
        # Main layout with sidebar
        with ui.row().classes('w-full flex-nowrap').style('background: #0f0f13; height: calc(100vh - 80px);'):
            
            # Left Sidebar - fixed width, sticky, scrollable if needed
            with ui.column().classes('gap-4 p-5').style(
                'width: 220px; min-width: 220px; flex-shrink: 0; background: #16161d; '
                'border-right: 1px solid #2a2a3a; position: sticky; top: 80px; '
                'height: calc(100vh - 80px); overflow-y: auto;'
            ):
                # Sidebar header
                with ui.row().classes('items-center gap-2 mb-2'):
                    ui.icon('analytics', size='20px').style('color: #a78bfa;')
                    ui.label('Statistics').classes('text-sm font-semibold uppercase tracking-wider').style(
                        'color: #68687a;'
                    )
                
                # Stat cards stacked vertically
                self._create_sidebar_stat('total_card', 'Total', len(self.extension_list), 'cyan', 'inventory_2')
                self._create_sidebar_stat('running_card', 'Running', 0, 'amber', 'sync')
                self._create_sidebar_stat('completed_card', 'Completed', 0, 'emerald', 'check_circle')
                self._create_sidebar_stat('total_cost_card', 'Total Cost', '$0.00', 'violet', 'payments')
                
                # Stats auto-update
                ui.timer(1.0, self._update_stats)
                
                # Spacer
                ui.element('div').classes('flex-grow')
                
                # Sidebar footer info
                with ui.element('div').style(
                    'padding: 12px; background: #1c1c26; border-radius: 8px; border: 1px solid #2a2a3a;'
                ):
                    ui.label('Quick Actions').classes('text-xs font-medium uppercase tracking-wider mb-2').style(
                        'color: #68687a;'
                    )
                    ui.button('Select All', on_click=self._select_all, icon='select_all').props('flat dense').style(
                        'color: #9898a8 !important; justify-content: flex-start; width: 100%;'
                    )
                    ui.button('Clear Selection', on_click=self._select_none, icon='deselect').props('flat dense').style(
                        'color: #9898a8 !important; justify-content: flex-start; width: 100%;'
                    )
            
            # Main content area - scrollable independently
            with ui.column().classes('flex-grow p-6 gap-5').style(
                'min-width: 0; overflow-y: auto; height: calc(100vh - 80px);'
            ):
                
                # Controls section
                with ui.card().classes('w-full').style(
                    'background: #1c1c26; border: 1px solid #2a2a3a; border-radius: 12px; padding: 20px;'
                ):
                    with ui.row().classes('items-center gap-2 mb-4'):
                        ui.icon('tune', size='22px').style('color: #a78bfa;')
                        ui.label('Test Configuration').classes('text-lg font-semibold').style('color: #e8e8ed;')
                    
                    with ui.row().classes('gap-3 flex-wrap items-center'):
                        # Build extension options with priority info for display
                        self._extension_priority_map = {
                            ext.name: getattr(ext, 'priority', 'Medium')
                            for ext in self.extension_list
                        }
                        
                        # Format: "Display Name • Priority"  
                        extension_options = {
                            ext.name: f"{getattr(ext, 'display_name', ext.name)}  •  {getattr(ext, 'priority', 'Medium')}"
                            for ext in self.extension_list
                        }
                        
                        self.extension_select = ui.select(
                            options=extension_options,
                            multiple=True,
                            label='Select Extensions',
                            on_change=lambda e: self._on_selection_change(e.value)
                        ).classes('flex-grow').props('use-chips filled dark').style(
                            'background: #16161d; min-width: 200px; max-width: 600px;'
                        )
                        
                        # Run button with gradient
                        self.run_button = ui.button(
                            'Run Tests',
                            on_click=self._run_selected,
                            icon='play_arrow'
                        ).props('unelevated').style(
                            'background: linear-gradient(135deg, #22d3ee, #34d399) !important; '
                            'color: #0f0f13 !important; font-weight: 600; padding: 12px 24px;'
                        )
                    
                    # Selection counter
                    with ui.row().classes('items-center gap-2 mt-3'):
                        ui.icon('check_circle', size='18px').style('color: #34d399;')
                        self.selection_label = ui.label('0 extensions selected').style('color: #9898a8; font-size: 14px;')
                
                # Grid section header
                with ui.row().classes('w-full items-center justify-between'):
                    with ui.column().classes('gap-1'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('grid_view', size='22px').style('color: #22d3ee;')
                            ui.label('Extension Status').classes('text-xl font-semibold').style('color: #e8e8ed;')
                        ui.label('Click any card to view full output log').classes('text-sm').style('color: #68687a;')
                    
                    # Filter toggle with modern styling
                    self.show_filter = ui.toggle(
                        ['All', 'Selected', 'Running'],
                        value='Selected',
                        on_change=lambda: self._rebuild_grid()
                    ).props('no-caps').style(
                        'background: #1c1c26; border-radius: 8px; border: 1px solid #2a2a3a;'
                    )
                
                # Extension grid
                self.grid_container = ui.element('div').classes(
                    'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 w-full'
                )
                
                self._rebuild_grid()
    
    def _create_sidebar_stat(self, card_id: str, label: str, value: Any, color: str, icon: str) -> None:
        """Create a compact stat card for the sidebar."""
        color_map = {
            'cyan': '#22d3ee',
            'amber': '#fbbf24',
            'emerald': '#34d399',
            'violet': '#a78bfa'
        }
        hex_color = color_map.get(color, '#22d3ee')
        
        with ui.element('div').style(
            'background: #1c1c26; border: 1px solid #2a2a3a; border-radius: 10px; padding: 14px;'
        ):
            with ui.row().classes('items-center justify-between w-full'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon(icon, size='18px').style(f'color: {hex_color};')
                    ui.label(label).classes('text-xs font-medium').style('color: #9898a8;')
                setattr(self, f'{card_id}_value', 
                    ui.label(str(value)).classes('text-xl font-bold').style(f'color: {hex_color};')
                )
    
    def _update_stats(self) -> None:
        """Update summary statistics."""
        try:
            running = sum(1 for s in self.extension_states.values() if s.status == 'running')
            completed = sum(1 for s in self.extension_states.values() if s.status == 'completed')
            total_cost = sum(s.current_cost for s in self.extension_states.values())
            
            self.running_card_value.text = str(running)
            self.completed_card_value.text = str(completed)
            self.total_cost_card_value.text = f'${total_cost:.4f}'
        except Exception:
            # UI elements may have been deleted during page refresh/navigation
            pass
    
    def _on_selection_change(self, value: List[str]) -> None:
        """Handle selection change."""
        self.selected_extensions = set(value) if value else set()
        self.selection_label.text = f'{len(self.selected_extensions)} extensions selected'
        self._rebuild_grid()
    
    def _select_all(self) -> None:
        self.extension_select.value = list(self.extension_states.keys())
    
    def _select_none(self) -> None:
        self.extension_select.value = []
    
    def _select_running(self) -> None:
        running = [name for name, state in self.extension_states.items() if state.status == 'running']
        self.extension_select.value = running
    
    async def _run_selected(self) -> None:
        """Run tests for selected extensions."""
        if not self.selected_extensions:
            ui.notify('Please select at least one extension', type='warning')
            return
        
        ui.notify(f'Starting tests for {len(self.selected_extensions)} extensions...', type='info')
        await self.run_tests(list(self.selected_extensions))
        ui.notify('All tests completed!', type='positive')
    
    def _rebuild_grid(self) -> None:
        """Rebuild the extension grid based on filter."""
        # Deactivate and cancel timers for existing cards before clearing
        for card in self.cards.values():
            card.active = False  # Mark as inactive FIRST
            if hasattr(card, 'timer'):
                card.timer.cancel()
        
        self.grid_container.clear()
        self.cards.clear()
        
        filter_mode = self.show_filter.value
        
        extensions_to_show = []
        for name, state in self.extension_states.items():
            if filter_mode == 'All':
                extensions_to_show.append(name)
            elif filter_mode == 'Selected' and name in self.selected_extensions:
                extensions_to_show.append(name)
            elif filter_mode == 'Running' and state.status == 'running':
                extensions_to_show.append(name)
        
        with self.grid_container:
            if not extensions_to_show:
                with ui.element('div').classes('col-span-full flex flex-col items-center justify-center py-16 gap-4'):
                    ui.icon('inbox', size='64px').style('color: #3d3d52;')
                    ui.label('No extensions to display').classes('text-lg').style('color: #68687a;')
                    ui.label('Select some extensions from the dropdown above').style('color: #3d3d52; font-size: 14px;')
            else:
                for name in extensions_to_show:
                    self.cards[name] = ExtensionCard(
                        state=self.extension_states[name],
                        on_click=lambda n=name: self.show_extension_detail_dialog(n)
                    )


class ExtensionCard:
    """A single extension card in the grid."""
    
    # Status configurations for dark theme
    STATUS_CONFIG = {
        'idle': {
            'color': '#68687a',
            'bg': '#1c1c26',
            'border': '#2a2a3a',
            'glow': 'none',
            'icon': 'hourglass_empty'
        },
        'running': {
            'color': '#22d3ee',
            'bg': '#1c1c26',
            'border': '#22d3ee',
            'glow': '0 0 20px rgba(34, 211, 238, 0.2)',
            'icon': 'sync'
        },
        'completed': {
            'color': '#34d399',
            'bg': '#1c1c26',
            'border': '#34d399',
            'glow': '0 0 20px rgba(52, 211, 153, 0.15)',
            'icon': 'check_circle'
        },
        'error': {
            'color': '#fb7185',
            'bg': '#1c1c26',
            'border': '#fb7185',
            'glow': '0 0 20px rgba(251, 113, 133, 0.2)',
            'icon': 'error'
        }
    }
    
    # Priority styling configurations
    PRIORITY_CONFIG = {
        'Top': {'color': '#fb7185', 'bg': '#fb718520', 'icon': 'keyboard_double_arrow_up'},
        'High': {'color': '#fbbf24', 'bg': '#fbbf2420', 'icon': 'keyboard_arrow_up'},
        'Medium': {'color': '#22d3ee', 'bg': '#22d3ee20', 'icon': 'remove'},
        'Low': {'color': '#68687a', 'bg': '#68687a20', 'icon': 'keyboard_arrow_down'},
        'N/A': {'color': '#3d3d52', 'bg': '#3d3d5220', 'icon': 'help_outline'}
    }
    
    def __init__(self, state: ExtensionState, on_click: callable):
        self.state = state
        self.on_click = on_click
        self.active = True  # Flag to track if card is still valid
        self._build()
    
    def _build(self) -> None:
        """Build the card UI."""
        config = self.STATUS_CONFIG.get(self.state.status, self.STATUS_CONFIG['idle'])
        extra_class = 'card-running' if self.state.status == 'running' else ''
        
        self.card = ui.card().classes(f'cursor-pointer transition-all duration-200 {extra_class}').style(
            f'background: {config["bg"]}; '
            f'border: 1px solid {config["border"]}; '
            f'border-radius: 12px; '
            f'box-shadow: {config["glow"]}; '
            f'padding: 16px;'
        ).on('click', self.on_click)
        
        with self.card:
            # Header with status indicator
            with ui.row().classes('w-full justify-between items-start mb-2'):
                with ui.column().classes('gap-1 flex-1 overflow-hidden'):
                    self.name_label = ui.label(self.state.display_name).classes(
                        'font-semibold truncate'
                    ).style('color: #e8e8ed; font-size: 15px; max-width: 100%;')
                
                # Status indicator dot
                with ui.element('div').classes('flex items-center gap-2'):
                    self.status_dot = ui.element('div').style(
                        f'width: 8px; height: 8px; border-radius: 50%; background: {config["color"]}; '
                        f'box-shadow: 0 0 8px {config["color"]}80;'
                    )
                    self.status_icon = ui.icon(config['icon'], size='18px').style(f'color: {config["color"]};')
            
            # Priority badge
            priority_cfg = self.PRIORITY_CONFIG.get(self.state.priority, self.PRIORITY_CONFIG['Medium'])
            with ui.element('div').classes('flex items-center gap-1 mb-3').style(
                f'background: {priority_cfg["bg"]}; padding: 4px 8px; border-radius: 4px; width: fit-content;'
            ):
                ui.icon(priority_cfg['icon'], size='14px').style(f'color: {priority_cfg["color"]};')
                ui.label(self.state.priority).classes('text-xs font-semibold uppercase tracking-wider').style(
                    f'color: {priority_cfg["color"]};'
                )
            
            # Metrics display - tokens while running, cost when completed
            with ui.element('div').classes('mb-3'):
                # Token/Cost row
                with ui.row().classes('items-center gap-3'):
                    # Main metric (tokens or cost)
                    self.metric_icon = ui.icon('token', size='18px').style('color: #22d3ee;')
                    self.metric_label = ui.label(self._format_metric()).classes('text-xl font-bold').style(
                        'color: #22d3ee;'
                    )
                
                # Activity indicator (only shown when running)
                self.activity_container = ui.element('div').classes('flex items-center gap-1 mt-1')
                with self.activity_container:
                    self.activity_icon = ui.icon('psychology', size='14px').style('color: #a78bfa;')
                    self.activity_label = ui.label('').classes('text-xs').style(
                        'color: #a78bfa; font-style: italic;'
                    )
            
            # Latest message with terminal-style display
            with ui.element('div').style(
                'background: #0f0f13; border-radius: 6px; padding: 10px; '
                'border: 1px solid #2a2a3a; min-height: 44px;'
            ):
                self.message_label = ui.label(self.state.latest_message).classes('text-xs').style(
                    'color: #9898a8; font-family: "JetBrains Mono", monospace; '
                    'overflow: hidden; text-overflow: ellipsis; display: -webkit-box; '
                    '-webkit-line-clamp: 2; -webkit-box-orient: vertical;'
                )
        
        # Auto-refresh this card
        self.timer = ui.timer(0.5, self.refresh)
    
    def _get_status_config(self) -> dict:
        return self.STATUS_CONFIG.get(self.state.status, self.STATUS_CONFIG['idle'])
    
    def _format_tokens(self, tokens: int) -> str:
        """Format token count with K/M suffix."""
        if tokens >= 1_000_000:
            return f"{tokens / 1_000_000:.1f}M"
        elif tokens >= 1_000:
            return f"{tokens / 1_000:.1f}k"
        return str(tokens)
    
    def _format_metric(self) -> str:
        """Format the main metric based on status."""
        if self.state.status == 'completed':
            return f"${self.state.current_cost:.4f}"
        else:
            total_tokens = self.state.input_tokens + self.state.output_tokens
            return f"{self._format_tokens(total_tokens)} tokens"
    
    def _get_activity_icon(self) -> str:
        """Get icon based on current activity."""
        activity = self.state.current_activity.lower()
        if 'thinking' in activity:
            return 'psychology'
        elif 'using' in activity or 'read' in activity:
            return 'build'
        elif 'responding' in activity:
            return 'chat'
        elif 'completed' in activity:
            return 'check'
        return 'sync'
    
    def refresh(self) -> None:
        """Refresh the card display."""
        # Skip if card has been deactivated
        if not self.active:
            return
        try:
            config = self._get_status_config()
            
            # Update metric display (tokens while running, cost when completed)
            self.metric_label.text = self._format_metric()
            if self.state.status == 'completed':
                self.metric_icon._props['name'] = 'payments'
                self.metric_icon.style('color: #34d399;')
                self.metric_label.style('color: #34d399;')
            else:
                self.metric_icon._props['name'] = 'token'
                self.metric_icon.style('color: #22d3ee;')
                self.metric_label.style('color: #22d3ee;')
            self.metric_icon.update()
            
            # Update activity indicator
            if self.state.status == 'running' and self.state.current_activity:
                self.activity_label.text = self.state.current_activity
                self.activity_icon._props['name'] = self._get_activity_icon()
                self.activity_icon.update()
                self.activity_container.style('display: flex;')
            else:
                self.activity_container.style('display: none;')
            
            self.message_label.text = self.state.latest_message or 'Waiting for output...'
            
            # Update status indicator
            self.status_dot.style(
                f'width: 8px; height: 8px; border-radius: 50%; background: {config["color"]}; '
                f'box-shadow: 0 0 8px {config["color"]}80;'
            )
            self.status_icon._props['name'] = config['icon']
            self.status_icon.style(f'color: {config["color"]};')
            self.status_icon.update()
            
            # Update card border/glow
            extra_class = 'card-running' if self.state.status == 'running' else ''
            self.card._classes = [c for c in self.card._classes if c != 'card-running']
            if extra_class:
                self.card._classes.append(extra_class)
            self.card.style(
                f'background: {config["bg"]}; '
                f'border: 1px solid {config["border"]}; '
                f'border-radius: 12px; '
                f'box-shadow: {config["glow"]}; '
                f'padding: 16px;'
            )
        except Exception:
            # Card may have been deleted (e.g., grid rebuilt), deactivate and cancel
            self.active = False
            if hasattr(self, 'timer'):
                self.timer.cancel()


# Main entry point
def main():
    # Enable dark mode for Quasar
    app.add_static_files('/static', 'static')
    
    test_ui = EvoqExtensionTestUI()
    test_ui.build_ui()
    ui.run(
        title='Evoq Extension Tester',
        port=8098,
        reload=False,
        dark=True,
        favicon='🧪'
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()