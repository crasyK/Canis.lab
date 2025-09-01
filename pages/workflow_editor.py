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
    use_chip
)
from lib.tools.llm import get_available_llm_tools, prepare_data
from lib.tools.code import get_available_code_tools, prepare_tool_use
from lib.tools.chip import get_available_chips, prepare_chip_use
from lib.tools.global_func import get_type, check_data_type, has_connection
from lib.directory_manager import dir_manager
import json
import os

# Page config
st.set_page_config(page_title="Workflow Editor", layout="wide")

# New UX Classes
class SmartStepBuilder:
    """Dropdown-based step creation interface"""
    
    def __init__(self, current_workflow):
        self.current_workflow = current_workflow
        self.available_llm_tools = get_available_llm_tools()
        self.available_code_tools = get_available_code_tools()
        self.available_chips = get_available_chips()  # Add this lin
    
    def render(self):
        """Main step builder interface"""
        st.subheader("🔧 Add New Step")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            tool_type = st.radio("Type:", ["LLM", "Code", "Chip"], horizontal=True)
            
            if tool_type == "Chip":
                available_tools = list(self.available_chips.keys())
            elif tool_type == "LLM":
                available_tools = self.available_llm_tools
            else:
                available_tools = self.available_code_tools
            
            selected_tool = st.selectbox(
                "Tool:", 
                options=["Select tool..."] + list(available_tools),
                key="tool_selector"
            )
        
        with col2:
            step_name = st.text_input(
                "Step Name:", 
                placeholder="Enter descriptive name...",
                key="step_name_input"
            )
            
            # Test mode toggle (only for LLM and Chip)
            if tool_type in ["LLM", "Chip"]:
                test_mode = st.checkbox(
                    "🧪 Test Mode (5 entries only)",
                    key="test_mode_toggle",
                    help="Run on sample data first"
                )
            else:
                test_mode = False
        
        # Smart connections (only if tool selected)
        if selected_tool != "Select tool...":
            connections = self.render_smart_connections(selected_tool, tool_type)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("➕ Add Step", disabled=not step_name):
                    self.add_step_with_connections(tool_type, selected_tool, step_name, connections, test_mode)
                    st.rerun()
            with col2:
                if st.button("🔄 Reset Form"):
                    # Clear form by refreshing keys
                    for key in ['tool_selector', 'step_name_input', 'test_mode_toggle']:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
    
    def render_smart_connections(self, tool_name, tool_type):
        """Render intelligent connection dropdowns"""
        # Get tool requirements based on type
        if tool_type == "LLM":
            tool_spec = prepare_data(tool_name)
        elif tool_type == "Code":
            tool_spec = prepare_tool_use(tool_name)
        else:  # Chip
            tool_spec = prepare_chip_use(tool_name)
        
        input_requirements = tool_spec.get('in', {})
        
        if not input_requirements:
            st.info("ℹ️ This tool doesn't require input connections")
            return {}
        
        st.write("**🔗 Input Connections:**")
        connections = {}
        
        for param_name, param_spec in input_requirements.items():
            connections[param_name] = self.render_connection_dropdown(param_name, param_spec)
        
        return {k: v for k, v in connections.items() if v}
    
    def render_connection_dropdown(self, param_name, param_spec):
        """Individual connection dropdown with smart filtering"""
        viable_sources = self.get_viable_sources(param_spec)
        needs_single_data = self.param_accepts_single_data(param_spec)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if viable_sources:
                options = ["Select source..."] + [
                    f"{src['step_name']}.{src['param_name']}" 
                    for src in viable_sources
                ]
                
                selected = st.selectbox(
                    f"**{param_name}**:",
                    options,
                    key=f"conn_{param_name}",
                    help=f"Type: {param_spec}"
                )
                
                if selected != "Select source...":
                    return selected
            else:
                st.warning(f"⚠️ No compatible sources for **{param_name}**")
        
        with col2:
            # Inline single data creation
            if needs_single_data and st.button(f"➕ Single", key=f"single_{param_name}"):
                return self.create_inline_single_data(param_name, param_spec)
        
        return None
    
    def get_viable_sources(self, param_spec):
        """Get list of viable data sources for a parameter with type checking"""
        state_file_path = dir_manager.get_state_file_path(self.current_workflow)
        if not state_file_path.exists():
            return []
        
        current_state_data = dir_manager.load_json(state_file_path)
        viable_sources = []
        
        # Check completed steps' outputs
        for step_data in current_state_data.get('state_steps', []):
            if step_data.get('status') == 'completed':
                for param_name, file_path in step_data.get('data', {}).get('out', {}).items():
                    # Get the actual data type from the node
                    node_info = self.find_node_by_file_path(file_path, current_state_data.get('nodes', []))
                    if node_info and self.is_type_compatible(node_info.get('type', {}), param_spec):
                        viable_sources.append({
                            'step_name': step_data.get('name', 'Unknown'),
                            'param_name': param_name,
                            'source_ref': f"{step_data.get('name', 'Unknown')}.{param_name}",
                            'data_type': node_info.get('type', {}),
                            'file_path': file_path
                        })
        
        # Check single data blocks
        for node in current_state_data.get('nodes', []):
            if (node.get('state') == 'single_data' and 
                self.is_type_compatible(node.get('type', {}), param_spec)):
                viable_sources.append({
                    'step_name': 'Single Data',
                    'param_name': node.get('name', 'Unknown'),
                    'source_ref': node.get('name', 'Unknown'),
                    'data_type': node.get('type', {}),
                    'is_single': True
                })
        
        return viable_sources

    def find_node_by_file_path(self, file_path, nodes):
        """Find node by its file path"""
        for node in nodes:
            if node.get('file_name') == file_path:
                return node
        return None

    def is_type_compatible(self, source_type, target_spec):
        """Check if source type is compatible with target specification"""
        try:
            from lib.tools.global_func import has_connection
            return has_connection(source_type, target_spec)
        except ImportError:
            # Fallback to basic type checking
            if isinstance(source_type, dict) and isinstance(target_spec, dict):
                # Check if there's any overlap in type keys
                return bool(set(source_type.keys()) & set(target_spec.keys()))
            return True  # Default to compatible if can't check
    
    def param_accepts_single_data(self, param_spec):
        """Check if parameter can accept single data input"""
        # Most parameters can accept single data
        return True
    
    def create_inline_single_data(self, param_name, param_spec):
        """Create single data inline with proper modal dialog"""
        # Set session state to show inline single data creation
        st.session_state[f'show_inline_single_{param_name}'] = True
        st.session_state[f'inline_param_spec_{param_name}'] = param_spec
        return None

    def render_inline_single_data_dialogs(self):
        """Render any active inline single data creation dialogs"""
        # Check for active inline single data dialogs
        for key in list(st.session_state.keys()):
            if key.startswith('show_inline_single_') and st.session_state[key]:
                param_name = key.replace('show_inline_single_', '')
                param_spec = st.session_state.get(f'inline_param_spec_{param_name}', {})
                
                with st.expander(f"🔧 Create Single Data for {param_name}", expanded=True):
                    self.render_single_data_form(param_name, param_spec)

    def render_single_data_form(self, param_name, param_spec):
        """Render single data creation form"""
        with st.form(f"inline_single_{param_name}"):
            # Determine expected data type from param_spec
            expected_types = list(param_spec.keys()) if isinstance(param_spec, dict) else ['string']
            
            data_name = st.text_input(
                "Data Name:",
                value=f"{param_name}_data",
                key=f"inline_name_{param_name}"
            )
            
            # Create appropriate input based on expected type
            data_value = self.create_typed_input(expected_types[0], param_name)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("✅ Create"):
                    if data_name and data_value is not None:
                        if create_single_data_block(data_name, expected_types[0], data_value):
                            # Clear the dialog
                            st.session_state[f'show_inline_single_{param_name}'] = False
                            if f'inline_param_spec_{param_name}' in st.session_state:
                                del st.session_state[f'inline_param_spec_{param_name}']
                            st.rerun()
            
            with col2:
                if st.form_submit_button("❌ Cancel"):
                    st.session_state[f'show_inline_single_{param_name}'] = False
                    if f'inline_param_spec_{param_name}' in st.session_state:
                        del st.session_state[f'inline_param_spec_{param_name}']
                    st.rerun()

    def create_typed_input(self, data_type, param_name):
        """Create appropriate input field based on data type"""
        if data_type == "string" or data_type == "str":
            return st.text_area(
                "String Value:",
                placeholder="Enter your text here...\nMultiple lines supported",
                key=f"inline_string_{param_name}",
                height=100
            )
        
        elif data_type == "integer" or data_type == "int":
            return st.number_input(
                "Integer Value:",
                value=0,
                step=1,
                key=f"inline_int_{param_name}"
            )
        
        elif data_type == "list":
            list_input = st.text_input(
                "List Items:",
                placeholder="item1, item2, item3",
                key=f"inline_list_{param_name}",
                help="Enter items separated by commas"
            )
            if list_input:
                items = [item.strip() for item in list_input.split(',') if item.strip()]
                st.caption(f"📋 Preview: {items} ({len(items)} items)")
                return items
            return []
        
        elif data_type == "json":
            json_input = st.text_area(
                "JSON Value:",
                placeholder='{\n  "key": "value",\n  "number": 123\n}',
                key=f"inline_json_{param_name}",
                height=120
            )
            if json_input:
                try:
                    import json
                    parsed = json.loads(json_input)
                    st.success("✅ Valid JSON")
                    return parsed
                except json.JSONDecodeError as e:
                    st.error(f"❌ Invalid JSON: {e}")
                    return None
            return None
        
        else:
            # Default to string input
            return st.text_input(
                f"{data_type.title()} Value:",
                key=f"inline_default_{param_name}"
            )
        
    def normalize_tool_requirements(self, tool_type, tool_name):
        """Normalize tool requirements to consistent dict format"""
        try:
            if tool_type == 'llm':
                tool_spec = prepare_data(tool_name)
            elif tool_type == 'code':
                tool_spec = prepare_tool_use(tool_name)
            else:  # chip
                tool_spec = prepare_chip_use(tool_name)
            
            input_req = tool_spec.get('in', {})
            output_req = tool_spec.get('out', {})
            
            # Normalize inputs
            if isinstance(input_req, list):
                input_req = {f"input_{i+1}": req for i, req in enumerate(input_req)} if input_req else {}
            
            # Normalize outputs
            if isinstance(output_req, list):
                if output_req:
                    output_req = {f"output_{i+1}": req for i, req in enumerate(output_req)}
                else:
                    output_req = {"output": {"json": "data"}}
            elif not output_req:
                output_req = {"output": {"json": "data"}}
            
            return input_req, output_req
            
        except Exception as e:
            print(f"❌ Error normalizing requirements for {tool_type}:{tool_name}: {e}")
            # Return safe defaults
            return {}, {"output": {"json": "data"}}

        
    def create_step_instance_for_pending(self, pending_step):
        """Create step instance and add to visual flow"""
        try:
            from lib.app_objects import step
            
            # Get current state data for nodes info
            state_file_path = dir_manager.get_state_file_path(st.session_state.current_workflow)
            if state_file_path.exists():
                current_state_data = dir_manager.load_json(state_file_path)
                current_markers = current_state_data.get('nodes', [])
            else:
                current_markers = []
            
            # Get normalized requirements
            input_requirements, output_requirements = self.normalize_tool_requirements(
                pending_step['type'], 
                pending_step['tool']
            )
            
            # Create markers_map based on requirements
            markers_map = {
                'in': len(input_requirements) if input_requirements else 0,
                'out': len(output_requirements) if output_requirements else 1
            }
            
            # Create step data structure with proper dict format
            step_data = {
                'in': input_requirements,
                'out': output_requirements
            }
            
            # Calculate position
            position_x = 100 + (pending_step['step_number'] - 1) * 300
            position_y = 100
            
            # Create step instance
            step_instance = step(
                markers_map=markers_map,
                step_type=pending_step['type'],
                status='pending',
                step_data=step_data,
                step_name=pending_step['name'],
                nodes_info=current_markers
            )
            
            # Override step number to match pending step
            step_instance.step_number = pending_step['step_number']
            step.instances[pending_step['step_number']] = step_instance
            
            # Store step instance in pending step for later use
            pending_step['step_instance'] = step_instance
            pending_step['position'] = (position_x, position_y)
            
            # Update visual flow
            update_flow_with_pending_steps()
            
            print(f"✅ Created step instance for {pending_step['name']} with {len(input_requirements)} inputs and {len(output_requirements)} outputs")
            
        except Exception as e:
            print(f"❌ Error creating step instance: {e}")
            import traceback
            traceback.print_exc() 

    
    def add_step_with_connections(self, tool_type, tool_name, step_name, connections, test_mode):
        """Add step to pending with proper type handling"""
        if not hasattr(st.session_state, 'pending_steps'):
            st.session_state.pending_steps = []
        
        # Get requirements based on tool type
        if tool_type == "LLM":
            requirements = prepare_data(tool_name).get('in', {})
        elif tool_type == "Code":
            requirements = prepare_tool_use(tool_name).get('in', {})
        else:  # Chip
            requirements = prepare_chip_use(tool_name).get('in', {})
        
        # Calculate proper step number based on existing workflow state
        state_file_path = dir_manager.get_state_file_path(st.session_state.current_workflow)
        if state_file_path.exists():
            current_state_data = dir_manager.load_json(state_file_path)
            existing_steps_count = len(current_state_data.get('state_steps', []))
        else:
            existing_steps_count = 0
        
        # Step number should be: existing completed steps + current pending steps + 1
        step_number = existing_steps_count + len(st.session_state.pending_steps) + 1
        
        print(f"DEBUG STEP CALCULATION:")
        print(f"  - Existing completed steps: {existing_steps_count}")
        print(f"  - Current pending steps: {len(st.session_state.pending_steps)}")
        print(f"  - Calculated step_number: {step_number}")
        
        # Create pending step
        pending_step = {
            'name': step_name,
            'type': tool_type.lower(),  # "llm", "code", or "chip"
            'tool': tool_name,
            'test_mode': test_mode,
            'connections': connections,
            'input_requirements': requirements,
            'needs_connections': [req for req in requirements.keys() if req not in connections],
            'step_number': step_number  # Use calculated step number
        }
        
        st.session_state.pending_steps.append(pending_step)
        
        # Clear all edges when adding a new pending step to avoid stale connections
        if hasattr(st.session_state, 'flow_state') and st.session_state.flow_state:
            print(f"🧹 Clearing {len(st.session_state.flow_state.edges)} existing edges")
            st.session_state.flow_state.edges = []
        
        # Create step instance and add to visual flow
        self.create_step_instance_for_pending(pending_step)

        self.create_visual_edges_from_connections(pending_step, connections)
        
        set_message('success', f"✅ Added {tool_type} step: {step_name}")
        
        print(f"DEBUG: Added pending step '{step_name}' with step_number {step_number}")

    def create_visual_edges_from_connections(self, pending_step, connections):
        """Convert step builder connections to visual flow edges"""
        if not connections or not hasattr(st.session_state, 'flow_state'):
            return
            
        from streamlit_flow.elements import StreamlitFlowEdge
        
        # Get current state data for source lookup
        state_file_path = dir_manager.get_state_file_path(st.session_state.current_workflow)
        if state_file_path.exists():
            current_state_data = dir_manager.load_json(state_file_path)
        else:
            return
        
        new_edges = []
        step_number = pending_step['step_number']
        input_requirements = pending_step.get('input_requirements', {})
        param_names = list(input_requirements.keys())
        
        print(f"🔗 Creating visual edges for step {step_number} with connections: {connections}")
        
        for param_name, source_value in connections.items():
            if not source_value:
                continue
                
            # Find the input index for this parameter
            try:
                param_index = param_names.index(param_name) + 1  # 1-based for visual flow
            except ValueError:
                continue
                
            # Create target ID
            target_id = f"{step_number}-in-{param_index}"
            
            # FIX: Clean up source_value - remove "Single Data." prefix
            if source_value.startswith("Single Data."):
                clean_source_value = source_value.replace("Single Data.", "")
            else:
                clean_source_value = source_value
            
            # Create proper source ID
            source_id = f"single-{clean_source_value}"
            
            # Create edge
            edge_id = f"builder-edge-{clean_source_value}-to-{target_id}"
            edge = StreamlitFlowEdge(
                edge_id,
                source_id,
                target_id,
                style={'stroke': '#4CAF50', 'strokeWidth': 2}
            )
            
            new_edges.append(edge)
            print(f"✅ Created edge: {source_id} -> {target_id}")
        
        # Add edges to flow state
        if new_edges:
            if not st.session_state.flow_state.edges:
                st.session_state.flow_state.edges = []
            st.session_state.flow_state.edges.extend(new_edges)
            print(f"🔗 Added {len(new_edges)} visual edges to flow")
            
            # Force flow refresh
            st.session_state.flow_state = st.session_state.flow_state






class DataPreview:
    """Data preview panel for clicked nodes"""
    
    def __init__(self, current_workflow):
        self.current_workflow = current_workflow
    
    def render_preview_panel(self, selected_node_id=None):
        """Render data preview at bottom"""
        if not selected_node_id:
            st.info("👆 Click on a node above to preview its data")
            return
        
        st.subheader(f"🔍 Data Preview: {selected_node_id}")
        
        try:
            sample_data = self.get_sample_data(selected_node_id)
            
            if sample_data:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Type", sample_data.get('type', 'Unknown'))
                with col2:
                    st.metric("Total Items", sample_data.get('total_count', 0))
                with col3:
                    st.metric("Showing", min(5, sample_data.get('total_count', 0)))
                
                st.write("**Sample Data:**")
                if sample_data['type'] == 'json':
                    st.json(sample_data['sample'])
                else:
                    for i, item in enumerate(sample_data['sample'][:5]):
                        st.text(f"{i}: {str(item)[:100]}{'...' if len(str(item)) > 100 else ''}")
        except Exception as e:
            st.error(f"Error loading preview: {e}")
    
    def get_sample_data(self, node_id):
        """Get sample data for preview from node ID"""
        try:
            # Load current state
            state_file_path = dir_manager.get_state_file_path(self.current_workflow)
            current_state_data = dir_manager.load_json(state_file_path)
            
            # Use existing preview logic
            if is_completed_output_marker(node_id, current_state_data):
                data = load_marker_preview_data(node_id, current_state_data)
                if 'error' not in data:
                    return {
                        'type': 'json',
                        'sample': data,
                        'total_count': len(data) if isinstance(data, (dict, list)) else 1
                    }
            
            return None
        except Exception as e:
            return None

def show_persistent_message():
    """Display persistent messages that survive page reloads"""
    if 'message' in st.session_state and st.session_state.message:
        msg_type = st.session_state.message.get('type', 'info')
        msg_text = st.session_state.message.get('text', '')
        if msg_type == 'success':
            st.success(msg_text)
        elif msg_type == 'error':
            st.error(msg_text)
        elif msg_type == 'warning':
            st.warning(msg_text)
        elif msg_type == 'info':
            st.info(msg_text)
        # Clear message after showing
        st.session_state.message = None

def set_message(message_type, text):
    """Set a message that persists through reloads"""
    st.session_state.message = {'type': message_type, 'text': text}

if 'current_workflow' not in st.session_state:
    st.session_state.current_workflow = None
if 'flow_state' not in st.session_state:
    st.session_state.flow_state = None
if 'pending_steps' not in st.session_state:
    st.session_state.pending_steps = []

# Initialize preview state
if 'selected_marker_data' not in st.session_state:
    st.session_state.selected_marker_data = None
if 'selected_marker_name' not in st.session_state:
    st.session_state.selected_marker_name = None
if 'show_preview' not in st.session_state:
    st.session_state.show_preview = False
if 'show_seed_dialog' not in st.session_state:
    st.session_state.show_seed_dialog = False
if 'show_llm_dialog' not in st.session_state:
    st.session_state.show_llm_dialog = False
if 'show_code_dialog' not in st.session_state:
    st.session_state.show_code_dialog = False
if 'show_run_dialog' not in st.session_state:
    st.session_state.show_run_dialog = False
if 'show_create_workflow_dialog' not in st.session_state:
    st.session_state.show_create_workflow_dialog = False
if 'show_single_data_dialog' not in st.session_state:
    st.session_state.show_single_data_dialog = False
if 'selected_marker_data' not in st.session_state:
    st.session_state.selected_marker_data = None
if 'selected_marker_name' not in st.session_state:
    st.session_state.selected_marker_name = None
if 'test_mode_enabled' not in st.session_state:
    st.session_state.test_mode_enabled = False
if 'retry_test' not in st.session_state:
    st.session_state.retry_test = False

def get_available_seed_files():
    """Get list of available seed files from seed_files directory"""
    return dir_manager.list_seed_files()

def preview_seed_file(file_path):
    """Preview seed file content"""
    try:
        with open(file_path, 'r') as f:
            seed_data = json.load(f)
        # Extract actual seed if it's a progress file
        if 'seed_file' in seed_data:
            actual_seed = seed_data['seed_file']
            metadata = {
                'created': seed_data.get('timestamp', 'Unknown'),
                'conversation_length': seed_data.get('conversation_length', 0)
            }
        else:
            actual_seed = seed_data
            metadata = None
        return actual_seed, metadata
    except Exception as e:
        st.error(f"Error reading seed file: {e}")
        return None, None

def is_completed_output_marker(node_id, current_state_data):
    """Check if a node represents a completed output marker"""
    if not ('-out-' in node_id):
        return False
    
    # Extract step number from node ID
    step_number = int(node_id.split('-')[0])
    
    # Check if step exists and is completed
    if step_number <= len(current_state_data.get('state_steps', [])):
        step_data = current_state_data['state_steps'][step_number - 1]
        return step_data.get('status') == 'completed'
    
    return False

def load_marker_preview_data(node_id, current_state_data):
    """Load one sample entry from marker data file with path resolution"""
    try:
        # Extract step number and output index
        parts = node_id.split('-')
        step_number = int(parts[0])
        output_index = int(parts[2])
        
        # Get step data
        if step_number <= len(current_state_data.get('state_steps', [])):
            step_data = current_state_data['state_steps'][step_number - 1]
            output_data = step_data.get('data', {}).get('out', {})
            
            # Get the specific output marker
            output_keys = list(output_data.keys())
            if output_index <= len(output_keys):
                marker_key = output_keys[output_index - 1]
                marker_file_path = output_data[marker_key]
                
                # Use path resolution instead of manual path construction
                resolved_path = dir_manager.resolve_path(marker_file_path)
                
                if resolved_path and resolved_path.exists():
                    with open(resolved_path, 'r') as f:
                        data = json.load(f)
                    
                    # Return one sample entry based on data structure
                    if isinstance(data, dict) and data:
                        first_key = next(iter(data.keys()))
                        return {first_key: data[first_key]}
                    elif isinstance(data, list) and data:
                        return data[0] if data else {}
                    else:
                        return data
                else:
                    return {
                        "error": f"Data file not found: {marker_file_path}",
                        "debug_info": {
                            "original_path": marker_file_path,
                            "resolved_path": str(resolved_path) if resolved_path else "None"
                        }
                    }
        
        return {"error": "Could not resolve marker data"}
        
    except Exception as e:
        return {"error": f"Could not load data: {str(e)}"}



def get_marker_display_name(node_id, current_state_data):
    """Get display name for a marker from node ID"""
    try:
        # Extract step number and output index
        parts = node_id.split('-')
        step_number = int(parts[0])
        output_index = int(parts[2])
        
        # Get step data
        if step_number <= len(current_state_data.get('state_steps', [])):
            step_data = current_state_data['state_steps'][step_number - 1]
            output_data = step_data.get('data', {}).get('out', {})
            
            # Get the specific output marker key
            output_keys = list(output_data.keys())
            if output_index <= len(output_keys):
                marker_key = output_keys[output_index - 1]
                step_name = step_data.get('name', f'Step {step_number}')
                return f"{step_name} → {marker_key}"
        
        return f"Output {node_id}"
        
    except Exception as e:
        return f"Marker {node_id}"

def handle_marker_click(node_id, current_state_data):
    """Handle marker preview directly from state data"""
    if not node_id or '-out-' not in node_id:
        return False
    
    # Parse the node ID: format is {step_number}-out-{counter}
    parts = node_id.split('-')
    if len(parts) < 3:
        return False
        
    try:
        step_number = int(parts[0]) - 1  # Convert to 0-based index
        marker_counter = int(parts[2]) - 1  # Convert to 0-based index
    except ValueError:
        st.error("Invalid node ID format")
        return False
    
    # Get the step data directly from state
    steps = current_state_data.get('state_steps', [])
    if step_number >= len(steps):
        st.error(f"Step {step_number + 1} not found")
        return False
    
    step_data = steps[step_number]
    output_data = step_data.get('data', {}).get('out', {})
    
    if not output_data:
        st.warning("No output data found for this step")
        return False
    
    # Get the marker by counter
    marker_keys = list(output_data.keys())
    if marker_counter >= len(marker_keys):
        st.error(f"Marker {marker_counter + 1} not found")
        return False
    
    marker_key = marker_keys[marker_counter]
    file_path = output_data[marker_key]
    
    # Get the display name from nodes data
    nodes = current_state_data.get('nodes', [])
    display_name = get_marker_display_name_from_nodes(marker_key, file_path, nodes)
    
    # Load and show the preview data
    preview_data = load_marker_preview_data(file_path)
    show_marker_preview(display_name, preview_data, marker_key)
    
    return True

def get_marker_display_name_from_nodes(marker_key, file_path, nodes):
    """Get display name from nodes data"""
    # First, try to find by file path
    for node in nodes:
        if node.get('file_name') == file_path:
            return node.get('name', marker_key)
    
    # If not found by file path, try by marker name
    for node in nodes:
        if node.get('name') == marker_key:
            return node.get('display_name', marker_key)
    
    # Fallback to marker key
    return marker_key

def load_marker_preview_data(file_path, sample_size=5):
    """Load preview data from marker file path"""
    try:
        # Handle single data (non-file paths)
        if isinstance(file_path, str) and not file_path.startswith('runs/') and not file_path.endswith(('.json', '.jsonl')):
            return {
                'type': 'single',
                'sample': [file_path],
                'total_count': 1
            }
        
        # Handle file path resolution
        final_path = file_path
        if not os.path.exists(final_path):
            return {
                'type': 'error',
                'sample': [f"File not found: {file_path}"],
                'total_count': 0
            }
        
        # Load the data
        with open(final_path, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            sample_items = list(data.items())[:sample_size]
            return {
                'type': 'json',
                'sample': dict(sample_items),
                'total_count': len(data),
                'file_path': final_path
            }
        elif isinstance(data, list):
            return {
                'type': 'list',
                'sample': data[:sample_size],
                'total_count': len(data),
                'file_path': final_path
            }
        else:
            return {
                'type': 'single',
                'sample': [data],
                'total_count': 1,
                'file_path': final_path
            }
            
    except json.JSONDecodeError as e:
        return {
            'type': 'error',
            'sample': [f"JSON decode error: {str(e)}"],
            'total_count': 0
        }
    except Exception as e:
        return {
            'type': 'error',
            'sample': [f"Error loading data: {str(e)}"],
            'total_count': 0
        }

def show_marker_preview(display_name, preview_data, marker_key):
    """Show the marker preview in UI"""
    if not preview_data:
        st.warning(f"No preview data available for {display_name}")
        return
    
    # Store in session state for the render section to display
    st.session_state.selected_marker_data = preview_data
    st.session_state.selected_marker_name = display_name
    st.session_state.show_preview = True

def render_data_preview_section():
    """Render data preview section using the simplified approach"""
    if (st.session_state.get('selected_marker_data') is not None and 
        st.session_state.get('selected_marker_name') is not None):
        st.divider()
        
        preview_data = st.session_state.selected_marker_data
        display_name = st.session_state.selected_marker_name or 'Unknown'
        
        with st.expander(f"📊 Data Preview: {display_name}", expanded=True):
            # Header with metrics
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.subheader("Sample Data")
                data_type = preview_data.get('type', 'unknown')
                st.caption(f"Type: {data_type.upper()}")
            
            with col2:
                total_count = preview_data.get('total_count', 0)
                st.metric("Total Entries", total_count)
                sample_count = len(preview_data.get('sample', []))
                st.caption(f"Showing {sample_count} of {total_count}")
            
            with col3:
                if st.button("❌ Clear", key="clear_preview", type="secondary"):
                    # Force clear all preview-related session state
                    keys_to_clear = ['selected_marker_data', 'selected_marker_name', 'show_preview']
                    for key in keys_to_clear:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.success("Preview cleared!")
                    st.rerun()
            
            # Display the actual data
            sample = preview_data.get('sample', [])
            data_type = preview_data.get('type', 'unknown')
            
            if data_type == 'error':
                st.error(sample[0] if sample else "Unknown error")
            elif data_type == 'json' and isinstance(sample, dict):
                st.json(sample)
            elif data_type == 'list' and isinstance(sample, list):
                if len(sample) == 0:
                    st.info("Empty list")
                else:
                    for i, item in enumerate(sample):
                        with st.container():
                            st.write(f"**Entry {i+1}:**")
                            if isinstance(item, dict):
                                st.json(item)
                            else:
                                st.code(str(item))
                            if i < len(sample) - 1:
                                st.divider()
            elif data_type == 'single':
                st.code(str(sample[0]) if sample else "No data")
            else:
                st.code(str(sample))
            
            # Show file path if available
            if preview_data.get('file_path'):
                with st.expander("📁 File Information", expanded=False):
                    st.code(preview_data['file_path'])
                    if os.path.exists(preview_data['file_path']):
                        try:
                            file_size = os.path.getsize(preview_data['file_path'])
                            st.caption(f"File size: {file_size:,} bytes")
                        except:
                            st.caption("File size: Unable to determine")

def calculate_seed_combinations_with_breakdown(seed_data):
    """Calculate total combinations and provide detailed breakdown"""
    from lib.tools.seed import normalize_variables, generate_entries
    
    variables = seed_data.get('variables', {})
    
    if not variables:
        return 0, []
    
    try:
        # Use existing seed calculation logic
        dimensions = normalize_variables(variables)
        entries = generate_entries(dimensions)
        total_combinations = len(entries)
        
        # Create breakdown details
        breakdown_details = []
        
        for var_name, var_value in variables.items():
            if isinstance(var_value, list):
                count = len(var_value)
                breakdown_details.append(f"{var_name}: {count} options")
                
            elif isinstance(var_value, dict):
                # For nested structures, count branches and total leaf values
                branch_count = len(var_value.keys())
                total_leaf_count = sum(len(flatten_leaves(branch_val)) for branch_val in var_value.values())
                
                breakdown_details.append(f"{var_name}_key: {branch_count} categories")
                breakdown_details.append(f"{var_name}_value: {total_leaf_count} total values")
                
            else:
                # Scalar value
                breakdown_details.append(f"{var_name}: 1 option")
        
        return total_combinations, breakdown_details
        
    except Exception as e:
        return 0, [f"Error calculating combinations: {str(e)}"]

def flatten_leaves(value):
    """Recursively flatten nested structures to count leaf values"""
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(flatten_leaves(item))
        return result
    elif isinstance(value, dict):
        result = []
        for k, v in value.items():
            result.extend(flatten_leaves(v))
        return result
    else:
        return [value]

def sample_input_data_for_test(connections, current_state_data, max_entries=5):
    """Sample random entries from connected data sources for testing"""
    import random
    sampled_data = {}
    
    for param_name, data_source in connections.items():
        try:
            # Handle single data blocks
            for node in current_state_data.get('nodes', []):
                if node.get('name') == data_source and node.get('state') == 'single_data':
                    sampled_data[param_name] = node.get('file_name')  # Single value
                    break
            else:
                # Handle file-based data
                # Find the node with this name
                marker_node = None
                for node in current_state_data.get('nodes', []):
                    if node.get('name') == data_source:
                        marker_node = node
                        break
                
                if marker_node:
                    workflow_name = current_state_data.get('name', 'unknown')
                    full_file_path = dir_manager.get_workflow_path(workflow_name) / marker_node['file_name']
                    
                    if full_file_path.exists():
                        with open(full_file_path, 'r') as f:
                            full_data = json.load(f)
                        
                        if isinstance(full_data, dict):
                            # Sample random keys from dictionary
                            available_keys = list(full_data.keys())
                            sample_size = min(max_entries, len(available_keys))
                            sampled_keys = random.sample(available_keys, sample_size)
                            sampled_data[param_name] = {k: full_data[k] for k in sampled_keys}
                            
                        elif isinstance(full_data, list):
                            # Sample random items from list
                            sample_size = min(max_entries, len(full_data))
                            sampled_data[param_name] = random.sample(full_data, sample_size)
                            
                        else:
                            # Single value data
                            sampled_data[param_name] = full_data
                    else:
                        sampled_data[param_name] = f"Error: File not found"
                else:
                    sampled_data[param_name] = f"Error: Data source '{data_source}' not found"
                    
        except Exception as e:
            print(f"Error sampling data for {param_name}: {e}")
            sampled_data[param_name] = f"Error: {str(e)}"
    
    return sampled_data

def add_test_step(step_type, step_name, tool_name):
    """Add a test step with proper input/output marker mapping"""
    test_step_name = f"test_{step_name}"
    add_pending_step(step_type, test_step_name, tool_name)

def create_single_data_edges_from_state(state_data, flow_state):
    """Recreate edges for single data connections based on workflow state"""
    from streamlit_flow.elements import StreamlitFlowEdge
    
    edges = list(flow_state.edges) if flow_state.edges else []
    
    # Look through completed steps to find single data usage
    for step in state_data.get('state_steps', []):
        step_inputs = step.get('data', {}).get('in', {})
        
        # Find which step number this corresponds to
        step_name = step.get('name', '')
        step_number = None
        
        # Find the step number from existing nodes
        for node in flow_state.nodes:
            if 'parent' in node.id and node.data.get('content') == step_name:
                step_number = node.id.split('-')[0]
                break
        
        if step_number:
            # Check each input to see if it's a single data reference
            input_index = 1
            for input_key, input_value in step_inputs.items():
                # Check if this input references a single data node
                for single_node in state_data.get('nodes', []):
                    if (single_node.get('state') == 'single_data' and 
                        single_node.get('name') == input_value):
                        
                        # Create edge from single data node to step input
                        source_id = f"single-{single_node['name']}"
                        target_id = f"{step_number}-in-{input_index}"
                        edge_id = f"restored-edge-{source_id}-to-{target_id}"
                        
                        # Check if edge already exists
                        edge_exists = any(e.source == source_id and e.target == target_id 
                                        for e in edges)
                        
                        if not edge_exists:
                            edge = StreamlitFlowEdge(
                                edge_id,
                                source_id,
                                target_id,
                                style={'stroke': '#4CAF50', 'strokeWidth': 2}
                            )
                            edges.append(edge)
                            print(f"DEBUG: Restored single data edge: {source_id} -> {target_id}")
                
                input_index += 1
    
    return edges

def load_workflow_state(workflow_name):
    """Load workflow state and recreate visual flow with proper edge restoration"""
    try:
        # Clear any existing state first
        if 'pending_steps' in st.session_state:
            st.session_state.pending_steps = []
        
        # Load state file
        state_file_path = dir_manager.get_state_file_path(workflow_name)
        if not state_file_path.exists():
            set_message('error', f"❌ Workflow state file not found: {workflow_name}")
            return None
            
        state_data = dir_manager.load_json(state_file_path)
        
        # Create step instances and nodes from ALL steps (not just completed ones)
        from lib.app_objects import step
        step.reset_class_state()  # Clear existing instances
        
        nodes = []
        for step_data in state_data.get('state_steps', []):
            # Remove the status filter - show ALL steps
            # if step_data.get('status') == 'completed':  # <-- REMOVE THIS LINE
            
            # Calculate markers_map from step data
            inputs = step_data.get('data', {}).get('in', {})
            outputs = step_data.get('data', {}).get('out', {})
            markers_map = {'in': len(inputs), 'out': len(outputs)}
            
            step_instance = step(
                markers_map=markers_map,
                step_type=step_data.get('type', 'code'),
                status=step_data.get('status', 'completed'),  # Pass the actual status
                step_data=step_data.get('data', {}),
                step_name=step_data.get('name', f'Step {len(nodes)+1}'),
                nodes_info=state_data.get('nodes', [])
            )
            nodes.extend(step_instance.return_step())
        
        # Create single data nodes
        single_data_nodes = create_single_data_nodes_from_state(state_data)
        nodes.extend(single_data_nodes)
        
        # Create edges between steps
        edges = step.create_edges_between_steps()
        
        # Create initial flow state
        from streamlit_flow import StreamlitFlowState
        flow_state = StreamlitFlowState(nodes, edges)
        
        # IMPORTANT: Restore single data edges
        restored_edges = create_single_data_edges_from_state(state_data, flow_state)
        flow_state.edges = restored_edges
        
        # Update session state
        st.session_state.flow_state = flow_state
        st.session_state.current_workflow = workflow_name
        
        print(f"✅ Loaded workflow: {workflow_name}")
        print(f"DEBUG: Created {len(nodes)} nodes and {len(restored_edges)} edges")
        
        return state_data
        
    except Exception as e:
        set_message('error', f"❌ Error loading workflow: {e}")
        print(f"❌ Error loading workflow {workflow_name}: {e}")
        import traceback
        traceback.print_exc()
        return None



def save_single_data_connections_to_state(state_file_path, connections):
    """Save single data connections to the workflow state file"""
    try:
        state_data = dir_manager.load_json(state_file_path)
        
        # Add single data connections to each step's input data
        for step in state_data.get('state_steps', []):
            step_name = step.get('name', '')
            if step_name in connections:
                step_connections = connections[step_name]
                
                # Update the step's input data to include single data references
                if 'data' not in step:
                    step['data'] = {}
                if 'in' not in step['data']:
                    step['data']['in'] = {}
                
                # Add single data connections to the step's input data
                for param_name, source_value in step_connections.items():
                    # Check if this is a single data reference
                    for node in state_data.get('nodes', []):
                        if (node.get('state') == 'single_data' and 
                            node.get('name') == source_value):
                            step['data']['in'][param_name] = source_value
                            print(f"DEBUG: Saved single data connection: {step_name}.{param_name} = {source_value}")
        
        # Save updated state
        dir_manager.save_json(state_file_path, state_data)
        print("✅ Saved single data connections to state file")
        
    except Exception as e:
        print(f"❌ Error saving single data connections: {e}")


def apply_visual_states(nodes, state_data):
    """Apply visual states to nodes based on step status"""
    for node in nodes:
        if 'parent' in node.id:  # Step nodes
            step_number = int(node.id.split('-')[0])
            if step_number <= len(state_data['state_steps']):
                step_data = state_data['state_steps'][step_number - 1]
                status = step_data.get('status', 'idle')
                # Apply visual styling based on status
                if status == 'completed':
                    node.data['style'] = {'backgroundColor': '#d4edda', 'opacity': '0.8'}
                elif status == 'failed':
                    node.data['style'] = {'backgroundColor': '#f8d7da', 'opacity': '0.8'}
                elif status in ['uploaded', 'in_progress']:
                    node.data['style'] = {'backgroundColor': '#fff3cd', 'opacity': '0.9'}
                else:
                    node.data['style'] = {'backgroundColor': '#ffffff', 'opacity': '1.0'}
    return nodes

def get_available_runs():
    """Get list of available workflow runs"""
    return dir_manager.list_workflows()

def create_new_workflow(workflow_name):
    """Create a new workflow"""
    try:
        # Ensure workflow directory exists
        dir_manager.ensure_workflow_directory(workflow_name)
        
        # Create initial state
        state_file_path = dir_manager.get_state_file_path(workflow_name)
        create_state(str(state_file_path), workflow_name)
        
        # Load the new workflow
        state_data = load_workflow_state(workflow_name)
        if state_data:
            set_message('success', f"✅ Created new workflow: {workflow_name}")
            return True
        return False
    except Exception as e:
        set_message('error', f"❌ Error creating workflow: {e}")
        return False

def add_pending_step(step_type, step_name, tool_name):
    """Add a step with proper input/output marker mapping"""
    print(f"🔧 Adding pending step: {step_name} ({step_type}: {tool_name})")
    
    if not st.session_state.current_workflow:
        set_message('error', "❌ No workflow selected. Please select or create a workflow first.")
        return

    if 'pending_steps' not in st.session_state:
        st.session_state.pending_steps = []

    try:
        # Get current state data
        state_file_path = dir_manager.get_state_file_path(st.session_state.current_workflow)
        if not state_file_path.exists():
            set_message('error', f"❌ State file not found for workflow: {st.session_state.current_workflow}")
            return

        current_state_data = dir_manager.load_json(state_file_path)
        
        # Calculate next step number
        existing_steps = len(current_state_data.get('state_steps', []))
        pending_steps_count = len(st.session_state.pending_steps)
        next_step_number = existing_steps + pending_steps_count + 1

        # 🔧 GET TOOL REQUIREMENTS (This was missing!)
        if step_type == 'llm':
            tool_spec = prepare_data(tool_name)
        else:  # code
            tool_spec = prepare_tool_use(tool_name)
        
        print(f"📋 Tool spec for {tool_name}: {tool_spec}")
        
        # Extract input and output requirements
        input_requirements = tool_spec.get('in', {})
        output_requirements = tool_spec.get('out', {})
        
        print(f"🔌 Input requirements: {input_requirements}")
        print(f"📤 Output requirements: {output_requirements}")
        
        # Create markers_map based on tool requirements
        markers_map = {
            'in': len(input_requirements) if input_requirements else 1,
            'out': len(output_requirements) if output_requirements else 1
        }
        
        print(f"📍 Created markers_map: {markers_map}")
        
        # Create step data with proper input/output structure
        step_data = {
            'name': step_name,
            'type': step_type,
            'tool_name': tool_name,
            'status': 'pending',
            'in': input_requirements,  # 🔧 Use actual tool requirements
            'out': output_requirements  # 🔧 Use actual tool requirements
        }
        
        # Calculate position
        position_x = 100 + (next_step_number - 1) * 300
        position_y = 100
        
        # Get current markers for the step instance
        current_markers = current_state_data.get('nodes', [])
        
        # Create step instance with correct parameters
        from lib.app_objects import step
        
        step_instance = step(
            markers_map=markers_map,
            step_type=step_type,
            status='pending',
            step_data=step_data,
            step_name=step_name,
            nodes_info=current_markers
        )
        
        # Override step number
        step_instance.step_number = next_step_number
        step.instances[next_step_number] = step_instance
        
        print(f"✅ Created step instance: {step_instance} with number {next_step_number}")

        # Create pending step with connection requirements
        pending_step = {
            'type': step_type,
            'name': step_name,
            'tool': tool_name,
            'step_number': next_step_number,
            'step_instance': step_instance,
            'connections': {},
            'position': (position_x, position_y),
            'input_requirements': input_requirements,  # 🔧 Store for UI
            'needs_connections': list(input_requirements.keys()) if input_requirements else []
        }

        # Add to pending steps
        st.session_state.pending_steps.append(pending_step)
        print(f"✅ Added pending step. Total pending: {len(st.session_state.pending_steps)}")

        # Update the visual flow
        update_flow_with_pending_steps()

        # Set success message with connection info
        connection_info = ""
        if input_requirements:
            required_inputs = list(input_requirements.keys())
            connection_info = f" (Needs: {', '.join(required_inputs)})"
        
        set_message('success', f"✅ Added {step_type} step: {step_name}{connection_info}")

    except Exception as e:
        print(f"❌ Error adding pending step: {e}")
        set_message('error', f"❌ Error adding step: {e}")
        import traceback
        traceback.print_exc()

def update_flow_with_pending_steps():
    """Update the flow state to include pending steps in the visual diagram"""
    print(f"🔄 Updating flow with {len(st.session_state.get('pending_steps', []))} pending steps")
    
    # Ensure flow_state exists
    if 'flow_state' not in st.session_state or not st.session_state.flow_state:
        print("📭 No flow_state found, creating empty one")
        from streamlit_flow import StreamlitFlowState
        st.session_state.flow_state = StreamlitFlowState([], [])

    if not st.session_state.get('pending_steps'):
        print("📭 No pending steps to add")
        return

    try:
        # Get all existing nodes (both from loaded workflow and previously added pending steps)
        existing_nodes = list(st.session_state.flow_state.nodes)
        existing_edges = list(st.session_state.flow_state.edges)
        
        # CLEAR STALE EDGES - Remove edges that point to non-existent pending steps
        valid_edges = []
        pending_step_numbers = {ps['step_number'] for ps in st.session_state.pending_steps}
        
        # Get completed step numbers
        if st.session_state.current_workflow:
            state_file_path = dir_manager.get_state_file_path(st.session_state.current_workflow)
            current_state_data = dir_manager.load_json(state_file_path)
            completed_step_numbers = set(range(1, len(current_state_data.get('state_steps', [])) + 1))
        else:
            completed_step_numbers = set()
        
        all_valid_step_numbers = completed_step_numbers | pending_step_numbers
        
        for edge in existing_edges:
            # Check if edge connects to valid steps
            is_valid = True
            
            # Check source
            if '-' in edge.source and not edge.source.startswith('single-'):
                source_step = int(edge.source.split('-')[0])
                if source_step not in all_valid_step_numbers:
                    is_valid = False
                    print(f"🗑️ Removing stale edge (invalid source): {edge.id}")
            
            # Check target
            if '-' in edge.target and not edge.target.startswith('single-'):
                target_step = int(edge.target.split('-')[0])
                if target_step not in all_valid_step_numbers:
                    is_valid = False
                    print(f"🗑️ Removing stale edge (invalid target): {edge.id}")
            
            if is_valid:
                valid_edges.append(edge)
        
        print(f"🧹 Cleaned edges: {len(existing_edges)} -> {len(valid_edges)}")
        
        # Get existing node IDs to avoid duplicates
        existing_node_ids = {node.id for node in existing_nodes}
        print(f"📋 Existing node IDs: {existing_node_ids}")

        # Add pending step nodes to the current flow
        new_nodes = []
        for i, pending_step in enumerate(st.session_state.pending_steps):
            print(f"🔧 Processing pending step {i+1}: {pending_step['name']}")
            try:
                # Get step nodes from the step instance
                step_nodes = pending_step['step_instance'].return_step()
                print(f"📦 Step returned {len(step_nodes)} nodes")

                # Add these nodes to the new_nodes list if not already present
                for node in step_nodes:
                    if node.id not in existing_node_ids:
                        new_nodes.append(node)
                        existing_node_ids.add(node.id)
                        print(f"➕ Adding new node: {node.id}")
                    else:
                        print(f"⏭️ Skipping existing node: {node.id}")

            except Exception as e:
                print(f"❌ Error processing step {pending_step['name']}: {e}")
                continue

        # Update the flow state with all nodes (existing + new) and cleaned edges
        if new_nodes:
            all_nodes = existing_nodes + new_nodes
            st.session_state.flow_state.nodes = all_nodes
            st.session_state.flow_state.edges = valid_edges  # Use cleaned edges
            print(f"✅ Added {len(new_nodes)} new nodes. Total nodes: {len(all_nodes)}")
        else:
            # Still update edges even if no new nodes
            st.session_state.flow_state.edges = valid_edges
            print("📭 No new nodes to add, but updated edges")

        print(f"🎯 Flow now has {len(st.session_state.flow_state.nodes)} total nodes")

    except Exception as e:
        print(f"❌ Error updating flow with pending steps: {e}")
        import traceback
        traceback.print_exc()


def execute_pending_steps():
    """Execute pending steps with proper directory handling and connections"""
    if not st.session_state.current_workflow:
        set_message('error', '❌ No workflow selected')
        return False

    if not st.session_state.pending_steps:
        set_message('info', 'ℹ️ No pending steps to execute')
        return True

    try:
        # Get current edge connections from the flow
        connections = get_edge_connections(st.session_state.flow_state)
        print(f"DEBUG: Extracted connections: {connections}")
        
        # Validate all pending steps have required connections
        validation_errors = []
        for pending_step in st.session_state.pending_steps:
            step_name = pending_step['name']
            required_inputs = pending_step.get('input_requirements', {})
            step_connections = connections.get(step_name, {})
            
            missing_connections = []
            for required_input in required_inputs.keys():
                if required_input not in step_connections or not step_connections[required_input]:
                    missing_connections.append(required_input)
            
            if missing_connections:
                validation_errors.append(f"{step_name}: missing {', '.join(missing_connections)}")
        
        if validation_errors:
            error_msg = "❌ Missing connections:\n" + "\n".join(validation_errors)
            set_message('error', error_msg)
            print(f"VALIDATION FAILED: {error_msg}")
            return False
        
        print("✅ All connections validated successfully")

        # Get state file path (move this outside the loop)
        state_file_path = dir_manager.get_state_file_path(st.session_state.current_workflow)

        # Execute each pending step
        for pending_step in st.session_state.pending_steps:
            step_connections = connections.get(pending_step['name'], {})
            test_mode = pending_step.get('test_mode', False)
            
            print(f"🚀 Executing {pending_step['name']} (test_mode: {test_mode}) with connections: {step_connections}")
            
            # Clean connection values (remove "Single Data." prefix and fix parameter names)
            cleaned_connections = {}
            for param_name, source_value in step_connections.items():
                # Clean parameter name (replace spaces with underscores)
                clean_param_name = param_name.replace(' ', '_')
                
                # Clean source value (remove "Single Data." prefix)
                if source_value.startswith("Single Data."):
                    clean_source_value = source_value.replace("Single Data.", "")
                else:
                    clean_source_value = source_value
                
                cleaned_connections[clean_param_name] = clean_source_value
            
            print(f"🧹 Cleaned connections: {step_connections} -> {cleaned_connections}")
            
            try:
                if pending_step['type'] == 'llm':
                    use_llm_tool(
                        str(state_file_path),
                        pending_step['name'],
                        pending_step['tool'],
                        cleaned_connections,  # Use cleaned connections
                        test_mode=test_mode
                    )
                elif pending_step['type'] == 'code':
                    use_code_tool(
                        str(state_file_path),
                        pending_step['name'],
                        pending_step['tool'],
                        cleaned_connections,  # Use cleaned connections
                        test_mode=test_mode
                    )
                elif pending_step['type'] == 'chip':
                    use_chip(
                        str(state_file_path),  # Use workflow name instead of file path
                        pending_step['name'],
                        pending_step['tool'],
                        cleaned_connections,  # Use cleaned connections
                        test_mode=test_mode                     # test_mode parameter
                    )
                else:
                    raise ValueError(f"Unknown step type: {pending_step['type']}")

                print(f"✅ Executed: {pending_step['name']}")

            except Exception as e:
                set_message('error', f"❌ Error executing {pending_step['name']}: {e}")
                print(f"❌ Execution error for {pending_step['name']}: {e}")
                import traceback
                traceback.print_exc()
                return False

        # Save single data connections AFTER successful execution
        if connections:
            save_single_data_connections_to_state(state_file_path, connections)

        # Clear pending steps after successful execution
        st.session_state.pending_steps = []

        # Reload the workflow state to show updated diagram
        load_workflow_state(st.session_state.current_workflow)
        return True

    except Exception as e:
        set_message('error', f'❌ Execution error: {e}')
        print(f"❌ Overall execution error: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_edge_connections(flow_state):
    """Extract edge connections from the flow state with proper mapping to tool requirements"""
    connections = {}
    print(f"DEBUG: Processing {len(flow_state.edges)} edges")
    
    # Get current state data to look up actual marker names
    if st.session_state.current_workflow:
        state_file_path = dir_manager.get_state_file_path(st.session_state.current_workflow)
        current_state_data = dir_manager.load_json(state_file_path)
        state_steps = current_state_data.get('state_steps', [])
    else:
        state_steps = []
    
    for edge in flow_state.edges:
        print(f"DEBUG: Edge {edge.id}: {edge.source} -> {edge.target}")
        
        source_id = edge.source
        target_id = edge.target
        
        # Parse target to identify which step and input it belongs to
        if '-' in target_id and target_id.count('-') >= 2:
            parts = target_id.split('-')
            if len(parts) >= 3:
                step_number = parts[0]
                node_type = parts[1] # 'in' or 'out'
                input_index = parts[2] # '1', '2', etc.
                
                print(f"DEBUG: Parsing target {target_id}: step={step_number}, type={node_type}, index={input_index}")

                # Add this debug block to see what's actually in pending_steps
                print(f"DEBUG: Looking for step_number {step_number}, available pending steps:")
                for ps in st.session_state.get('pending_steps', []):
                    print(f"  - {ps['name']}: step_number={ps.get('step_number')}")

                
                # Find the corresponding pending step
                for pending_step in st.session_state.get('pending_steps', []):
                    if str(pending_step['step_number']) == step_number and node_type == 'in':
                        print(f"DEBUG: Found matching pending step: {pending_step['name']}")
                        
                        # Initialize connections dict for this step
                        if pending_step['name'] not in connections:
                            connections[pending_step['name']] = {}
                        
                        # Get tool requirements to map input index to parameter name
                        tool_requirements = pending_step.get('input_requirements', {})
                        print(f"DEBUG: Tool requirements: {tool_requirements}")
                        
                        # Map input index to parameter name
                        param_names = list(tool_requirements.keys())
                        try:
                            param_index = int(input_index) - 1 # Convert to 0-based index
                            if 0 <= param_index < len(param_names):
                                matching_param = param_names[param_index]
                                
                                # Resolve source connection with PROPER MARKER LOOKUP
                                if source_id.startswith('single-'):
                                    source_value = source_id.replace('single-', '')
                                elif '-' in source_id:
                                    source_parts = source_id.split('-')
                                    if len(source_parts) >= 3:
                                        source_step_num = int(source_parts[0])
                                        source_type = source_parts[1]  # 'out'
                                        source_index = int(source_parts[2])  # 1, 2, 3...
                                        
                                        # Look up the actual output marker name from state
                                        if source_step_num <= len(state_steps):
                                            source_step_data = state_steps[source_step_num - 1]
                                            output_data = source_step_data.get('data', {}).get('out', {})
                                            
                                            # Get the actual output marker name by index
                                            output_keys = list(output_data.keys())
                                            if source_index <= len(output_keys):
                                                actual_output_name = output_keys[source_index - 1]
                                                source_value = actual_output_name
                                                print(f"DEBUG: Resolved output marker: step {source_step_num} output {source_index} -> {actual_output_name}")
                                            else:
                                                source_value = f"step_{source_step_num}_output_{source_index}"
                                                print(f"WARNING: Output index {source_index} out of range for step {source_step_num}")
                                        else:
                                            source_value = f"step_{source_step_num}_output_{source_index}"
                                            print(f"WARNING: Step {source_step_num} not found in state")
                                    else:
                                        source_value = source_id
                                else:
                                    source_value = source_id
                                
                                connections[pending_step['name']][matching_param] = source_value
                                print(f"DEBUG: Mapped {target_id} -> {matching_param} = {source_value}")
                                
                            else:
                                print(f"WARNING: Input index {input_index} out of range for {len(param_names)} parameters")
                        except ValueError:
                            print(f"WARNING: Could not parse input index '{input_index}' as integer")
                        break # Found the step, no need to continue
                else:
                    print(f"DEBUG: Could not find pending step for target {target_id}")
            else:
                print(f"DEBUG: Could not parse target ID: {target_id}")
    
    print(f"DEBUG: Final connections: {connections}")
    return connections

def create_single_data_block(data_name, data_type, data_value):
    """Enhanced version that properly handles single data persistence and visualization"""
    if not st.session_state.current_workflow:
        set_message('error', "❌ No workflow selected. Please select or create a workflow first.")
        return False
    
    try:
        from datetime import datetime
        
        # Get current state data
        state_file_path = dir_manager.get_state_file_path(st.session_state.current_workflow)
        if not state_file_path.exists():
            set_message('error', f"❌ State file not found for workflow: {st.session_state.current_workflow}")
            return False
        
        current_state_data = dir_manager.load_json(state_file_path)
        
        # Check for duplicate names
        existing_names = [node['name'] for node in current_state_data.get('nodes', [])]
        if data_name in existing_names:
            set_message('error', f"❌ A node with name '{data_name}' already exists. Please use a different name.")
            return False
        
        # Create truncated display name (7 characters)
        display_name = str(data_value)[:7] + "..." if len(str(data_value)) > 7 else str(data_value)
        
        # Create type specification following existing pattern
        type_spec = {data_type: "single"}
        
        # Create single data marker with enhanced structure
        single_data_marker = {
            "name": data_name,
            "file_name": data_value,  # Store actual value in file_name field
            "type": type_spec,
            "state": "single_data",
            "display_name": display_name,
            "created_at": datetime.now().isoformat(),  # Add timestamp
            "data_type": data_type,  # Explicit data type for easier handling
            "is_single_data": True   # Clear flag for identification
        }
        
        # Add to workflow state
        if "nodes" not in current_state_data:
            current_state_data["nodes"] = []
        current_state_data["nodes"].append(single_data_marker)
        
        # Force atomic save to prevent corruption
        dir_manager.atomic_save_json(state_file_path, current_state_data)
        
        # Force immediate flow state reconstruction
        load_workflow_state(st.session_state.current_workflow)
        
        set_message('success', f"✅ Created single data block: {data_name}")
        return True
        
    except Exception as e:
        set_message('error', f"❌ Error creating single data block: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_single_data_nodes_from_state(state_data):
    """Create standalone single data nodes that appear in the workflow editor"""
    from streamlit_flow.elements import StreamlitFlowNode
    
    single_data_nodes = []
    nodes = state_data.get('nodes', [])
    
    # Filter for single data nodes
    single_data_markers = [node for node in nodes if node.get('state') == 'single_data']
    
    # Create visual nodes for each single data marker
    for i, marker in enumerate(single_data_markers):
        # Calculate position (arrange in a column on the left)
        position_x = 50  # Fixed x position on the left
        position_y = 100 + (i * 100)  # Vertical spacing
        
        # Get display name
        display_name = marker.get('display_name', marker['name'])
        
        # Get styling based on data type
        data_type = marker.get('data_type', 'string')
        color_map = {
            'string': '#90EE90',    # Light green
            'integer': '#87CEEB',   # Sky blue
            'list': '#DDA0DD',      # Plum
            'json': '#F0E68C'       # Khaki
        }
        
        style = {
            'width': '120px',
            'height': '60px',
            'backgroundColor': color_map.get(data_type, '#E0E0E0'),
            'border': '2px solid #4CAF50',  # Green border for single data
            'borderRadius': '8px',
            'color': 'black',
            'fontSize': '12px',
            'textAlign': 'center',
            'display': 'flex',
            'alignItems': 'center',
            'justifyContent': 'center',
            'boxShadow': '2px 2px 4px rgba(0,0,0,0.1)'
        }
        
        # Create the visual node with proper connection setup
        single_node = StreamlitFlowNode(
            f"single-{marker['name']}",  # Unique ID
            (position_x, position_y),
            {
                'content': display_name,
                'full_name': marker['name'],
                'data_type': marker.get('data_type', 'unknown'),
                'value': marker['file_name'],  # The actual data value
                'is_single_data': True,
                'marker_name': marker['name'],  # Add marker name for connection tracking
                'file_path': marker['file_name']  # Add file path for connection resolution
            },
            'input',  # Single data nodes are connection sources (input to the flow)
            target_position='right',
            draggable=True,
            connectable=True,  # Explicitly enable connections
            style=style
        )
        
        single_data_nodes.append(single_node)
    
    return single_data_nodes

# SIDEBAR - WORKFLOW ACTIONS AND MANAGEMENT
with st.sidebar:
    st.header("🛠️ Workflow Manager")
    
    # Create New Workflow Section
    st.subheader("➕ Create New Workflow")
    
    if st.button("🆕 Create New Workflow", key="create_workflow_btn", use_container_width=True):
        st.session_state.show_create_workflow_dialog = True
        st.rerun()
    
    # Load Existing Workflow Section
    st.subheader("📁 Load Existing Workflow")
    available_runs = get_available_runs()
    if available_runs:
        selected_workflow_sidebar = st.selectbox(
            "Select Workflow:",
            options=[None] + available_runs,
            format_func=lambda x: "Choose a workflow..." if x is None else x,
            key="sidebar_workflow_select"
        )
        
        if selected_workflow_sidebar and selected_workflow_sidebar != st.session_state.current_workflow:
            if st.button("🔄 Load Selected", key="load_selected_btn", use_container_width=True):
                state_data = load_workflow_state(selected_workflow_sidebar)
                if state_data:
                    set_message('success', f"✅ Loaded workflow: {selected_workflow_sidebar}")
                    st.rerun()
    else:
        st.info("No existing workflows found")
    
    st.divider()
    
    # Current Workflow Actions (only show if workflow is loaded)
    if st.session_state.current_workflow:
        st.subheader("🔧 Workflow Actions")
        st.caption(f"Current: {st.session_state.current_workflow}")
        
        # Simplified action buttons - step creation now in main interface
        if st.button("📊 Add Single Data", key="sidebar_add_single_btn", use_container_width=True):
            st.session_state.show_single_data_dialog = True
            st.rerun()
        
        if st.button("🌱 Start Seed Step", key="sidebar_seed_btn", use_container_width=True):
            st.session_state.show_seed_dialog = True
            st.rerun()
        
        # Show pending steps count and allow execution
        if st.session_state.pending_steps:
            pending_count = len(st.session_state.pending_steps)
            if st.button(f"▶️ Execute {pending_count} Steps", key="sidebar_run_steps_btn", use_container_width=True):
                if execute_pending_steps():
                    set_message('success', "✅ All pending steps executed!")
                    st.rerun()
        else:
            st.button("▶️ No Pending Steps", disabled=True, key="sidebar_run_steps_disabled", use_container_width=True)

# Header
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🔄 Workflow Editor")
    show_persistent_message()

with col2:
    # Current workflow indicator
    if st.session_state.current_workflow:
        st.success(f"📁 {st.session_state.current_workflow}")
    else:
        st.info("No workflow loaded")

# CREATE NEW WORKFLOW DIALOG
if st.session_state.get('show_create_workflow_dialog', False):
    with st.expander("🆕 Create New Workflow", expanded=True):
        with st.form("create_workflow_form"):
            st.markdown("### Enter Workflow Details")
            workflow_name = st.text_input(
                "Workflow Name:",
                placeholder="Enter a unique name for your workflow",
                key="new_workflow_name"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("🚀 Create Workflow", use_container_width=True)
                if submitted:
                    if workflow_name:
                        if workflow_name not in get_available_runs():
                            if create_new_workflow(workflow_name):
                                st.session_state.show_create_workflow_dialog = False
                                st.rerun()
                        else:
                            set_message('error', f"❌ Workflow '{workflow_name}' already exists!")
                    else:
                        set_message('warning', "⚠️ Please enter a workflow name.")
            
            with col2:
                cancel = st.form_submit_button("Cancel", use_container_width=True)
                if cancel:
                    st.session_state.show_create_workflow_dialog = False
                    st.rerun()

# Load workflow (from homepage selection or dropdown)
selected_workflow = st.session_state.get('selected_workflow')
if selected_workflow and selected_workflow != st.session_state.current_workflow:
    state_data = load_workflow_state(selected_workflow)
    if state_data:
        set_message('success', f"✅ Loaded workflow: {selected_workflow}")

# Main workflow editing interface
if st.session_state.current_workflow and st.session_state.flow_state:
    # Load current state data
    state_file_path = dir_manager.get_state_file_path(st.session_state.current_workflow)
    current_state_data = dir_manager.load_json(state_file_path)

    # Workflow info metrics (keep existing)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Workflow", current_state_data['name'])
    with col2:
        status = current_state_data['status']
        if status == 'running':
            st.metric("Status", "🔄 Running")
        elif status == 'running_chip':
            st.metric("Status", "🔧 Running Chip")
        elif status == 'completed':
            st.metric("Status", "✅ Complete")
        elif status == 'failed':
            st.metric("Status", "❌ Failed")
        else:
            st.metric("Status", f"📊 {status.title()}")
    with col3:
        st.metric("Steps", len(current_state_data['state_steps']))
    with col4:
        # Show running batches count
        running_batches = [s for s in current_state_data['state_steps']
                          if s.get('status') in ['uploaded', 'in_progress']]
        if running_batches:
            st.metric("🟡 Running", len(running_batches))
        else:
            st.metric("Running", 0)
    
    # NEW SIMPLIFIED INTERFACE LAYOUT
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Smart step builder (replaces complex dialogs)
        step_builder = SmartStepBuilder(st.session_state.current_workflow)
        step_builder.render()
        
        # Execute pending steps
        if st.session_state.pending_steps:
            st.divider()
            if st.button(f"🚀 Execute {len(st.session_state.pending_steps)} Steps", use_container_width=True):
                if execute_pending_steps():
                    set_message('success', "✅ All steps executed!")
                    st.rerun()
        

    
    with col2:
        # Workflow visualization
        st.subheader("📊 Workflow Visualization")
        updated_flow_state = streamlit_flow(
            'workflow_editor',
            st.session_state.flow_state,
            fit_view=True,
            height=500,
            enable_node_menu=False,
            enable_edge_menu=False,
            enable_pane_menu=False,
            get_edge_on_click=True,
            get_node_on_click=True,
            show_minimap=True,
            hide_watermark=True,
            allow_new_edges=True,
            min_zoom=0.1,
        ) 
        
        # Handle node clicks for data preview
        if updated_flow_state.selected_id:
            selected_id = updated_flow_state.selected_id
            if handle_marker_click(selected_id, current_state_data):
                st.rerun()

        # Handle node updates (dragging) - NO FORCED REFRESH
        nodes_updated = False
        for node in updated_flow_state.nodes:
            if 'parent' in node.id:
                current_pos = tuple(dict(node.position).values())
                prev_pos = tuple(node.data["prev_pos"])
                if current_pos != prev_pos:
                    step_number = int(node.id.split('-')[0])
                    step_instance = step.get_instance_by_number(step_number)
                    if step_instance:
                        updated_nodes = step_instance.return_step(current_pos)
                        updated_flow_state.nodes = [
                            n for n in updated_flow_state.nodes
                            if not n.id.startswith(f'{step_number}-')
                        ]
                        updated_flow_state.nodes.extend(updated_nodes)
                        nodes_updated = True

        # Always keep the SAME state object reference
        st.session_state.flow_state = updated_flow_state
        if nodes_updated:
            st.rerun()

    # Running batch status (non-refreshing display)
    if running_batches:
        st.subheader("⏳ Running Batches")
        for batch_step in running_batches:
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"**{batch_step['name']}** - {batch_step.get('tool_name', 'Unknown Tool')}")
                    if 'batch' in batch_step and batch_step['batch'].get('upload_id'):
                        st.caption(f"Batch ID: {batch_step['batch']['upload_id']}")
                with col2:
                    if batch_step['status'] == 'uploaded':
                        st.markdown("🔵 **Uploaded**")
                    elif batch_step['status'] == 'in_progress':
                        st.markdown("🟡 **In Progress**")
                    else:
                        st.markdown(f"⚪ **{batch_step['status'].title()}**")

                with col3:
                    if st.button("🔍 Check", key=f"check_{batch_step['name']}"):
                        try:
                            result = complete_running_step(state_file_path)
                            st.toast(f"Batch result: {result}")
                            # Manual refresh of visual state only
                            load_workflow_state(st.session_state.current_workflow)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
        st.divider()

    # Data preview panel (full width at bottom)
    render_data_preview_section()

    # UPDATED SEED STEP DIALOG WITH DROPDOWN (keep for seed creation)
    if st.session_state.get('show_seed_dialog', False):
        with st.expander("🌱 Start Seed Step", expanded=True):
            # Get available seed files
            available_seed_files = get_available_seed_files()
            st.markdown("### Choose Seed File Source")

            # Create tabs for different input methods
            tab1, tab2 = st.tabs(["📁 From Seed Files", "📝 Manual Path"])

            seed_file_path = None
            with tab1:
                if available_seed_files:
                    st.write(f"**Found {len(available_seed_files)} seed files:**")
                    # Dropdown for seed file selection
                    selected_seed = st.selectbox(
                        "Select Seed File:",
                        options=[None] + available_seed_files,
                        format_func=lambda x: "Choose a seed file..." if x is None else x['display_name'],
                        key="seed_file_dropdown"
                    )

                    if selected_seed:
                        seed_file_path = selected_seed['path']
                        # Show enhanced preview with entry count
                        with st.expander("📋 Seed File Preview & Analysis", expanded=True):
                            seed_content, metadata = preview_seed_file(selected_seed['path'])
                            if seed_content:
                                # Calculate and display entry count
                                total_entries, breakdown = calculate_seed_combinations_with_breakdown(seed_content)
                                
                                # Entry count display
                                col1, col2 = st.columns([1, 2])
                                with col1:
                                    st.metric("📊 Total Entries", f"{total_entries:,}")
                                
                                with col2:
                                    if breakdown:
                                        st.write("**Combination Breakdown:**")
                                        for detail in breakdown:
                                            st.caption(f"• {detail}")
                                
                                # Show metadata if available
                                if metadata:
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.caption(f"Created: {metadata['created']}")
                                    with col2:
                                        st.caption(f"Conversation turns: {metadata['conversation_length']}")

                                # Show key information
                                st.write("**Variables:**")
                                if 'variables' in seed_content:
                                    for var_name, var_values in seed_content['variables'].items():
                                        if isinstance(var_values, list):
                                            st.write(f"• {var_name}: {len(var_values)} options")
                                        elif isinstance(var_values, dict):
                                            st.write(f"• {var_name}: {len(var_values)} categories")
                                        else:
                                            st.write(f"• {var_name}: {type(var_values).__name__}")

                                st.write("**Prompt Template:**")
                                if 'constants' in seed_content and 'prompt' in seed_content['constants']:
                                    st.code(seed_content['constants']['prompt'])
                else:
                    st.info("No seed files found in the seed_files directory.")
                    st.markdown("💡 **Tip:** Use the **Seed Architect** to create seed files!")
                    if st.button("🏗️ Go to Seed Architect"):
                        st.switch_page("pages/seed_architect.py")

            with tab2:
                st.write("**Enter seed file path manually:**")
                manual_seed_file = st.text_input("Seed file path:", placeholder="path/to/your/seed_file.json")
                if manual_seed_file:
                    seed_file_path = manual_seed_file

            # Action buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🌱 Start Seed Step"):
                    if seed_file_path:
                        try:
                            # Ensure workflow directory exists first
                            dir_manager.ensure_workflow_directory(st.session_state.current_workflow)
                            # Get proper state file path
                            state_file_path = dir_manager.get_state_file_path(st.session_state.current_workflow)
                            start_seed_step(str(state_file_path), seed_file_path)
                            set_message('success', "🚀 Seed step started!")
                            st.session_state.show_seed_dialog = False
                            # Manual refresh of visual state
                            load_workflow_state(st.session_state.current_workflow)
                            st.rerun()
                        except Exception as e:
                            set_message('error', f"❌ Error starting seed: {e}")
                    else:
                        set_message('warning', "⚠️ Please select or enter a seed file path.")

            with col2:
                if st.button("Cancel##seed"):
                    st.session_state.show_seed_dialog = False
                    st.rerun()

    # OLD DIALOGS COMMENTED OUT - REPLACED BY SmartStepBuilder
    # # LLM tool dialog
    # if st.session_state.get('show_llm_dialog', False):
    #     with st.expander("🤖 Add LLM Tool", expanded=True):
    #         # ... old dialog code ...

    # #CODE TOOL DIALOG
    # if st.session_state.get('show_code_dialog', False):
    #     with st.expander("⚙️ Add Code Tool", expanded=True):
    #         # ... old dialog code ...

    # SINGLE DATA DIALOG
    if st.session_state.get('show_single_data_dialog', False):
        with st.expander("📊 Add Single Data Block", expanded=True):
            with st.form("single_data_form"):
                st.markdown("### Create Single Data Block")
                
                # Name input
                data_name = st.text_input(
                    "Data Name:",
                    placeholder="Enter a name for this data block",
                    key="single_data_name"
                )
                
                # Data type selection
                data_type = st.selectbox(
                    "Data Type:",
                    options=["string", "integer", "list", "json"],
                    key="single_data_type"
                )
                
                # Dynamic input based on type
                data_value = None
                if data_type == "string":
                    data_value = st.text_input(
                        "String Value:",
                        placeholder="Enter string value",
                        key="single_string_input"
                    )
                elif data_type == "integer":
                    data_value = st.number_input(
                        "Integer Value:",
                        value=0,
                        step=1,
                        key="single_int_input"
                    )
                elif data_type == "list":
                    list_input = st.text_input(
                        "List Items (comma-separated):",
                        placeholder="item1, item2, item3",
                        key="single_list_input"
                    )
                    if list_input:
                        # Convert comma-separated to list
                        data_value = [item.strip() for item in list_input.split(',') if item.strip()]
                        st.caption(f"Preview: {data_value}")
                elif data_type == "json":
                    json_input = st.text_area(
                        "JSON Value:",
                        placeholder='{"key": "value"}',
                        key="single_json_input"
                    )
                    if json_input:
                        try:
                            import json
                            data_value = json.loads(json_input)
                            st.success("✅ Valid JSON")
                        except json.JSONDecodeError as e:
                            st.error(f"❌ Invalid JSON: {e}")
                            data_value = None
                
                # Form buttons
                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("📊 Create Single Data")
                    if submitted:
                        if data_name and data_value is not None:
                            create_single_data_block(data_name, data_type, data_value)
                            st.session_state.show_single_data_dialog = False
                            st.rerun()
                        else:
                            set_message('warning', "⚠️ Please fill in all fields.")
                
                with col2:
                    cancel = st.form_submit_button("Cancel")
                    if cancel:
                        st.session_state.show_single_data_dialog = False
                        st.rerun()

    # INLINE SINGLE DATA DIALOGS
    step_builder.render_inline_single_data_dialogs()

    # Display pending steps
    if st.session_state.pending_steps:
        st.subheader("⏳ Pending Steps")
        st.info("💡 These steps are now visible in the diagram below. Connect the required inputs, then click 'Execute' to run them.")
        
        for i, pending_step in enumerate(st.session_state.pending_steps):
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 3, 2, 1])
                
                with col1:
                    st.write(f"**{pending_step['name']}**")
                    st.caption(f"{pending_step['type'].upper()}: {pending_step['tool']}")
                
                with col2:
                    # Show required connections
                    if pending_step.get('needs_connections'):
                        st.write("🔌 **Needs Connections:**")
                        for req in pending_step['needs_connections']:
                            req_type = pending_step['input_requirements'][req]
                            st.caption(f"• {req}: {req_type}")
                    else:
                        st.write("✅ **No connections needed**")
                
                with col3:
                    # Show connection status
                    connected_count = len([c for c in pending_step.get('connections', {}).values() if c])
                    required_count = len(pending_step.get('needs_connections', []))
                    
                    if required_count == 0:
                        st.success("Ready ✅")
                    elif connected_count == required_count:
                        st.success("Connected ✅")
                    else:
                        st.warning(f"Missing {required_count - connected_count}")
                
                with col4:
                    if st.button("❌", key=f"remove_pending_{i}", help="Remove this step"):
                        # Remove from pending steps and visual flow
                        removed_step = st.session_state.pending_steps.pop(i)
                        step_id_prefix = f"{removed_step['step_number']}-"
                        st.session_state.flow_state.nodes = [
                            node for node in st.session_state.flow_state.nodes
                            if not node.id.startswith(step_id_prefix)
                        ]
                        st.rerun()
        
        st.divider()

    # OLD WORKFLOW VISUALIZATION SECTION - REPLACED BY NEW LAYOUT
    # (This section is now handled in the simplified interface above)

    # OLD NODE SELECTION INFO - REPLACED BY DataPreview
    # (Node selection info is now handled in the DataPreview panel)

else:
    st.info("👆 Please create a new workflow or load an existing one from the sidebar.")
    # Show example workflows if any exist
    available_runs = get_available_runs()
    if available_runs:
        st.subheader("📁 Available Workflows")
        for run in available_runs[:5]:  # Show first 5
            if st.button(f"Load {run}", key=f"load_{run}"):
                state_data = load_workflow_state(run)
                if state_data:
                    set_message('success', f"✅ Loaded workflow: {run}")
                    st.rerun()
