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

# Page config
st.set_page_config(page_title="Workflow Editor", layout="wide")

# Initialize session state for workflow editor
if 'current_workflow' not in st.session_state:
    st.session_state.current_workflow = None
if 'flow_state' not in st.session_state:
    st.session_state.flow_state = None
if 'pending_steps' not in st.session_state:
    st.session_state.pending_steps = []

def get_available_seed_files():
    """Get list of available seed files from seed_files directory"""
    seed_files_dir = "seed_files/"
    seed_files = []
    
    if os.path.exists(seed_files_dir):
        for file in os.listdir(seed_files_dir):
            if file.endswith('.json'):
                try:
                    # Validate it's a proper seed file by checking structure
                    file_path = os.path.join(seed_files_dir, file)
                    with open(file_path, 'r') as f:
                        seed_data = json.load(f)
                    
                    # Check if it has the required seed file structure
                    if isinstance(seed_data, dict):
                        # If it's a seed progress file, extract the actual seed
                        if 'seed_file' in seed_data:
                            actual_seed = seed_data['seed_file']
                        else:
                            actual_seed = seed_data
                        
                        # Validate seed file structure
                        if ('variables' in actual_seed and 
                            'constants' in actual_seed and 
                            'call' in actual_seed):
                            seed_files.append({
                                'filename': file,
                                'path': file_path,
                                'display_name': file.replace('.json', '').replace('_', ' ').title()
                            })
                
                except (json.JSONDecodeError, KeyError):
                    # Skip invalid JSON files
                    continue
    
    return seed_files

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

def load_workflow_state(workflow_name):
    """Load workflow state without auto-refresh"""
    try:
        state_file_path = f"runs/{workflow_name}/state.json"
        with open(state_file_path, 'r') as f:
            state_data = json.load(f)
        
        flow_data = create_complete_flow_from_state(state_data)
        nodes = flow_data['nodes']
        edges = flow_data['edges']
        
        # Apply visual state based on step status (greyed out, etc.)
        nodes = apply_visual_states(nodes, state_data)
        
        st.session_state.flow_state = StreamlitFlowState(nodes, edges)
        st.session_state.current_workflow = workflow_name
        return state_data
    except Exception as e:
        st.error(f"Error loading workflow: {e}")
        return None

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
        source_id = edge.source
        target_id = edge.target
        
        for i, pending_step in enumerate(st.session_state.pending_steps):
            if target_id.startswith(f'pending_{i}_'):
                connections[pending_step['name']] = connections.get(pending_step['name'], {})
                marker_name = target_id.split('_')[-1]
                source_marker = source_id.split('-')[-1]
                connections[pending_step['name']][marker_name] = source_marker
    
    return connections

# Header with navigation
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("🏠 Back to Dashboard"):
        st.switch_page("app.py")

with col2:
    st.title("🔄 Workflow Editor")

with col3:
    # Manual refresh only (no auto-refresh)
    if st.button("🔄 Refresh"):
        if st.session_state.current_workflow:
            load_workflow_state(st.session_state.current_workflow)
            st.rerun()

# Load workflow (from homepage selection or dropdown)
selected_workflow = st.session_state.get('selected_workflow')
if selected_workflow and selected_workflow != st.session_state.current_workflow:
    state_data = load_workflow_state(selected_workflow)
    if state_data:
        st.success(f"Loaded workflow: {selected_workflow}")

# Sidebar for workflow management (simplified)
with st.sidebar:
    st.header("Workflow Management")
    
    # Workflow selector
    available_runs = get_available_runs()
    if available_runs:
        current_selection = st.selectbox(
            "Select Workflow:", 
            available_runs,
            index=available_runs.index(st.session_state.current_workflow) if st.session_state.current_workflow in available_runs else 0
        )
        
        if current_selection != st.session_state.current_workflow:
            state_data = load_workflow_state(current_selection)
            if state_data:
                st.success(f"Loaded workflow: {current_selection}")
                st.rerun()
    
    # Create new workflow
    with st.expander("📝 Create New Workflow"):
        new_run_name = st.text_input("Run Name:")
        if st.button("Create Workflow"):
            if new_run_name:
                try:
                    state = create_state(new_run_name)
                    st.success(f"Created workflow: {state['name']}")
                    state_data = load_workflow_state(state['name'])
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating workflow: {e}")
    
    # Quick link to Seed Architect
    st.divider()
    st.markdown("### 🏗️ Tools")
    if st.button("🏗️ Seed Architect", use_container_width=True):
        st.switch_page("pages/seed_architect.py")

# Main workflow editing interface
if st.session_state.current_workflow and st.session_state.flow_state:
    # Load current state data
    state_file_path = f"runs/{st.session_state.current_workflow}/state.json"
    with open(state_file_path, 'r') as f:
        current_state_data = json.load(f)
    
    # Workflow info
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Workflow", current_state_data['name'])
    with col2:
        if current_state_data['status'] == 'running':
            st.metric("Status", "🟡 Running")
        elif current_state_data['status'] == 'completed':
            st.metric("Status", "🟢 Complete")
        elif current_state_data['status'] == 'failed':
            st.metric("Status", "🔴 Failed")
        else:
            st.metric("Status", f"⚪ {current_state_data['status']}")
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
        if st.session_state.pending_steps:
            if st.button("▶️ Run Configured Steps"):
                st.session_state.show_run_dialog = True
        else:
            st.button("▶️ Run Configured Steps", disabled=True)
    
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
    
    # UPDATED SEED STEP DIALOG WITH DROPDOWN
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
                        
                        # Show preview
                        with st.expander("🔍 Preview Seed File", expanded=False):
                            seed_content, metadata = preview_seed_file(selected_seed['path'])
                            
                            if seed_content:
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
                            start_seed_step(st.session_state.current_workflow, seed_file_path)
                            st.success("Seed step started!")
                            st.session_state.show_seed_dialog = False
                            # Manual refresh of visual state
                            load_workflow_state(st.session_state.current_workflow)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error starting seed: {e}")
                    else:
                        st.warning("Please select or enter a seed file path.")
            
            with col2:
                if st.button("Cancel##seed"):
                    st.session_state.show_seed_dialog = False
                    st.rerun()
    
    # LLM tool dialog (same as before)
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
    
    # Code tool dialog (same as before)
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
    
    # Rest of the dialog handling code (run dialog, etc.) - same as before
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
                                    st.session_state.current_workflow,
                                    pending_step['name'],
                                    pending_step['tool'],
                                    step_connections
                                )
                            else:  # code
                                use_code_tool(
                                    st.session_state.current_workflow,
                                    pending_step['name'],
                                    pending_step['tool'],
                                    step_connections
                                )
                        
                        # Clear pending steps
                        st.session_state.pending_steps = []
                        st.session_state.show_run_dialog = False
                        st.success("All steps executed successfully!")
                        load_workflow_state(st.session_state.current_workflow)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error executing steps: {e}")
            
            with col2:
                if st.button("Cancel##run"):
                    st.session_state.show_run_dialog = False
                    st.rerun()
    
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
    
    # Workflow visualization - NO AUTO-REFRESH, only manual updates
    st.subheader("📊 Workflow Visualization")
    
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
        allow_new_edges=True,
        min_zoom=0.1
    )
    
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
    
    # Node/Edge selection info (same as before)
    if updated_flow_state.selected_id:
        selected_id = updated_flow_state.selected_id
        selected_node = None
        for node in updated_flow_state.nodes:
            if node.id == selected_id:
                selected_node = node
                break
        
        if selected_node:
            st.subheader(f"Selected Node: {selected_node.data.get('content', 'Unknown')}")
            
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
                st.write("**Marker Information:**")
                node_content = selected_node.data.get('content', 'Unknown')
                st.write(f"Marker Name: {node_content}")
                
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

else:
    st.info("👆 Please create a new workflow or load an existing one from the sidebar.")
    
    # Show example workflows if any exist
    available_runs = get_available_runs()
    if available_runs:
        st.subheader("📁 Available Workflows")
        for run in available_runs[:5]:  # Show first 5
            if st.button(f"Load {run}", key=f"load_{run}"):
                state_file_path = f"runs/{run}/state.json"
                state_data = load_workflow_state(run)
                if state_data:
                    st.success(f"Loaded workflow: {run}")
                    st.rerun()