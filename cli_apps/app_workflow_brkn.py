# workflow_editor.py
import streamlit as st
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
from streamlit_flow.state import StreamlitFlowState
from lib.app_objects import step, create_complete_flow_from_state
from lib.state_managment import (
    create_state, start_seed_step, complete_running_step,
    use_llm_tool, use_code_tool, get_markers, get_uploaded_markers
)
from lib.tools.llm import get_available_llm_tools, prepare_data
from lib.tools.code import get_available_code_tools, prepare_tool_use
from lib.tools.global_func import get_type, check_data_type, has_connection
import json
import os
import time

# Page config
st.set_page_config(page_title="Workflow Editor", layout="wide")

# Initialize session state
if 'current_state_file' not in st.session_state:
    st.session_state.current_state_file = None
if 'flow_state' not in st.session_state:
    st.session_state.flow_state = None
if 'selected_node' not in st.session_state:
    st.session_state.selected_node = None
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'last_batch_result' not in st.session_state:
    st.session_state.last_batch_result = None
if 'show_batch_result' not in st.session_state:
    st.session_state.show_batch_result = False
if 'pending_steps' not in st.session_state:
    st.session_state.pending_steps = []
if 'force_refresh' not in st.session_state:
    st.session_state.force_refresh = False

def load_workflow_state(state_file_path):
    """Load and visualize workflow state"""
    try:
        with open(state_file_path, 'r') as f:
            state_data = json.load(f)
        flow_data = create_complete_flow_from_state(state_data)
        nodes = flow_data['nodes']
        edges = flow_data['edges']
        st.session_state.flow_state = StreamlitFlowState(nodes, edges)
        st.session_state.current_state_file = state_file_path
        return state_data
    except Exception as e:
        st.error(f"Error loading workflow: {e}")
        return None

def refresh_workflow():
    """Refresh the current workflow visualization"""
    if st.session_state.current_state_file:
        load_workflow_state(st.session_state.current_state_file)

def get_available_runs():
    """Get list of available workflow runs"""
    runs_dir = "runs/"
    if os.path.exists(runs_dir):
        return [d for d in os.listdir(runs_dir) if os.path.isdir(os.path.join(runs_dir, d))]
    return []

def add_pending_step(step_type, step_name, tool_name):
    """Add a step to pending execution queue"""
    pending_step = {
        'type': step_type,
        'name': step_name,
        'tool': tool_name,
        'connections': {}  # Will be filled when user connects edges
    }
    st.session_state.pending_steps.append(pending_step)

def get_edge_connections(flow_state):
    """Extract edge connections from the flow state"""
    connections = {}
    for edge in flow_state.edges:
        # Parse edge to understand source->target connections
        source_id = edge.source
        target_id = edge.target
        
        # Map connections for pending steps
        for i, pending_step in enumerate(st.session_state.pending_steps):
            # Check if this edge connects to a pending step
            if target_id.startswith(f'pending_{i}_'):
                connections[pending_step['name']] = connections.get(pending_step['name'], {})
                # Extract marker name from target_id
                marker_name = target_id.split('_')[-1]
                # Find source marker name
                source_marker = source_id.split('-')[-1]
                connections[pending_step['name']][marker_name] = source_marker
    
    return connections

# Main UI
st.title("🔄 Workflow Editor")

# Check if we need to force refresh the workflow (for operations that change the underlying state)
if st.session_state.force_refresh:
    refresh_workflow()
    st.session_state.force_refresh = False

# Sidebar for workflow management
with st.sidebar:
    st.header("Workflow Management")
    # Create new workflow
    with st.expander("📝 Create New Workflow"):
        new_run_name = st.text_input("Run Name:")
        if st.button("Create Workflow"):
            if new_run_name:
                try:
                    state = create_state(new_run_name)
                    st.success(f"Created workflow: {state['name']}")
                    st.session_state.current_state_file = f"runs/{state['name']}/state.json"
                    refresh_workflow()
                except Exception as e:
                    st.error(f"Error creating workflow: {e}")
    # Load existing workflow
    st.subheader("📂 Load Existing Workflow")
    available_runs = get_available_runs()
    if available_runs:
        selected_run = st.selectbox("Select Workflow:", available_runs)
        if st.button("Load Workflow"):
            state_file_path = f"runs/{selected_run}/state.json"
            state_data = load_workflow_state(state_file_path)
            if state_data:
                st.success(f"Loaded workflow: {selected_run}")
    else:
        st.info("No workflows found. Create a new one!")
    # Auto-refresh toggle
    st.session_state.auto_refresh = st.checkbox("Auto-refresh (5s)", value=st.session_state.auto_refresh)
    # Manual refresh
    if st.button("🔄 Refresh"):
        refresh_workflow()

# Main content area
if st.session_state.current_state_file and st.session_state.flow_state:
    # Load current state data
    with open(st.session_state.current_state_file, 'r') as f:
        current_state_data = json.load(f)
    # Workflow info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Workflow", current_state_data['name'])
    with col2:
        st.metric("Status", current_state_data['status'])
    with col3:
        st.metric("Steps", len(current_state_data['state_steps']))
    
    # Action buttons
    st.subheader("🛠️ Workflow Actions")
    action_col1, action_col2, action_col3, action_col4 = st.columns(4)
    
    with action_col1:
        if st.button("🌱 Start Seed Step"):
            st.session_state.show_seed_dialog = True
    
    with action_col2:
        if st.button("🤖 Add LLM Tool"):
            st.session_state.show_llm_dialog = True
    
    with action_col3:
        if st.button("⚙️ Add Code Tool"):
            st.session_state.show_code_dialog = True
    
    with action_col4:
        # Run button to execute configured steps
        if st.session_state.pending_steps:
            if st.button("▶️ Run Configured Steps"):
                st.session_state.show_run_dialog = True
        else:
            st.button("▶️ Run Configured Steps", disabled=True, help="No pending steps to run")
    
    # Display pending steps
    if st.session_state.pending_steps:
        st.subheader("⏳ Pending Steps")
        for i, pending_step in enumerate(st.session_state.pending_steps):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.write(f"**{pending_step['name']}**")
            with col2:
                st.write(f"{pending_step['type'].upper()}: {pending_step['tool']}")
            with col3:
                if st.button("❌", key=f"remove_pending_{i}"):
                    st.session_state.pending_steps.pop(i)
                    st.rerun()
        st.divider()
    
    # Display stored batch results
    if st.session_state.show_batch_result and st.session_state.last_batch_result:
        st.subheader("📊 Last Batch Operation Result")
        
        result = st.session_state.last_batch_result
        
        # Handle the result display
        if isinstance(result, tuple) and len(result) == 2:
            message, counts = result
            
            # Display the main message
            if "completed successfully" in str(message):
                st.success(f"✅ {message}")
            elif "failed" in str(message):
                st.error(f"❌ {message}")
            elif "in progress" in str(message):
                st.warning(f"⏳ {message}")
            else:
                st.info(f"ℹ️ {message}")
            
            # Display detailed batch information
            if isinstance(counts, dict):
                # Create metrics columns
                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                
                with metric_col1:
                    completed = counts.get("completed", 0)
                    st.metric("✅ Completed", completed)
                
                with metric_col2:
                    failed = counts.get("failed", 0)
                    if failed > 0:
                        st.metric("❌ Failed", failed, delta=f"-{failed}")
                    else:
                        st.metric("❌ Failed", failed)
                
                with metric_col3:
                    total = counts.get("total", 0)
                    st.metric("📝 Total", total)
                
                with metric_col4:
                    if st.button("❌ Clear Result"):
                        st.session_state.show_batch_result = False
                        st.session_state.last_batch_result = None
                        st.rerun()
                
                # Progress bar
                if total > 0:
                    progress = completed / total
                    st.progress(progress, text=f"Progress: {completed}/{total} ({progress:.1%})")
                
                # Show error details if present
                if "error" in counts and counts["error"]:
                    with st.expander("🔍 Error Details", expanded=False):
                        error_info = counts["error"]
                        st.json(error_info if isinstance(error_info, dict) else str(error_info))
            else:
                st.write(f"Status: {counts}")
        else:
            # Handle simple string results
            st.info(f"Result: {result}")
            if st.button("❌ Clear Result##simple"):
                st.session_state.show_batch_result = False
                st.session_state.last_batch_result = None
                st.rerun()
        
        st.divider()
    
    # Batch Job Monitoring (FIXED - no immediate refresh)
    if current_state_data['status'] == 'running':
        st.subheader("⏳ Running Batch Jobs")
        # Find the last running step
        running_steps = [step for step in current_state_data['state_steps']
                        if step.get('status') in ['uploaded', 'in_progress']]
        if running_steps:
            latest_step = running_steps[-1]
            if 'batch' in latest_step and latest_step['batch'].get('upload_id'):
                batch_id = latest_step['batch']['upload_id']
                # Create a monitoring card
                with st.container():
                    st.write(f"**{latest_step['name']}** - {latest_step.get('tool_name', 'Unknown Tool')}")
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"Batch ID: `{batch_id}`")
                        st.write(f"Status: {latest_step['status']}")
                    with col2:
                        if st.button("🔍 Check Status & Complete"):
                            try:
                                # FIXED: Don't refresh immediately, just store results
                                result = complete_running_step(st.session_state.current_state_file)
                                
                                # Store the result in session state
                                st.session_state.last_batch_result = result
                                st.session_state.show_batch_result = True
                                
                                # FIXED: Set flag to refresh on next cycle instead of immediate refresh
                                st.session_state.force_refresh = True
                                
                            except Exception as e:
                                st.session_state.last_batch_result = f"Error: {e}"
                                st.session_state.show_batch_result = True
    
    # Run configured steps dialog
    if st.session_state.get('show_run_dialog', False):
        with st.expander("▶️ Run Configured Steps", expanded=True):
            st.write("**Steps to execute:**")
            
            # Get current edge connections
            connections = get_edge_connections(st.session_state.flow_state)
            
            for pending_step in st.session_state.pending_steps:
                st.write(f"- {pending_step['name']} ({pending_step['type']}: {pending_step['tool']})")
                
                # Show connections if any
                if pending_step['name'] in connections:
                    st.write(f"  Connections: {connections[pending_step['name']]}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("▶️ Execute All"):
                    try:
                        # Execute each pending step
                        for pending_step in st.session_state.pending_steps:
                            step_connections = connections.get(pending_step['name'], {})
                            
                            if pending_step['type'] == 'llm':
                                use_llm_tool(
                                    st.session_state.current_state_file,
                                    pending_step['name'],
                                    pending_step['tool'],
                                    step_connections
                                )
                            else:  # code
                                use_code_tool(
                                    st.session_state.current_state_file,
                                    pending_step['name'],
                                    pending_step['tool'],
                                    step_connections
                                )
                        
                        # Clear pending steps
                        st.session_state.pending_steps = []
                        st.session_state.show_run_dialog = False
                        st.success("All steps executed successfully!")
                        st.session_state.force_refresh = True
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error executing steps: {e}")
            
            with col2:
                if st.button("Cancel##run"):
                    st.session_state.show_run_dialog = False
                    st.rerun()
    
    # Seed step dialog
    if st.session_state.get('show_seed_dialog', False):
        with st.expander("🌱 Start Seed Step", expanded=True):
            seed_file = st.text_input("Seed file path:")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Start Seed"):
                    if seed_file:
                        try:
                            start_seed_step(st.session_state.current_state_file, seed_file)
                            st.success("Seed step started!")
                            st.session_state.show_seed_dialog = False
                            st.session_state.force_refresh = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error starting seed: {e}")
            with col2:
                if st.button("Cancel"):
                    st.session_state.show_seed_dialog = False
                    st.rerun()
    
    # LLM tool dialog (simplified - no marker selection)
    if st.session_state.get('show_llm_dialog', False):
        with st.expander("🤖 Add LLM Tool", expanded=True):
            step_name = st.text_input("Step Name:")
            available_llm_tools = get_available_llm_tools()
            selected_llm_tool = st.selectbox("Select LLM Tool:", available_llm_tools)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Add LLM Tool"):
                    if step_name and selected_llm_tool:
                        add_pending_step('llm', step_name, selected_llm_tool)
                        st.success(f"LLM tool '{selected_llm_tool}' added to pending steps!")
                        st.session_state.show_llm_dialog = False
                        st.rerun()
                    else:
                        st.warning("Please fill in step name and select a tool.")
            with col2:
                if st.button("Cancel##llm"):
                    st.session_state.show_llm_dialog = False
                    st.rerun()
    
    # Code tool dialog (simplified - no marker selection)
    if st.session_state.get('show_code_dialog', False):
        with st.expander("⚙️ Add Code Tool", expanded=True):
            step_name = st.text_input("Step Name:##code")
            available_code_tools = get_available_code_tools()
            selected_code_tool = st.selectbox("Select Code Tool:", available_code_tools)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Add Code Tool"):
                    if step_name and selected_code_tool:
                        add_pending_step('code', step_name, selected_code_tool)
                        st.success(f"Code tool '{selected_code_tool}' added to pending steps!")
                        st.session_state.show_code_dialog = False
                        st.rerun()
                    else:
                        st.warning("Please fill in step name and select a tool.")
            with col2:
                if st.button("Cancel##code"):
                    st.session_state.show_code_dialog = False
                    st.rerun()
    
    # Workflow visualization
    st.subheader("📊 Workflow Visualization")
    
    # FIXED: Consistent state management for dragging
    updated_flow_state = streamlit_flow(
        'workflow_editor',
        st.session_state.flow_state,
        fit_view=True,
        height=600,
        enable_node_menu=True,
        enable_edge_menu=True,
        enable_pane_menu=True,
        get_edge_on_click=True,
        get_node_on_click=True,
        show_minimap=True,
        hide_watermark=True,
        allow_new_edges=True,  # Enable edge creation for connections
        min_zoom=0.1
    )
    
    # FIXED: Handle node updates (dragging) - consistent with the SAME state object
    nodes_updated = False
    for node in updated_flow_state.nodes:
        if 'parent' in node.id:
            current_pos = tuple(dict(node.position).values())
            prev_pos = tuple(node.data["prev_pos"])
            if current_pos != prev_pos:
                step_number = int(node.id.split('-')[0])
                step_instance = step.get_instance_by_number(step_number)
                if step_instance:
                    # Update nodes for this step
                    updated_nodes = step_instance.return_step(current_pos)
                    # Replace nodes for this step in the SAME state object
                    updated_flow_state.nodes = [
                        n for n in updated_flow_state.nodes
                        if not n.id.startswith(f'{step_number}-')
                    ]
                    updated_flow_state.nodes.extend(updated_nodes)
                    nodes_updated = True
    
    # FIXED: Always keep the SAME state object reference
    st.session_state.flow_state = updated_flow_state
    
    if nodes_updated:
        st.rerun()
    
    # Node/Edge selection info
    if updated_flow_state.selected_id:
        selected_id = updated_flow_state.selected_id
        # Find the selected node
        selected_node = None
        for node in updated_flow_state.nodes:
            if node.id == selected_id:
                selected_node = node
                break
        if selected_node:
            st.subheader(f"Selected Node: {selected_node.data.get('content', 'Unknown')}")
            # Show node details
            if 'parent' in selected_node.id:
                step_number = int(selected_node.id.split('-')[0])
                if step_number <= len(current_state_data['state_steps']):
                    step_data = current_state_data['state_steps'][step_number - 1]
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Step Information:**")
                        st.write(f"Name: {step_data['name']}")
                        st.write(f"Type: {step_data['type']}")
                        st.write(f"Status: {step_data['status']}")
                        if 'tool_name' in step_data:
                            st.write(f"Tool: {step_data['tool_name']}")
                    with col2:
                        st.write("**Data Flow:**")
                        st.write(f"Inputs: {len(step_data['data']['in'])}")
                        st.write(f"Outputs: {len(step_data['data']['out'])}")
                        if step_data['type'] == 'llm' and 'batch' in step_data:
                            batch_id = step_data['batch'].get('upload_id', 'N/A')
                            st.write(f"Batch ID: {batch_id}")
            elif 'in-' in selected_node.id or 'out-' in selected_node.id:
                # Handle input/output node selection
                st.write("**Marker Information:**")
                node_content = selected_node.data.get('content', 'Unknown')
                st.write(f"Marker Name: {node_content}")
                # Find marker details in state
                for marker in current_state_data['nodes']:
                    if marker['name'] == node_content:
                        st.write(f"Type: {marker['type']}")
                        st.write(f"State: {marker['state']}")
                        st.write(f"File: {marker['file_name']}")
                        break
        else:
            st.info(f"Selected ID: {selected_id} (Node details not available)")
    
    # Markers table
    st.subheader("📋 Available Markers")
    markers_data = []
    for marker in current_state_data['nodes']:
        markers_data.append({
            'Name': marker['name'],
            'Type': str(marker['type']),
            'State': marker['state'],
            'File': marker['file_name']
        })
    if markers_data:
        st.dataframe(markers_data, use_container_width=True)
    
    # Auto-refresh functionality
    if st.session_state.auto_refresh:
        time.sleep(5)
        refresh_workflow()
        st.rerun()

else:
    st.info("👆 Please create a new workflow or load an existing one from the sidebar.")
    # Show example workflows if any exist
    available_runs = get_available_runs()
    if available_runs:
        st.subheader("📁 Available Workflows")
        for run in available_runs[:5]:  # Show first 5
            if st.button(f"Load {run}", key=f"load_{run}"):
                state_file_path = f"runs/{run}/state.json"
                state_data = load_workflow_state(state_file_path)
                if state_data:
                    st.success(f"Loaded workflow: {run}")
                    st.rerun()
