import streamlit as st
import os
import json
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
from streamlit_flow.state import StreamlitFlowState
from uuid import uuid4
from lib.state_managment import create_state, start_seed_step, complete_running_step, use_llm_tool, use_code_tool, get_markers
from lib.tools.llm import get_available_llm_tools, prepare_data
from lib.tools.code import get_available_code_tools, prepare_tool_use
from lib.tools.global_func import get_type, check_data_type, has_connection

class WorkflowApp:
    """Streamlit-based Workflow Designer using Streamlit Flow."""
    
    def __init__(self):
        self.state_directory = "runs/"
        if 'workflow_initialized' not in st.session_state:
            st.session_state.workflow_initialized = True
            st.session_state.flow_state = None
            st.session_state.current_run = None
            self.init_flow_state()
    
    def init_flow_state(self):
        """Initialize the flow state with basic nodes."""
        nodes = [
            StreamlitFlowNode(
                id="start", 
                pos=(100, 100), 
                data={'content': 'Start', 'type': 'start'}, 
                node_type='input',
                source_position='right'
            )
        ]
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
    
    def create_tool_node(self, tool_type: str, tool_name: str, step_name: str) -> StreamlitFlowNode:
        """Create a new tool node."""
        node_id = f"tool_{uuid4()}"
        color = "#4CAF50" if tool_type == "llm" else "#2196F3"
        
        return StreamlitFlowNode(
            id=node_id,
            pos=(300, 200),
            data={
                'content': f"{step_name}\n({tool_type}: {tool_name})",
                'type': 'tool',
                'tool_type': tool_type,
                'tool_name': tool_name,
                'step_name': step_name
            },
            node_type='default',
            source_position='right',
            target_position='left',
            style={'background': color, 'color': 'white'}
        )
    
    def execute_node(self, node_data: dict):
        """Execute a workflow node."""
        if not st.session_state.current_run:
            st.error("No run selected. Please select a run first.")
            return
            
        state_file_path = os.path.join(self.state_directory, st.session_state.current_run, "state.json")
        
        if node_data['type'] == 'start':
            st.success("Workflow started!")
        elif node_data['type'] == 'tool':
            tool_type = node_data['tool_type']
            tool_name = node_data['tool_name']
            step_name = node_data['step_name']
            
            try:
                if tool_type == "llm":
                    # Get required data mapping
                    tool_requirements = prepare_data(tool_name)["in"]
                    available_markers = get_markers(state_file_path)
                    
                    # For demo purposes, we'll use a simple mapping
                    data = {}
                    for req_marker, req_type in tool_requirements.items():
                        matching_markers = [m for m in available_markers if m["name"] == req_marker]
                        if matching_markers:
                            data[req_marker] = matching_markers[0]["name"]
                    
                    result = use_llm_tool(state_file_path, step_name, tool_name, data)
                    st.success(f"LLM tool '{tool_name}' executed successfully!")
                    
                else:  # code tool
                    tool_requirements = prepare_tool_use(tool_name)["in"]
                    available_markers = get_markers(state_file_path)
                    
                    data = {}
                    for req_marker, req_type in tool_requirements.items():
                        matching_markers = [m for m in available_markers if m["name"] == req_marker]
                        if matching_markers:
                            data[req_marker] = matching_markers[0]["name"]
                    
                    result = use_code_tool(state_file_path, step_name, tool_name, data)
                    st.success(f"Code tool '{tool_name}' executed successfully!")
                    
            except Exception as e:
                st.error(f"Error executing tool: {e}")

def main():
    """Main Streamlit app for Workflow Designer."""
    st.set_page_config(
        page_title="Workflow Designer",
        page_icon="⚙️",
        layout="wide"
    )
    
    app = WorkflowApp()
    
    # Header
    st.title("⚙️ Workflow Designer")
    st.markdown("### Design and Execute Synthetic Data Generation Workflows")
    
    # Sidebar controls
    with st.sidebar:
        st.header("🎛️ Controls")
        
        # Run Management
        st.subheader("📁 Run Management")
        
        # Create new run
        with st.expander("➕ Create New Run"):
            new_run_name = st.text_input("Run Name")
            if st.button("Create Run") and new_run_name:
                try:
                    state = create_state(new_run_name)
                    st.success(f"Run created: {state['name']}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating run: {e}")
        
        # Select existing run
        available_runs = app.get_available_runs()
        if available_runs:
            selected_run = st.selectbox("Select Run", available_runs)
            if st.button("Load Run"):
                st.session_state.current_run = selected_run
                st.success(f"Loaded run: {selected_run}")
                st.rerun()
        
        if st.session_state.current_run:
            st.info(f"Current Run: {st.session_state.current_run}")
            
            # Seed file management
            st.subheader("🌱 Seed Management")
            seed_files = app.get_available_seed_files()
            if seed_files:
                selected_seed = st.selectbox("Seed File", seed_files)
                if st.button("Start Seed Step"):
                    try:
                        state_file_path = os.path.join(app.state_directory, st.session_state.current_run, "state.json")
                        result = start_seed_step(state_file_path, selected_seed)
                        st.success("Seed step started!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error starting seed step: {e}")
        
        # Tool Addition
        st.subheader("🔧 Add Tools")
        
        tool_type = st.radio("Tool Type", ["llm", "code"])
        step_name = st.text_input("Step Name", value=f"step_{len(st.session_state.flow_state.nodes)}")
        
        if tool_type == "llm":
            available_tools = get_available_llm_tools()
        else:
            available_tools = get_available_code_tools()
            
        selected_tool = st.selectbox("Select Tool", available_tools)
        
        if st.button("Add Tool to Workflow"):
            new_node = app.create_tool_node(tool_type, selected_tool, step_name)
            st.session_state.flow_state.nodes.append(new_node)
            st.rerun()
    
    # Main workflow area
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("🔄 Workflow Design")
        
        # Flow diagram
        if st.session_state.flow_state:
            flow_result = streamlit_flow(
                'workflow_flow',
                st.session_state.flow_state,
                layout='layered',
                fit_view=True,
                show_controls=True,
                show_minimap=True,
                height=500
            )
            
            # Update session state with any changes
            if flow_result:
                st.session_state.flow_state = flow_result
                
            # Handle node interactions
            if hasattr(flow_result, 'selected_id') and flow_result.selected_id:
                selected_node = next((n for n in flow_result.nodes if n.id == flow_result.selected_id), None)
                if selected_node and st.button("Execute Selected Node"):
                    app.execute_node(selected_node.data)
    
    with col2:
        st.subheader("📊 Workflow Info")
        
        if st.session_state.flow_state:
            st.metric("Nodes", len(st.session_state.flow_state.nodes))
            st.metric("Edges", len(st.session_state.flow_state.edges))
            
            # Show node details
            with st.expander("Node Details"):
                for node in st.session_state.flow_state.nodes:
                    st.write(f"**{node.id}**: {node.data.get('content', 'No content')}")
        
        # Current markers (if run is loaded)
        if st.session_state.current_run:
            try:
                state_file_path = os.path.join(app.state_directory, st.session_state.current_run, "state.json")
                if os.path.exists(state_file_path):
                    markers = get_markers(state_file_path)
                    with st.expander("Available Markers"):
                        for marker in markers:
                            st.write(f"**{marker['name']}**: {marker['type']}")
            except Exception as e:
                st.error(f"Error loading markers: {e}")

if __name__ == "__main__":
    main()
