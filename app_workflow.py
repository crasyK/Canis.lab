import streamlit as st
import os
import json
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
from streamlit_flow.state import StreamlitFlowState
from streamlit_flow.layouts import LayeredLayout
from uuid import uuid4
import time

# Import actual library functions
from lib.state_managment import create_state, start_seed_step, complete_running_step, use_llm_tool, use_code_tool, get_markers
from lib.tools.llm import get_available_llm_tools, prepare_data
from lib.tools.code import get_available_code_tools, prepare_tool_use
from lib.tools.global_func import get_type, check_data_type, has_connection

class WorkflowAppWithSeparateHandles:
    """Enhanced Streamlit-based Workflow Designer using separate handle nodes."""
   
    def __init__(self):
        self.state_directory = "runs/"
        if 'workflow_initialized' not in st.session_state:
            st.session_state.workflow_initialized = True
            st.session_state.flow_state = None
            st.session_state.current_run = None
            st.session_state.status_check_interval = 3
            st.session_state.handle_node_counter = 0
            self.init_flow_state()
   
    def init_flow_state(self):
        """Initialize the flow state with empty nodes."""
        nodes = []
        edges = []
        st.session_state.flow_state = StreamlitFlowState(nodes=nodes, edges=edges)
   
    def get_available_runs(self) -> list[str]:
        """Get list of available run directories."""
        if not os.path.exists(self.state_directory):
            return []
        return [d for d in os.listdir(self.state_directory)
                if os.path.isdir(os.path.join(self.state_directory, d))]
   
    def get_available_seed_files(self) -> list[str]:
        """Get list of available seed files."""
        seed_files = []
        for file in os.listdir("."):
            if file.endswith(".json") and file.startswith("Seed_"):
                seed_files.append(file)
        return seed_files
   
    def get_data_type_color(self, data_type: str) -> str:
        """Get color for data type markers."""
        type_colors = {
            'json': '#FFC107',  # Yellow
            'str': '#4CAF50',   # Green
            'list': '#9C27B0',  # Purple
            'int': '#2196F3'    # Blue
        }
        return type_colors.get(data_type.lower(), '#757575')
   
    def create_separate_handle_nodes(self, parent_node_id: str, markers: list, base_x: int, base_y: int, parent_status: str = 'completed') -> tuple[list, list]:
        """Create separate small nodes for each output marker and connecting edges."""
        handle_nodes = []
        connecting_edges = []
        
        for i, marker in enumerate(markers):
            if isinstance(marker, dict):
                marker_name = marker.get('name', f'marker_{i}')
                marker_type = marker.get('type', {})
                marker_state = marker.get('state', 'created')
                
                if isinstance(marker_type, dict):
                    type_str = list(marker_type.keys())[0] if marker_type else 'unknown'
                else:
                    type_str = str(marker_type)
                
                # Color and status based on parent and marker state
                base_color = self.get_data_type_color(type_str)
                is_available = parent_status == 'completed' and marker_state in ['completed', 'uploaded']
                
                if not is_available:
                    base_color = '#757575'  # Gray for disabled
                    border_color = '#F44336'  # Red border for unavailable
                else:
                    border_color = '#333'
                
                handle_node_id = f"{parent_node_id}_handle_{i}_{uuid4()}"
                
                # Create a small handle node positioned to the right of parent
                handle_node = StreamlitFlowNode(
                    id=handle_node_id,
                    pos=(base_x + 250, base_y + i * 50),  # Offset to the right and down
                    data={
                        'content': f"🔗 {marker_name}\n({type_str})\n{'✅' if is_available else '🔴'}",
                        'type': 'handle',
                        'parent_id': parent_node_id,
                        'marker_name': marker_name,
                        'marker_type': type_str,
                        'marker_data': marker,
                        'marker_state': marker_state,
                        'is_available': is_available
                    },
                    node_type='default',  # Changed to default to allow both input and output
                    source_position='right',
                    target_position='left',
                    style={
                        'background': base_color,
                        'color': 'white',
                        'border': f'2px solid {border_color}',
                        'borderRadius': '8px',
                        'minWidth': '120px',
                        'minHeight': '50px',
                        'padding': '8px',
                        'fontSize': '11px',
                        'textAlign': 'center',
                        'opacity': '1.0' if is_available else '0.7'
                    }
                )
                handle_nodes.append(handle_node)
                
                # Create connecting edge from parent to handle node
                connecting_edge = StreamlitFlowEdge(
                    id=f"edge_{parent_node_id}_to_{handle_node_id}",
                    source=parent_node_id,
                    target=handle_node_id,
                    animated=False,
                    style={
                        'stroke': base_color,
                        'strokeWidth': 2,
                        'strokeDasharray': '5,5',  # Dashed line to show it's a connection
                        'opacity': '1.0' if is_available else '0.5'
                    },
                    label=None
                )
                connecting_edges.append(connecting_edge)
                
        return handle_nodes, connecting_edges
   
    def create_seed_node_with_handles(self, seed_file: str) -> tuple[StreamlitFlowNode, list, list]:
        """Create a seed node with separate handle nodes for outputs."""
        node_id = "seed"
        base_x, base_y = 100, 100
        
        # Get markers for seed node and check seed status
        markers = self.get_node_markers(node_id)
        seed_status = self.get_seed_status()
        
        # Determine node appearance based on status
        is_completed = seed_status['status'] == 'completed'
        background_color = '#4CAF50' if is_completed else '#757575'  # Green if completed, gray if not
        border_color = '#45a049' if is_completed else '#F44336'  # Green border if completed, red if not
        status_emoji = '✅' if is_completed else '🔴'
        
        # Create the main seed node (without complex handles)
        seed_node = StreamlitFlowNode(
            id=node_id,
            pos=(base_x, base_y),
            data={
                'content': f"🌱 Seed\n{seed_file}\n{status_emoji} {seed_status['status']}\n{len(markers)} outputs →",
                'type': 'seed',
                'seed_file': seed_file,
                'status': seed_status['status'],
                'markers': markers,
                'has_separate_handles': True,
                'is_available': is_completed
            },
            node_type='default',  # Changed from 'input' to allow connections
            source_position='right',
            style={
                'background': background_color,
                'color': 'white',
                'border': f'2px solid {border_color}',
                'borderRadius': '8px',
                'minWidth': '180px',
                'minHeight': '100px',
                'padding': '15px',
                'textAlign': 'center',
                'opacity': '1.0' if is_completed else '0.7'
            }
        )
        
        # Create separate handle nodes with status consideration
        handle_nodes, connecting_edges = self.create_separate_handle_nodes(
            node_id, markers, base_x, base_y, seed_status['status']
        )
        
        return seed_node, handle_nodes, connecting_edges
   
    def get_node_markers(self, node_id: str, step_name: str = None) -> list:
        """Get output markers for a node from the state file."""
        if not st.session_state.current_run:
            return []
            
        state_file_path = os.path.join(self.state_directory, st.session_state.current_run, "state.json")
        if not os.path.exists(state_file_path):
            return []
            
        try:
            markers = get_markers(state_file_path)
            if node_id == "seed":
                return [m for m in markers if isinstance(m, dict) and m.get("name")]
            elif step_name:
                # For tool steps, get markers from the step's output
                with open(state_file_path, 'r') as f:
                    state = json.load(f)
                for step in state.get("state_steps", []):
                    if step.get("name") == step_name and step.get("status") == "completed":
                        out_data = step.get("data", {}).get("out", {})
                        step_markers = []
                        for key, file_path in out_data.items():
                            # Create marker based on tool output
                            step_markers.append({
                                "name": key,
                                "type": {"json": "data"},  # Most tool outputs are JSON data
                                "state": "completed",
                                "file_name": file_path
                            })
                        return step_markers
            return []
        except Exception as e:
            print(f"Error getting markers: {e}")
            return []
   
    def get_node_status(self, node_id: str, step_name: str = None) -> dict:
        """Get current status and progress of a node from state file."""
        if not st.session_state.current_run:
            return {'status': 'created', 'progress': 0}
            
        state_file_path = os.path.join(self.state_directory, st.session_state.current_run, "state.json")
        if not os.path.exists(state_file_path):
            return {'status': 'created', 'progress': 0}
            
        try:
            with open(state_file_path, 'r') as f:
                state = json.load(f)
            
            for step in state.get("state_steps", []):
                if step.get("name") == step_name:
                    return {
                        'status': step.get("status", "created"),
                        'progress': step.get("progress", 0),
                        'error': step.get("error", None)
                    }
            return {'status': 'created', 'progress': 0}
        except:
            return {'status': 'created', 'progress': 0}
    
    def get_seed_status(self) -> dict:
        """Get the status of the seed step specifically."""
        if not st.session_state.current_run:
            return {'status': 'created', 'progress': 0}
            
        state_file_path = os.path.join(self.state_directory, st.session_state.current_run, "state.json")
        if not os.path.exists(state_file_path):
            return {'status': 'created', 'progress': 0}
            
        try:
            with open(state_file_path, 'r') as f:
                state = json.load(f)
            
            # Look for seed step
            for step in state.get("state_steps", []):
                if step.get("name") == "seed":
                    return {
                        'status': step.get("status", "created"),
                        'progress': step.get("progress", 0),
                        'error': step.get("error", None)
                    }
            return {'status': 'created', 'progress': 0}
        except:
            return {'status': 'created', 'progress': 0}
   
    def create_tool_node_with_handles(self, tool_type: str, tool_name: str, step_name: str) -> StreamlitFlowNode:
        """Create a tool node that can connect to handle nodes."""
        node_id = f"tool_{uuid4()}"
        
        # Get corner color based on tool type
        corner_color = "#F44336" if tool_type == "llm" else "#FF9800"
        base_color = "#424242"
        
        return StreamlitFlowNode(
            id=node_id,
            pos=(500, 200),
            data={
                'content': f"🔧 {step_name}\n({tool_type.upper()}: {tool_name})",
                'type': 'tool',
                'tool_type': tool_type,
                'tool_name': tool_name,
                'step_name': step_name,
                'status': 'created',
                'can_connect_to_handles': True
            },
            node_type='default',
            source_position='right',
            target_position='left',
            style={
                'background': base_color,
                'color': 'white',
                'border': f'3px solid {corner_color}',
                'borderRadius': '8px',
                'minWidth': '180px',
                'minHeight': '80px',
                'padding': '10px',
                'textAlign': 'center'
            }
        )
   
    def create_input_node(self, data_type: str, value: str = "") -> StreamlitFlowNode:
        """Create a single input node."""
        node_id = f"input_{uuid4()}"
        color = self.get_data_type_color(data_type)
        
        return StreamlitFlowNode(
            id=node_id,
            pos=(200, 300),
            data={
                'content': f"📝 Input\n{data_type.upper()}\nValue: {value[:15]}{'...' if len(value) > 15 else ''}",
                'type': 'input',
                'data_type': data_type,
                'value': value,
                'status': 'completed'
            },
            node_type='default',
            source_position='right',
            style={
                'background': color,
                'color': 'white',
                'border': '2px solid #333',
                'borderRadius': '8px',
                'minWidth': '120px',
                'minHeight': '80px',
                'padding': '8px',
                'textAlign': 'center'
            }
        )
   
    def validate_connection(self, source_node, target_node) -> tuple[bool, str]:
        """Validate if a connection between two nodes is possible."""
        # Check if source handle node is available (completed/uploaded)
        if source_node.data.get('type') == 'handle':
            if not source_node.data.get('is_available', False):
                return False, "Handle node is not available yet - parent step must complete first"
            
            # Allow connections from available handle nodes to tool nodes
            if target_node.data.get('type') == 'tool':
                return True, "Handle to tool connection valid"
            
            # Allow connections from handle nodes to other handle nodes (chaining)
            if target_node.data.get('type') == 'handle':
                return True, "Handle to handle connection valid"
        
        # Allow connections from input nodes to tool nodes
        if source_node.data.get('type') == 'input' and target_node.data.get('type') == 'tool':
            return True, "Input to tool connection valid"
        
        # Allow connections from seed node to tool nodes (if no separate handles)
        if source_node.data.get('type') == 'seed' and target_node.data.get('type') == 'tool':
            if not source_node.data.get('has_separate_handles', False):
                if source_node.data.get('is_available', False):
                    return True, "Seed to tool connection valid"
                else:
                    return False, "Seed step must complete first"
            else:
                return False, "Use the separate handle nodes to connect to tools"
        
        # Block connections to seed nodes
        if target_node.data.get('type') == 'seed':
            return False, "Cannot connect to seed node"
        
        return True, "Connection valid"
   
    def execute_node(self, node_data: dict):
        """Execute a workflow node."""
        if not st.session_state.current_run:
            st.error("No run selected. Please select a run first.")
            return
            
        state_file_path = os.path.join(self.state_directory, st.session_state.current_run, "state.json")
        
        if node_data['type'] == 'tool':
            tool_type = node_data['tool_type']
            tool_name = node_data['tool_name']
            step_name = node_data['step_name']
            tool_node_id = node_data['id']
            
            # Collect input data from connected nodes
            input_data = self.collect_input_data_for_node(node_data)
            
            try:
                if tool_type == "llm":
                    result = use_llm_tool(state_file_path, step_name, tool_name, input_data)
                    st.success(f"✅ LLM tool '{tool_name}' executed successfully!")
                else:
                    result = use_code_tool(state_file_path, step_name, tool_name, input_data)
                    st.success(f"✅ Code tool '{tool_name}' executed successfully!")
                
                # Create output handles for completed tool
                self.create_tool_output_handles(tool_node_id, step_name)
                st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Error executing tool: {e}")
    
    def create_tool_output_handles(self, tool_node_id: str, step_name: str):
        """Create output handle nodes for a completed tool."""
        # Find the tool node
        tool_node = next((n for n in st.session_state.flow_state.nodes if n.id == tool_node_id), None)
        if not tool_node:
            return
        
        # Get output markers for this tool step
        output_markers = self.get_node_markers("tool", step_name)
        
        if output_markers:
            # Position handles to the right of the tool node
            base_x = tool_node.pos[0]
            base_y = tool_node.pos[1]
            
            # Create handle nodes for outputs
            handle_nodes, connecting_edges = self.create_separate_handle_nodes(
                tool_node_id, output_markers, base_x, base_y, 'completed'
            )
            
            # Add to flow state
            st.session_state.flow_state.nodes.extend(handle_nodes)
            st.session_state.flow_state.edges.extend(connecting_edges)
            
            # Update tool node to show it has handles
            tool_node.data['has_output_handles'] = True
            tool_node.data['output_markers'] = output_markers
    
    def collect_input_data_for_node(self, node_data: dict) -> dict:
        """Collect input data from connected handle/input nodes."""
        input_data = {}
        tool_node_id = node_data.get('id')
        
        # Find edges that connect to this tool node
        for edge in st.session_state.flow_state.edges:
            if edge.target == tool_node_id:
                # Find the source node
                source_node = next((n for n in st.session_state.flow_state.nodes if n.id == edge.source), None)
                if source_node:
                    if source_node.data.get('type') == 'handle':
                        # Handle node - use marker name as key
                        marker_name = source_node.data.get('marker_name')
                        if marker_name:
                            input_data[marker_name] = marker_name  # Reference to marker
                    elif source_node.data.get('type') == 'input':
                        # Input node - use data type as key and value as value
                        data_type = source_node.data.get('data_type', 'input')
                        value = source_node.data.get('value', '')
                        input_data[data_type] = value
        
        return input_data
   
    def display_node_editor(self, selected_node):
        """Display enhanced node editor in sidebar."""
        with st.sidebar:
            st.markdown("---")
            st.subheader(f"📝 Node Editor")
            
            st.write(f"**ID:** `{selected_node.id}`")
            node_type = selected_node.data.get('type', 'unknown')
            st.write(f"**Type:** {node_type.title()}")
            
            if node_type == 'handle':
                st.write(f"**Parent:** {selected_node.data.get('parent_id')}")
                st.write(f"**Marker:** {selected_node.data.get('marker_name')}")
                st.write(f"**Data Type:** {selected_node.data.get('marker_type')}")
                st.write(f"**State:** {selected_node.data.get('marker_state', 'unknown')}")
                
                is_available = selected_node.data.get('is_available', False)
                if is_available:
                    st.success("✅ Available for connections")
                    st.info("🔗 This handle can connect to tool inputs and other handles.")
                else:
                    st.error("🔴 Not available - parent step must complete first")
                    st.warning("⏳ This handle will become available after the parent step completes.")
                
            elif node_type == 'tool':
                st.write(f"**Tool:** {selected_node.data.get('tool_name')}")
                st.write(f"**Step:** {selected_node.data.get('step_name')}")
                
                if st.button("▶️ Execute Node", type="primary"):
                    # Pass the node ID for data collection
                    node_data_with_id = selected_node.data.copy()
                    node_data_with_id['id'] = selected_node.id
                    self.execute_node(node_data_with_id)
                    
            elif node_type == 'input':
                st.write(f"**Data Type:** `{selected_node.data.get('data_type')}`")
                current_value = selected_node.data.get('value', '')
                new_value = st.text_area("Value", value=current_value, height=100)
                
                if st.button("💾 Update Value") and new_value != current_value:
                    selected_node.data['value'] = new_value
                    data_type = selected_node.data.get('data_type')
                    selected_node.data['content'] = f"📝 Input\n{data_type.upper()}\nValue: {new_value[:15]}{'...' if len(new_value) > 15 else ''}"
                    st.success("Value updated!")
                    st.rerun()
                    
            elif node_type == 'seed':
                st.write(f"**Seed File:** {selected_node.data.get('seed_file')}")
                status = selected_node.data.get('status', 'created')
                is_available = selected_node.data.get('is_available', False)
                
                if is_available:
                    st.success(f"✅ Status: {status}")
                else:
                    st.error(f"🔴 Status: {status}")
                    if st.button("🔄 Check Seed Completion"):
                        # Check if seed step has completed
                        state_file_path = os.path.join(self.state_directory, st.session_state.current_run, "state.json")
                        try:
                            result = complete_running_step(state_file_path)
                            st.success(f"Seed step completed: {result}")
                            st.rerun()
                        except Exception as e:
                            st.warning(f"Seed step still in progress: {e}")
                
                markers = selected_node.data.get('markers', [])
                st.write(f"**Outputs:** {len(markers)} separate handle nodes")
                
                if markers:
                    st.write("**Available Outputs:**")
                    for marker in markers:
                        if isinstance(marker, dict):
                            marker_name = marker.get('name', 'unknown')
                            marker_type = marker.get('type', {})
                            marker_state = marker.get('state', 'created')
                            file_name = marker.get('file_name', '')
                            
                            if isinstance(marker_type, dict):
                                type_str = list(marker_type.keys())[0] if marker_type else 'unknown'
                            else:
                                type_str = str(marker_type)
                            
                            status_icon = '✅' if marker_state in ['completed', 'uploaded'] else '🔴'
                            st.markdown(f"{status_icon} **{marker_name}** `{type_str}` ({marker_state})")
                            
                            # Show preview of actual content if available
                            if file_name and os.path.exists(file_name) and marker_state in ['completed', 'uploaded']:
                                with st.expander(f"Preview {marker_name}"):
                                    try:
                                        if file_name.endswith('.json'):
                                            with open(file_name, 'r') as f:
                                                content = json.load(f)
                                            if isinstance(content, dict):
                                                # Show first few entries
                                                preview_keys = list(content.keys())[:3]
                                                for key in preview_keys:
                                                    value = str(content[key])[:100]
                                                    st.text(f"{key}: {value}{'...' if len(str(content[key])) > 100 else ''}")
                                                if len(content) > 3:
                                                    st.text(f"... and {len(content) - 3} more entries")
                                        else:
                                            with open(file_name, 'r') as f:
                                                preview = f.read(200)
                                            st.text(f"{preview}{'...' if len(preview) == 200 else ''}")
                                    except Exception as e:
                                        st.error(f"Error reading file: {e}")


def main():
    """Main Streamlit app for Enhanced Workflow Designer."""
    st.set_page_config(
        page_title="🔧 Enhanced Workflow Designer",
        page_icon="⚙️",
        layout="wide"
    )
    
    app = WorkflowAppWithSeparateHandles()
    
    # Header
    st.title("🔧 Enhanced Workflow Designer with Separate Handles")
    st.markdown("### Design and Execute Synthetic Data Generation Workflows")
    
    # Enhanced color legend
    with st.expander("🎨 Node Types & Data Type Legend"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Node Types:**")
            st.markdown("🌱 **Seed** - Data source (Green)")
            st.markdown("🔗 **Handle** - Output connectors (Colored by type)")
            st.markdown("🔧 **Tool** - Processing nodes (Red=LLM, Orange=Code)")
            st.markdown("📝 **Input** - Single value inputs")
            
        with col2:
            st.markdown("**Data Types:**")
            st.markdown("🟨 **JSON** - Yellow")
            st.markdown("🟩 **STR** - Green")
            st.markdown("🟪 **LIST** - Purple")
            st.markdown("🟦 **INT** - Blue")
    
    # Sidebar controls
    with st.sidebar:
        st.header("🎛️ Controls")
        
        # Run Management
        st.subheader("📁 Run Management")
        
        with st.expander("➕ Create New Run"):
            new_run_name = st.text_input("Run Name")
            if st.button("Create Run") and new_run_name:
                try:
                    state = create_state(new_run_name)
                    if not os.path.exists(app.state_directory):
                        os.makedirs(app.state_directory)
                    st.success(f"✅ Run created: {state['name']}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error creating run: {e}")
        
        # Select existing run
        available_runs = app.get_available_runs()
        if available_runs:
            selected_run = st.selectbox("Select Run", available_runs)
            if st.button("📂 Load Run"):
                st.session_state.current_run = selected_run
                st.success(f"✅ Loaded run: {selected_run}")
                st.rerun()
        
        if st.session_state.current_run:
            st.info(f"📁 Current Run: **{st.session_state.current_run}**")
            
            # Seed file management - check both flow state and actual state file
            seed_exists_in_flow = any(node.id == "seed" for node in st.session_state.flow_state.nodes)
            state_file_path = os.path.join(app.state_directory, st.session_state.current_run, "state.json")
            seed_exists_in_state = False
            
            if os.path.exists(state_file_path):
                try:
                    with open(state_file_path, 'r') as f:
                        state = json.load(f)
                    seed_exists_in_state = any(step.get("name") == "seed" for step in state.get("state_steps", []))
                except:
                    pass
            
            # If seed exists in state but not in flow, recreate the flow
            if seed_exists_in_state and not seed_exists_in_flow:
                try:
                    # Find the seed file from state
                    with open(state_file_path, 'r') as f:
                        state = json.load(f)
                    
                    # Find the original seed file name from state steps
                    seed_file_name = "existing_seed.json"
                    for step in state.get("state_steps", []):
                        if step.get("name") == "seed":
                            # Try to infer seed file from batch file path or use default
                            batch_path = step.get("batch", {}).get("in", "")
                            if "seed" in batch_path:
                                seed_file_name = "reconstructed_seed.json"
                            break
                    
                    # Reconstruct seed node and handles
                    seed_node, handle_nodes, connecting_edges = app.create_seed_node_with_handles(seed_file_name)
                    
                    # Add all nodes and edges to the flow
                    st.session_state.flow_state.nodes.append(seed_node)
                    st.session_state.flow_state.nodes.extend(handle_nodes)
                    st.session_state.flow_state.edges.extend(connecting_edges)
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"Error recreating seed flow: {e}")
            
            # Add refresh button for workflow state
            if st.button("🔄 Refresh Workflow State"):
                # Clear current flow state
                app.init_flow_state()
                
                # Recreate nodes from state file if they exist
                if os.path.exists(state_file_path):
                    try:
                        with open(state_file_path, 'r') as f:
                            state = json.load(f)
                        
                        # Recreate seed node if it exists
                        for step in state.get("state_steps", []):
                            if step.get("name") == "seed":
                                seed_node, handle_nodes, connecting_edges = app.create_seed_node_with_handles("refreshed_seed.json")
                                st.session_state.flow_state.nodes.append(seed_node)
                                st.session_state.flow_state.nodes.extend(handle_nodes)
                                st.session_state.flow_state.edges.extend(connecting_edges)
                                break
                        
                        # Recreate tool nodes for completed steps
                        for step in state.get("state_steps", []):
                            if step.get("name") != "seed" and step.get("status") == "completed":
                                tool_type = step.get("type", "code")
                                tool_name = step.get("tool_name", "unknown")
                                step_name = step.get("name", "unknown")
                                
                                tool_node = app.create_tool_node_with_handles(tool_type, tool_name, step_name)
                                st.session_state.flow_state.nodes.append(tool_node)
                                
                                # Create output handles for completed tool
                                app.create_tool_output_handles(tool_node.id, step_name)
                        
                        st.success("🔄 Workflow state refreshed from saved state!")
                    except Exception as e:
                        st.error(f"Error refreshing from state: {e}")
                
                st.rerun()
            
            if not seed_exists_in_flow and not seed_exists_in_state:
                st.subheader("🌱 Start with Seed")
                # Select and load actual seed file
                available_seeds = app.get_available_seed_files()
                if available_seeds:
                    selected_seed = st.selectbox("Select Seed File", available_seeds)
                    if st.button("🚀 Load Seed"):
                        try:
                            # Initialize seed step in state management
                            state_file_path = os.path.join(app.state_directory, st.session_state.current_run, "state.json")
                            start_seed_step(state_file_path, selected_seed)
                            
                            seed_node, handle_nodes, connecting_edges = app.create_seed_node_with_handles(selected_seed)
                            
                            # Add all nodes and edges to the flow
                            st.session_state.flow_state.nodes.append(seed_node)
                            st.session_state.flow_state.nodes.extend(handle_nodes)
                            st.session_state.flow_state.edges.extend(connecting_edges)
                            
                            st.success(f"🌱 Seed '{selected_seed}' loaded with separate handles!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error loading seed: {e}")
                else:
                    st.info("No seed files found. Please add Seed_*.json files to the root directory.")
        
        # Tool Addition
        if st.session_state.current_run:
            st.subheader("🔧 Add Tools")
            
            tool_type = st.radio("Tool Type", ["llm", "code"], horizontal=True)
            step_name = st.text_input("Step Name", value=f"step_{len(st.session_state.flow_state.nodes)}")
            
            if tool_type == "llm":
                available_tools = get_available_llm_tools()
                icon = "🤖"
            else:
                available_tools = get_available_code_tools()
                icon = "💻"
            
            selected_tool = st.selectbox(f"{icon} Select Tool", available_tools)
            
            if st.button("➕ Add Tool to Workflow"):
                if step_name:
                    new_node = app.create_tool_node_with_handles(tool_type, selected_tool, step_name)
                    st.session_state.flow_state.nodes.append(new_node)
                    st.success(f"✅ Added {tool_type} tool: {selected_tool}")
                    st.rerun()
                else:
                    st.warning("Please enter a step name.")
            
            # Input Node Addition
            st.subheader("📝 Add Input Nodes")
            
            input_data_type = st.selectbox("Data Type", ["str", "int", "json", "list"])
            input_value = st.text_area("Value", height=100, placeholder=f"Enter {input_data_type} value...")
            
            if st.button("📝 Add Input Node"):
                new_input_node = app.create_input_node(input_data_type, input_value)
                st.session_state.flow_state.nodes.append(new_input_node)
                st.success(f"✅ Added input node: {input_data_type}")
                st.rerun()
    
    # Main workflow area
    st.subheader("🔄 Workflow Design")
    
    if not st.session_state.current_run:
        st.info("👆 Please create or select a run from the sidebar to start designing your workflow.")
        return
    
    if not st.session_state.flow_state.nodes:
        st.info("🌱 Create a demo seed to start your workflow, then add tools and connect them!")
        return
    
    # Enhanced instructions
    st.info("💡 **Instructions:** Connect the colored handle nodes (🔗) to tool inputs (🔧). Each handle represents a separate output that can be connected independently.")
    
    # Flow diagram
    if st.session_state.flow_state:
        flow_result = streamlit_flow(
            'enhanced_workflow_flow',
            st.session_state.flow_state,
            layout=LayeredLayout(direction='right'),
            fit_view=True,
            show_controls=True,
            show_minimap=True,
            height=700,
            get_edge_on_click=True,
            get_node_on_click=True
        )
        
        # Update session state with flow result
        if flow_result:
            st.session_state.flow_state = flow_result
        
        # Handle node interactions
        if hasattr(flow_result, 'selected_id') and flow_result.selected_id:
            selected_node = next((n for n in flow_result.nodes if n.id == flow_result.selected_id), None)
            if selected_node:
                app.display_node_editor(selected_node)

if __name__ == "__main__":
    main()
