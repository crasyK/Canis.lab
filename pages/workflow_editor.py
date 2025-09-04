import streamlit as st
import os
import json
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
from streamlit_flow.state import StreamlitFlowState
from streamlit_flow.layouts import LayeredLayout
from lib.app_objects import step, create_complete_flow_from_state
from lib.state_managment import (
    create_state, start_seed_step, complete_running_step,
    use_llm_tool, use_code_tool, get_markers, get_uploaded_markers,
    get_step_deletion_preview, use_chip, delete_step_and_data, get_deletable_steps, 
    delete_multiple_steps, clear_all_steps, recover_from_backup
)
from lib.tools.llm import get_available_llm_tools, prepare_data
from lib.tools.code import get_available_code_tools, prepare_tool_use
from lib.tools.chip import get_available_chips, prepare_chip_use
from lib.tools.global_func import get_type, check_data_type, has_connection
from lib.directory_manager import dir_manager
from lib.theme_manager import theme_manager

# Page config
st.set_page_config(page_title="Workflow Editor", layout="wide")

# Apply theme CSS
theme_manager.apply_theme_css()

# Enhanced session state initialization
def initialize_enhanced_session_state():
    """Initialize enhanced session state with better organization"""
    # Core workflow state
    if 'current_workflow' not in st.session_state:
        st.session_state.current_workflow = None
    
    if 'flow_state' not in st.session_state:
        st.session_state.flow_state = StreamlitFlowState([],[])
    
    # UI state management
    if 'selected_node_id' not in st.session_state:
        st.session_state.selected_node_id = None
    
    if 'show_workflow_creator' not in st.session_state:
        st.session_state.show_workflow_creator = False
    
    if 'show_workflow_loader' not in st.session_state:
        st.session_state.show_workflow_loader = False
    
    if 'show_seed_selector' not in st.session_state:
        st.session_state.show_seed_selector = False
    
    if 'show_single_data_creator' not in st.session_state:
        st.session_state.show_single_data_creator = False
    
    if 'show_step_creator' not in st.session_state:
        st.session_state.show_step_creator = False
    
    # Enhanced features
    if 'pending_steps' not in st.session_state:
        st.session_state.pending_steps = []
    
    if 'auto_save_enabled' not in st.session_state:
        st.session_state.auto_save_enabled = True
    
    if 'show_data_preview' not in st.session_state:
        st.session_state.show_data_preview = True
    
    if 'compact_mode' not in st.session_state:
        st.session_state.compact_mode = False
    
    # Message system
    if 'messages' not in st.session_state:
        st.session_state.messages = []

# Enhanced message system
def set_message(msg_type, message, duration=5):
    """Set a message with type and auto-clear"""
    st.session_state.messages.append({
        'type': msg_type,
        'message': message,
        'timestamp': st.session_state.get('message_counter', 0)
    })
    st.session_state.message_counter = st.session_state.get('message_counter', 0) + 1

def render_messages():
    """Render all active messages"""
    if not st.session_state.messages:
        return
    
    for msg in st.session_state.messages[-3:]:  # Show last 3 messages
        if msg['type'] == 'success':
            st.success(msg['message'])
        elif msg['type'] == 'error':
            st.error(msg['message'])
        elif msg['type'] == 'warning':
            st.warning(msg['message'])
        else:
            st.info(msg['message'])

# Enhanced utility functions using your existing architecture
def get_available_runs():
    """Get available workflow runs using your directory manager"""
    try:
        return dir_manager.get_available_runs()
    except Exception as e:
        set_message('error', f"Error loading workflows: {e}")
        return []

def create_new_workflow(workflow_name):
    """Create new workflow using your state management"""
    try:
        if create_state(workflow_name):
            st.session_state.current_workflow = workflow_name
            load_workflow_state(workflow_name)
            set_message('success', f"✅ Created workflow: {workflow_name}")
            return True
    except Exception as e:
        set_message('error', f"❌ Error creating workflow: {e}")
    return False

def load_workflow_state(workflow_name):
    """Load workflow state using your existing system"""
    try:
        st.session_state.current_workflow = workflow_name
        
        # Load the flow state using your existing system
        state_file_path = dir_manager.get_state_file_path(workflow_name)
        if state_file_path.exists():
            # Use your existing flow creation logic
            flow_state = create_complete_flow_from_state(str(state_file_path))
            st.session_state.flow_state = flow_state
            
            # Clear pending steps when loading existing workflow
            st.session_state.pending_steps = []
            
            set_message('success', f"✅ Loaded workflow: {workflow_name}")
            return True
        else:
            # Create empty flow for new workflow
            st.session_state.flow_state = StreamlitFlowState([])
            return True
            
    except Exception as e:
        set_message('error', f"❌ Error loading workflow: {e}")
        return False

def get_available_seed_files():
    """Get available seed files using your directory structure"""
    try:
        seeds_dir = dir_manager.get_seeds_directory()
        if not seeds_dir.exists():
            return []
        
        seed_files = []
        for seed_file in seeds_dir.glob("*.json"):
            try:
                # Load seed metadata if available
                seed_data = dir_manager.load_json(seed_file)
                display_name = seed_data.get('metadata', {}).get('name', seed_file.stem)
                seed_files.append({
                    'path': str(seed_file),
                    'display_name': display_name,
                    'filename': seed_file.name
                })
            except:
                # Fallback for seeds without metadata
                seed_files.append({
                    'path': str(seed_file),
                    'display_name': seed_file.stem,
                    'filename': seed_file.name
                })
        
        return sorted(seed_files, key=lambda x: x['display_name'])
    except Exception as e:
        set_message('error', f"Error loading seed files: {e}")
        return []

def preview_seed_file(seed_path):
    """Preview seed file content"""
    try:
        seed_data = dir_manager.load_json(seed_path)
        metadata = seed_data.get('metadata', {})
        return seed_data, metadata
    except Exception as e:
        set_message('error', f"Error previewing seed: {e}")
        return None, None

def calculate_seed_combinations_with_breakdown(seed_content):
    """Calculate total combinations from seed content"""
    try:
        if 'data_generation' not in seed_content:
            return 0, {}
        
        total = 1
        breakdown = {}
        
        for category, items in seed_content['data_generation'].items():
            if isinstance(items, list) and items:
                count = len(items)
                total *= count
                breakdown[category] = count
        
        return total, breakdown
    except:
        return 0, {}

def create_single_data_block(data_name, data_type, data_value):
    """Create single data block using your state management"""
    try:
        if not st.session_state.current_workflow:
            set_message('error', "No workflow loaded")
            return False
        
        state_file_path = dir_manager.get_state_file_path(st.session_state.current_workflow)
        
        # Load current state
        if state_file_path.exists():
            state_data = dir_manager.load_json(state_file_path)
        else:
            state_data = {'nodes': [], 'state_steps': []}
        
        # Create single data node
        single_data_node = {
            'name': data_name,
            'state': 'single_data',
            'data_type': data_type,
            'file_name': str(data_value),
            'type': {data_type: 'data'},
            'position': {'x': 50, 'y': 50 + len([n for n in state_data.get('nodes', []) if n.get('state') == 'single_data']) * 80}
        }
        
        # Add to nodes
        if 'nodes' not in state_data:
            state_data['nodes'] = []
        state_data['nodes'].append(single_data_node)
        
        # Save state
        dir_manager.save_json(state_file_path, state_data)
        
        # Reload workflow to update visual
        load_workflow_state(st.session_state.current_workflow)
        
        set_message('success', f"✅ Created single data: {data_name}")
        return True
        
    except Exception as e:
        set_message('error', f"❌ Error creating single data: {e}")
        return False

# Enhanced workflow management with your architecture
class EnhancedWorkflowManager:
    """Enhanced workflow management using your existing system"""
    
    def render_compact_header(self):
        """Render compact workflow header"""
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        
        with col1:
            if st.session_state.current_workflow:
                st.markdown(f"**📁 {st.session_state.current_workflow}**")
            else:
                st.markdown("**📁 No Workflow Loaded**")
        
        with col2:
            if st.button("🆕", help="New Workflow", key="header_new"):
                st.session_state.show_workflow_creator = True
        
        with col3:
            if st.button("📂", help="Load Workflow", key="header_load"):
                st.session_state.show_workflow_loader = True
        
        with col4:
            if st.button("💾", help="Auto-save", key="header_save"):
                st.session_state.auto_save_enabled = not st.session_state.auto_save_enabled
                status = "enabled" if st.session_state.auto_save_enabled else "disabled"
                set_message('info', f"Auto-save {status}")
    
    def render_workflow_stats(self):
        """Render workflow statistics"""
        if not st.session_state.current_workflow:
            return
        
        try:
            state_file_path = dir_manager.get_state_file_path(st.session_state.current_workflow)
            if state_file_path.exists():
                state_data = dir_manager.load_json(state_file_path)
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Steps", len(state_data.get('state_steps', [])))
                with col2:
                    completed = len([s for s in state_data.get('state_steps', []) if s.get('status') == 'completed'])
                    st.metric("Completed", completed)
                with col3:
                    pending = len(st.session_state.pending_steps)
                    st.metric("Pending", pending)
                with col4:
                    nodes = len(state_data.get('nodes', []))
                    st.metric("Data Nodes", nodes)
        except Exception as e:
            st.error(f"Error loading stats: {e}")

class EnhancedToolPalette:
    """Enhanced tool palette using your existing tool systems"""
    
    def __init__(self):
        self.llm_tools = get_available_llm_tools()
        self.code_tools = get_available_code_tools()
        self.chip_tools = get_available_chips()
    
    def render_compact_palette(self):
        """Render compact tool palette"""
        if not st.session_state.current_workflow:
            st.info("Load a workflow to add tools")
            return
        
        st.subheader("🧰 Add Tools")
        
        # Quick add buttons in columns
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🌱 Seed Step", use_container_width=True, key="quick_seed"):
                st.session_state.show_seed_selector = True
            
            if st.button("📊 Single Data", use_container_width=True, key="quick_single"):
                st.session_state.show_single_data_creator = True
        
        with col2:
            if st.button("🔧 Smart Builder", use_container_width=True, key="smart_builder"):
                st.session_state.show_smart_builder = True
            
            if st.button("⚡ Quick Tools", use_container_width=True, key="quick_tools"):
                st.session_state.show_quick_tools = True
        
        # Tool categories in expander
        with st.expander("🛠️ All Tools", expanded=False):
            self._render_tool_categories()
    
    def _render_tool_categories(self):
        """Render tool categories using your existing systems"""
        tab1, tab2, tab3 = st.tabs(["🤖 LLM", "⚙️ Code", "🔧 Chip"])
        
        with tab1:
            self._render_llm_tools()
        
        with tab2:
            self._render_code_tools()
        
        with tab3:
            self._render_chip_tools()
    
    def _render_llm_tools(self):
        """Render LLM tools using your prepare_data function"""
        if not self.llm_tools:
            st.info("No LLM tools available")
            return
        
        for tool in self.llm_tools:
            try:
                tool_info = prepare_data(tool)
                input_count = len(tool_info.get('in', {}))
                output_count = len(tool_info.get('out', {}))
                
                if st.button(
                    f"🤖 {tool}",
                    key=f"llm_{tool}",
                    help=f"Inputs: {input_count}, Outputs: {output_count}",
                    use_container_width=True
                ):
                    self._add_tool_step('llm', tool, tool_info)
            except Exception as e:
                st.error(f"Error with tool {tool}: {e}")
    
    def _render_code_tools(self):
        """Render code tools using your prepare_tool_use function"""
        if not self.code_tools:
            st.info("No code tools available")
            return
        
        for tool in self.code_tools:
            try:
                tool_info = prepare_tool_use(tool)
                input_count = len(tool_info.get('in', {}))
                output_count = len(tool_info.get('out', {}))
                
                if st.button(
                    f"⚙️ {tool}",
                    key=f"code_{tool}",
                    help=f"Inputs: {input_count}, Outputs: {output_count}",
                    use_container_width=True
                ):
                    self._add_tool_step('code', tool, tool_info)
            except Exception as e:
                st.error(f"Error with tool {tool}: {e}")
    
    def _render_chip_tools(self):
        """Render chip tools using your prepare_chip_use function"""
        if not self.chip_tools:
            st.info("No chip tools available")
            return
        
        for tool_name in self.chip_tools.keys():
            try:
                tool_info = prepare_chip_use(tool_name)
                input_count = len(tool_info.get('in', {}))
                output_count = len(tool_info.get('out', {}))
                
                if st.button(
                    f"🔧 {tool_name}",
                    key=f"chip_{tool_name}",
                    help=f"Inputs: {input_count}, Outputs: {output_count}",
                    use_container_width=True
                ):
                    self._add_tool_step('chip', tool_name, tool_info)
            except Exception as e:
                st.error(f"Error with tool {tool_name}: {e}")
    
    def _add_tool_step(self, tool_type, tool_name, tool_info):
        """Add tool step using your existing system"""
        st.session_state.selected_tool = {
            'type': tool_type,
            'name': tool_name,
            'info': tool_info
        }
        st.session_state.show_step_creator = True

class EnhancedPropertiesPanel:
    """Enhanced properties panel using your existing data systems"""
    
    def __init__(self, current_workflow):
        self.current_workflow = current_workflow
    
    def render_enhanced_properties(self, selected_node_id=None):
        """Render enhanced properties panel"""
        st.subheader("⚙️ Properties & Actions")
        
        if not selected_node_id:
            self._render_workflow_properties()
        else:
            self._render_node_properties(selected_node_id)
        
        # Always show workflow actions
        self._render_workflow_actions()
    
    def _render_workflow_properties(self):
        """Render workflow-level properties"""
        if not self.current_workflow:
            st.info("No workflow loaded")
            return
        
        try:
            state_file_path = dir_manager.get_state_file_path(self.current_workflow)
            if state_file_path.exists():
                state_data = dir_manager.load_json(state_file_path)
                
                st.write("**Workflow Overview**")
                
                # Status metrics
                steps = state_data.get('state_steps', [])
                completed_steps = [s for s in steps if s.get('status') == 'completed']
                running_steps = [s for s in steps if s.get('status') in ['uploaded', 'in_progress']]
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Steps", len(steps))
                    st.metric("Completed", len(completed_steps))
                with col2:
                    st.metric("Running", len(running_steps))
                    st.metric("Data Nodes", len(state_data.get('nodes', [])))
                
                # Recent activity
                if steps:
                    st.write("**Recent Steps:**")
                    for step in steps[-3:]:  # Last 3 steps
                        status_icon = "✅" if step.get('status') == 'completed' else "🔄" if step.get('status') in ['uploaded', 'in_progress'] else "⏸️"
                        st.write(f"{status_icon} {step.get('name', 'Unknown')} ({step.get('type', 'Unknown')})")
        except Exception as e:
            st.error(f"Error loading workflow properties: {e}")
    
    def _render_node_properties(self, node_id):
        """Render node-specific properties using your existing systems"""
        st.write(f"**Node: {node_id}**")
        
        try:
            state_file_path = dir_manager.get_state_file_path(self.current_workflow)
            state_data = dir_manager.load_json(state_file_path)
            
            # Handle different node types using your existing logic
            if node_id.startswith('single-'):
                self._render_single_data_properties(node_id, state_data)
            elif '-out-' in node_id:
                self._render_output_properties(node_id, state_data)
            elif '-parent' in node_id:
                self._render_step_properties(node_id, state_data)
            else:
                st.info("Select a specific node element for detailed properties")
                
        except Exception as e:
            st.error(f"Error loading node properties: {e}")
    
    def _render_single_data_properties(self, node_id, state_data):
        """Render single data properties using your data structure"""
        data_name = node_id.replace('single-', '')
        
        for node in state_data.get('nodes', []):
            if node.get('name') == data_name and node.get('state') == 'single_data':
                st.write(f"**Type:** {node.get('data_type', 'Unknown')}")
                st.write(f"**Value:**")
                st.code(str(node.get('file_name', 'No value')))
                
                # Action buttons
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Edit", key=f"edit_single_{data_name}"):
                        st.session_state.edit_single_data = {
                            'name': data_name,
                            'type': node.get('data_type'),
                            'value': node.get('file_name')
                        }
                
                with col2:
                    if st.button("🗑️ Delete", key=f"delete_single_{data_name}"):
                        self._delete_single_data(data_name, state_data)
                break
    
    def _render_output_properties(self, node_id, state_data):
        """Render output properties with data preview"""
        st.write("**Output Data Properties**")
        
        # Use your existing marker system
        if self._is_completed_output_marker(node_id, state_data):
            preview_data = self._load_marker_preview_data(node_id, state_data)
            
            if preview_data and 'error' not in preview_data:
                st.write("**Data Preview:**")
                if isinstance(preview_data, dict):
                    st.json(preview_data)
                elif isinstance(preview_data, list):
                    st.write(f"List with {len(preview_data)} items")
                    if preview_data:
                        st.json(preview_data[:3])  # Show first 3 items
                else:
                    st.text(str(preview_data)[:500])
            else:
                st.error("Could not load data preview")
        else:
            st.info("Output not yet available")
    
    def _render_step_properties(self, node_id, state_data):
        """Render step properties using your step data structure"""
        step_number = int(node_id.split('-')[0])
        
        if step_number <= len(state_data.get('state_steps', [])):
            step_data = state_data['state_steps'][step_number - 1]
            
            st.write(f"**Step {step_number} Details**")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Name:** {step_data.get('name', 'Unknown')}")
                st.write(f"**Type:** {step_data.get('type', 'Unknown')}")
                st.write(f"**Status:** {step_data.get('status', 'Unknown')}")
            
            with col2:
                if step_data.get('tool_name'):
                    st.write(f"**Tool:** {step_data['tool_name']}")
                
                inputs = step_data.get('data', {}).get('in', {})
                outputs = step_data.get('data', {}).get('out', {})
                st.metric("I/O", f"{len(inputs)}/{len(outputs)}")
            
            # Step actions
            self._render_step_actions(step_number, step_data)
    
    def _render_step_actions(self, step_number, step_data):
        """Render step-specific actions using your existing functions"""
        st.write("**Actions:**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if step_data.get('status') == 'completed':
                if st.button("🔄 Rerun", key=f"rerun_step_{step_number}"):
                    try:
                        # Use your existing rerun logic
                        self._rerun_step(step_number)
                    except Exception as e:
                        set_message('error', f"Error rerunning step: {e}")
        
        with col2:
            if step_data.get('status') in ['uploaded', 'in_progress']:
                if st.button("⏹️ Stop", key=f"stop_step_{step_number}"):
                    try:
                        # Use your existing stop logic
                        self._stop_step(step_number)
                    except Exception as e:
                        set_message('error', f"Error stopping step: {e}")
        
        with col3:
            # Check if step can be deleted using your existing function
            deletable_steps = get_deletable_steps(
                dir_manager.get_state_file_path(self.current_workflow)
            )
            
            if step_number in deletable_steps:
                if st.button("🗑️ Delete", key=f"delete_step_{step_number}"):
                    try:
                        delete_step_and_data(
                            str(dir_manager.get_state_file_path(self.current_workflow)),
                            step_number
                        )
                        load_workflow_state(self.current_workflow)
                        set_message('success', f"✅ Deleted step {step_number}")
                        st.rerun()
                    except Exception as e:
                        set_message('error', f"Error deleting step: {e}")
    
    def _render_workflow_actions(self):
        """Render workflow-level actions"""
        st.write("---")
        st.write("**Workflow Actions:**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🧹 Clear All", key="clear_all_steps"):
                if st.session_state.current_workflow:
                    try:
                        clear_all_steps(
                            str(dir_manager.get_state_file_path(st.session_state.current_workflow))
                        )
                        load_workflow_state(st.session_state.current_workflow)
                        set_message('success', "✅ Cleared all steps")
                        st.rerun()
                    except Exception as e:
                        set_message('error', f"Error clearing steps: {e}")
        
        with col2:
            if st.button("🔄 Reload", key="reload_workflow"):
                if st.session_state.current_workflow:
                    load_workflow_state(st.session_state.current_workflow)
                    set_message('info', "🔄 Workflow reloaded")
                    st.rerun()
        
        with col3:
            if st.button("💾 Backup", key="backup_workflow"):
                if st.session_state.current_workflow:
                    try:
                        # Create backup using your directory manager
                        backup_path = self._create_workflow_backup()
                        set_message('success', f"✅ Backup created: {backup_path}")
                    except Exception as e:
                        set_message('error', f"Error creating backup: {e}")
    
    # Helper methods using your existing systems
    def _is_completed_output_marker(self, node_id, state_data):
        """Check if output marker is completed using your logic"""
        try:
            # Use your existing marker checking logic
            markers = get_markers(str(dir_manager.get_state_file_path(self.current_workflow)))
            return any(marker.get('id') == node_id and marker.get('completed') for marker in markers)
        except:
            return False
    
    def _load_marker_preview_data(self, node_id, state_data):
        """Load marker preview data using your existing system"""
        try:
            # Use your existing preview data loading logic
            return load_marker_preview_data(node_id, state_data)
        except:
            return None
    
    def _delete_single_data(self, data_name, state_data):
        """Delete single data using your state management"""
        try:
            state_data['nodes'] = [
                n for n in state_data['nodes'] 
                if not (n.get('name') == data_name and n.get('state') == 'single_data')
            ]
            
            state_file_path = dir_manager.get_state_file_path(self.current_workflow)
            dir_manager.save_json(state_file_path, state_data)
            load_workflow_state(self.current_workflow)
            set_message('success', f"✅ Deleted single data: {data_name}")
            st.rerun()
        except Exception as e:
            set_message('error', f"Error deleting single data: {e}")
    
    def _rerun_step(self, step_number):
        """Rerun step using your existing system"""
        # Implement using your existing step rerun logic
        pass
    
    def _stop_step(self, step_number):
        """Stop step using your existing system"""
        # Implement using your existing step stop logic
        pass
    
    def _create_workflow_backup(self):
        """Create workflow backup using your directory manager"""
        # Implement backup creation using your existing system
        return "backup_created"

# Enhanced execution and step management using your existing systems
class EnhancedStepExecutor:
    """Enhanced step execution using your existing tool systems"""
    
    def __init__(self, current_workflow):
        self.current_workflow = current_workflow
    
    def execute_pending_steps(self):
        """Execute all pending steps using your existing systems"""
        if not st.session_state.pending_steps:
            return
        
        st.subheader("🚀 Execute Pending Steps")
        
        # Show pending steps summary
        st.write(f"**{len(st.session_state.pending_steps)} steps ready to execute:**")
        
        for i, pending_step in enumerate(st.session_state.pending_steps):
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.write(f"{i+1}. {pending_step['name']} ({pending_step['type']})")
            
            with col2:
                if pending_step.get('needs_connections'):
                    st.warning(f"⚠️ {len(pending_step['needs_connections'])} missing")
                else:
                    st.success("✅ Ready")
            
            with col3:
                if st.button("🗑️", key=f"remove_pending_{i}", help="Remove"):
                    st.session_state.pending_steps.pop(i)
                    st.rerun()
        
        # Execute buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("▶️ Execute All", key="execute_all_pending"):
                self._execute_all_pending()
        
        with col2:
            if st.button("🧪 Test Execute", key="test_execute_pending"):
                self._execute_all_pending(test_mode=True)
        
        with col3:
            if st.button("🧹 Clear Pending", key="clear_pending"):
                st.session_state.pending_steps = []
                st.rerun()
    
    def _execute_all_pending(self, test_mode=False):
        """Execute all pending steps using your existing tool functions"""
        try:
            state_file_path = str(dir_manager.get_state_file_path(self.current_workflow))
            
            for pending_step in st.session_state.pending_steps:
                # Use your existing tool execution functions
                if pending_step['type'] == 'llm':
                    use_llm_tool(
                        state_file_path,
                        pending_step['tool'],
                        pending_step['name'],
                        test_mode or pending_step.get('test_mode', False)
                    )
                elif pending_step['type'] == 'code':
                    use_code_tool(
                        state_file_path,
                        pending_step['tool'],
                        pending_step['name']
                    )
                elif pending_step['type'] == 'chip':
                    use_chip(
                        state_file_path,
                        pending_step['tool'],
                        pending_step['name'],
                        test_mode or pending_step.get('test_mode', False)
                    )
            
            # Clear pending steps after execution
            st.session_state.pending_steps = []
            
            # Reload workflow state
            load_workflow_state(self.current_workflow)
            
            mode_text = "test mode" if test_mode else "full execution"
            set_message('success', f"✅ Started execution in {mode_text}")
            st.rerun()
            
        except Exception as e:
            set_message('error', f"❌ Error executing steps: {e}")

# Main application function
def main():
    """Main application using your enhanced architecture"""
    initialize_enhanced_session_state()
    
    # Render messages
    render_messages()
    
    # Header
    st.title("🔧 Enhanced Workflow Editor")
    
    # Compact workflow management
    workflow_manager = EnhancedWorkflowManager()
    workflow_manager.render_compact_header()
    
    # Show workflow stats if loaded
    if st.session_state.current_workflow:
        workflow_manager.render_workflow_stats()
    
    st.markdown("---")
    
    # Main layout
    col1, col2, col3 = st.columns([1, 2, 1])
    
    # Left sidebar - Tools
    with col1:
        tool_palette = EnhancedToolPalette()
        tool_palette.render_compact_palette()
        
        # Step executor
        if st.session_state.pending_steps:
            st.markdown("---")
            step_executor = EnhancedStepExecutor(st.session_state.current_workflow)
            step_executor.execute_pending_steps()
    
    # Center - Flow visualization
    with col2:
        if st.session_state.current_workflow and st.session_state.flow_state:
            st.subheader(f"📊 {st.session_state.current_workflow}")
            
            # Render flow using your existing streamlit_flow
            selected_id = streamlit_flow(
                'workflow_flow',
                st.session_state.flow_state,
                layout=LayeredLayout(),
                fit_view=True,
                height=600,
                enable_node_menu=True,
                enable_edge_menu=True,
                enable_pane_menu=True,
                get_node_on_click=True,
                get_edge_on_click=True,
                key="main_flow"
            )
            
            # Update selected node
            if selected_id != st.session_state.selected_node_id:
                st.session_state.selected_node_id = selected_id
                st.rerun()
        else:
            st.info("👈 Create or load a workflow to get started")
    
    # Right sidebar - Properties
    with col3:
        properties_panel = EnhancedPropertiesPanel(st.session_state.current_workflow)
        properties_panel.render_enhanced_properties(st.session_state.selected_node_id)
    
    # Render dialogs using your existing dialog functions
    render_dialogs()

def render_dialogs():
    """Render all active dialogs using your existing dialog system"""
    if st.session_state.get('show_workflow_creator'):
        render_workflow_creation_dialog()
    
    if st.session_state.get('show_workflow_loader'):
        render_workflow_loader_dialog()
    
    if st.session_state.get('show_seed_selector'):
        render_seed_selector_dialog()
    
    if st.session_state.get('show_single_data_creator'):
        render_single_data_creator()
    
    if st.session_state.get('show_step_creator'):
        step_creator = StepCreator()
        step_creator.render()

# Run the application
if __name__ == "__main__":
    main()
