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
from lib.directory_manager import dir_manager
import json
import os

# Page config
st.set_page_config(page_title="Workflow Editor", layout="wide")

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

def load_workflow_state(workflow_name):
    """Load workflow state without auto-refresh"""
    try:
        state_file_path = dir_manager.get_state_file_path(workflow_name)
        state_data = dir_manager.load_json(state_file_path)
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
    """Add a step and immediately show it in the visual flow"""
    print(f"🔧 Adding pending step: {step_name} ({step_type}: {tool_name})")
    # Ensure current workflow exists
    if not st.session_state.current_workflow:
        set_message('error', "❌ No workflow selected. Please select or create a workflow first.")
        return

    # Initialize pending_steps if it doesn't exist
    if 'pending_steps' not in st.session_state:
        st.session_state.pending_steps = []

    try:
        # Get current state data to determine next step number
        state_file_path = dir_manager.get_state_file_path(st.session_state.current_workflow)
        if not state_file_path.exists():
            set_message('error', f"❌ State file not found for workflow: {st.session_state.current_workflow}")
            return

        current_state_data = dir_manager.load_json(state_file_path)

        # Calculate next step number
        existing_steps = len(current_state_data.get('state_steps', []))
        pending_steps_count = len(st.session_state.pending_steps)
        next_step_number = existing_steps + pending_steps_count + 1

        print(f"📊 Step numbers - Existing: {existing_steps}, Pending: {pending_steps_count}, Next: {next_step_number}")

        # Create step instance using app_objects
        from lib.app_objects import step
        step_instance = step(
            step_number=next_step_number,
            step_name=step_name,
            step_type=step_type,
            tool_name=tool_name,
            position=(100 + next_step_number * 200, 100)  # Position it visually
        )

        # Create pending step with the step instance
        pending_step = {
            'type': step_type,
            'name': step_name,
            'tool': tool_name,
            'step_number': next_step_number,
            'step_instance': step_instance,
            'connections': {}
        }

        # Add to pending steps
        st.session_state.pending_steps.append(pending_step)
        print(f"✅ Added pending step. Total pending: {len(st.session_state.pending_steps)}")

        # IMMEDIATELY update the visual flow
        update_flow_with_pending_steps()

        # Set success message
        set_message('success', f"✅ Added {step_type} step: {step_name}")

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
        print("⚠️ No flow_state found, creating empty one")
        from streamlit_flow import StreamlitFlowState
        st.session_state.flow_state = StreamlitFlowState([], [])

    if not st.session_state.get('pending_steps'):
        print("ℹ️ No pending steps to add")
        return

    try:
        # Get current node IDs to avoid duplicates
        existing_ids = {node.id for node in st.session_state.flow_state.nodes}
        print(f"📋 Existing node IDs: {existing_ids}")

        # Add pending step nodes to the current flow
        for i, pending_step in enumerate(st.session_state.pending_steps):
            print(f"🔧 Processing pending step {i+1}: {pending_step['name']}")
            try:
                # Get step nodes from the step instance
                step_nodes = pending_step['step_instance'].return_step()
                print(f"📦 Step returned {len(step_nodes)} nodes")

                # Add these nodes to the flow state if not already present
                new_nodes = []
                for node in step_nodes:
                    if node.id not in existing_ids:
                        new_nodes.append(node)
                        existing_ids.add(node.id)
                        print(f"➕ Adding new node: {node.id}")
                    else:
                        print(f"⏭️ Skipping existing node: {node.id}")

                if new_nodes:
                    st.session_state.flow_state.nodes.extend(new_nodes)
                    print(f"✅ Added {len(new_nodes)} new nodes to flow")

            except Exception as e:
                print(f"❌ Error processing step {pending_step['name']}: {e}")
                continue

        print(f"🎯 Flow now has {len(st.session_state.flow_state.nodes)} total nodes")

    except Exception as e:
        print(f"❌ Error updating flow with pending steps: {e}")
        import traceback
        traceback.print_exc()

def execute_pending_steps():
    """Execute pending steps with proper directory handling and connections"""
    if not st.session_state.current_workflow:
        set_message('error', "❌ No workflow selected")
        return False

    if not st.session_state.pending_steps:
        set_message('info', "ℹ️ No pending steps to execute")
        return True

    try:
        # Get current edge connections from the flow
        connections = get_edge_connections(st.session_state.flow_state)

        # Execute each pending step
        for pending_step in st.session_state.pending_steps:
            step_connections = connections.get(pending_step['name'], {})
            try:
                # Get proper state file path for the functions
                state_file_path = dir_manager.get_state_file_path(st.session_state.current_workflow)

                if pending_step['type'] == 'llm':
                    use_llm_tool(
                        str(state_file_path),
                        pending_step['name'],
                        pending_step['tool'],
                        step_connections
                    )
                else:  # code
                    use_code_tool(
                        str(state_file_path),
                        pending_step['name'],
                        pending_step['tool'],
                        step_connections
                    )

                print(f"✅ Executed: {pending_step['name']}")

            except Exception as e:
                set_message('error', f"❌ Error executing {pending_step['name']}: {e}")
                return False

        # Clear pending steps after successful execution
        st.session_state.pending_steps = []

        # Reload the workflow state to show updated diagram
        load_workflow_state(st.session_state.current_workflow)

        return True

    except Exception as e:
        set_message('error', f"❌ Execution error: {e}")
        return False

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
        
        # Action buttons
        if st.button("🌱 Start Seed Step", key="sidebar_start_seed_btn", use_container_width=True):
            st.session_state.show_seed_dialog = True
            st.rerun()
        
        if st.button("🤖 Add LLM Tool", key="sidebar_add_llm_btn", use_container_width=True):
            st.session_state.show_llm_dialog = True
            st.rerun()
        
        if st.button("⚙️ Add Code Tool", key="sidebar_add_code_btn", use_container_width=True):
            st.session_state.show_code_dialog = True
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
            
            # Optional description
            workflow_description = st.text_area(
                "Description (optional):",
                placeholder="Briefly describe what this workflow does",
                key="new_workflow_description"
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

    # LLM tool dialog
    if st.session_state.get('show_llm_dialog', False):
        with st.expander("🤖 Add LLM Tool", expanded=True):
            with st.form("llm_form"):
                step_name = st.text_input("Step Name:", key="llm_step_name")
                available_llm_tools = get_available_llm_tools()
                selected_llm_tool = st.selectbox("Select LLM Tool:", available_llm_tools, key="llm_tool_select")

                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("Add LLM Tool")
                    if submitted:
                        if step_name and selected_llm_tool:
                            add_pending_step('llm', step_name, selected_llm_tool)
                            set_message('success', f"🤖 LLM tool '{selected_llm_tool}' added to pending steps!")
                            st.session_state.show_llm_dialog = False
                            st.rerun()
                        else:
                            set_message('warning', "⚠️ Please fill in step name and select a tool.")

                with col2:
                    cancel = st.form_submit_button("Cancel")
                    if cancel:
                        st.session_state.show_llm_dialog = False
                        st.rerun()

    #CODE TOOL DIALOG
    if st.session_state.get('show_code_dialog', False):
        with st.expander("⚙️ Add Code Tool", expanded=True):
            with st.form("code_form"):
                step_name = st.text_input("Step Name:", key="code_step_name")
                available_code_tools = get_available_code_tools()
                selected_code_tool = st.selectbox("Select Code Tool:", available_code_tools, key="code_tool_select")

                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("Add Code Tool")
                    if submitted:
                        if step_name and selected_code_tool:
                            add_pending_step('code', step_name, selected_code_tool)
                            set_message('success', f"⚙️ Code tool '{selected_code_tool}' added to pending steps!")
                            st.session_state.show_code_dialog = False
                            st.rerun()
                        else:
                            set_message('warning', "⚠️ Please fill in step name and select a tool.")

                with col2:
                    cancel = st.form_submit_button("Cancel")
                    if cancel:
                        st.session_state.show_code_dialog = False
                        st.rerun()

    # Display pending steps
    if st.session_state.pending_steps:
        st.subheader("⏳ Pending Steps")
        st.info("💡 These steps are now visible in the diagram below. Connect them to other nodes, then click 'Execute' to run them.")
        for i, pending_step in enumerate(st.session_state.pending_steps):
            col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
            with col1:
                st.write(f"**{pending_step['name']}**")
            with col2:
                st.write(f"{pending_step['type'].upper()}: {pending_step['tool']}")
            with col3:
                st.caption(f"Step #{pending_step['step_number']}")
            with col4:
                if st.button("❌", key=f"remove_pending_{i}", help="Remove this step"):
                    # Remove from pending steps
                    removed_step = st.session_state.pending_steps.pop(i)
                    # Remove from visual flow
                    step_id_prefix = f"{removed_step['step_number']}-"
                    st.session_state.flow_state.nodes = [
                        node for node in st.session_state.flow_state.nodes
                        if not node.id.startswith(step_id_prefix)
                    ]
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
