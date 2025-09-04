import streamlit as st
import json
import os
import time
from lib.state_managment import complete_running_step
from lib.directory_manager import dir_manager

st.set_page_config(
    page_title="Workflow Dashboard", 
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

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

# Auto-refresh for homepage only
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

# Auto-refresh every 5 seconds on homepage
REFRESH_INTERVAL = 5

def get_all_workflows():
    """Get all workflows with their current status"""
    workflows = []
    
    for run_name in dir_manager.list_workflows():
        try:
            state_file_path = dir_manager.get_state_file_path(run_name)
            state_data = dir_manager.load_json(state_file_path)
            workflows.append({
                'name': run_name,
                'status': state_data['status'],
                'steps': len(state_data['state_steps']),
                'running_batches': get_running_batches(state_data),
                'state_file': str(state_file_path)
            })
        except Exception as e:
            st.error(f"Error loading {run_name}: {e}")
    
    return workflows

def get_running_batches(state_data):
    """Get running batch information"""
    running_batches = []
    for step in state_data['state_steps']:
        if step.get('status') in ['uploaded', 'in_progress'] and 'batch' in step:
            running_batches.append({
                'step_name': step['name'],
                'batch_id': step['batch'].get('upload_id'),
                'status': step['status'],
                'tool': step.get('tool_name', 'Unknown')
            })
    return running_batches

def check_and_complete_batch(workflow_name, state_file):
    """Check and complete running batches"""
    try:
        result = complete_running_step(state_file)
        return result
    except Exception as e:
        return f"Error: {e}"

# Main header with navigation
col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    st.title("🏠 Workflow Dashboard")
    show_persistent_message()
with col2:
    st.markdown("### Your Workflow Management Hub")

# Quick action buttons
st.subheader("🚀 Quick Actions")
action_col1, action_col2, action_col3, action_col4 = st.columns(4)

with action_col1:
    if st.button("➕ New Workflow", use_container_width=True):
        st.switch_page("pages/workflow_editor.py")

with action_col2:
    if st.button("🏗️ Seed Architect", use_container_width=True):
        st.switch_page("pages/seed_architect.py")

with action_col3:
    total_workflows = len(get_all_workflows())
    st.metric("Total Workflows", total_workflows)


st.divider()

# Workflows overview
col1, col2 = st.columns([3, 1])
with col1:
    st.subheader("📊 All Workflows")
with col2:
    if st.button("🔄 Manual Refresh"):
        st.session_state.last_refresh = 0
        st.rerun()

# Get all workflows
workflows = get_all_workflows()

if not workflows:
    st.info("No workflows found. Create one using the Workflow Editor or start with the Seed Architect!")
    
    # Show getting started options
    st.subheader("🎯 Getting Started")
    start_col1, start_col2 = st.columns(2)
    
    with start_col1:
        with st.container():
            st.markdown("**🏗️ Create Seed Files**")
            st.write("Design synthetic data generation templates with AI assistance")
            if st.button("Launch Seed Architect", key="start_architect"):
                st.switch_page("pages/seed_architect.py")
    
    with start_col2:
        with st.container():
            st.markdown("**🔄 Build Workflows**")
            st.write("Create and manage data processing workflows")
            if st.button("Create New Workflow", key="start_workflow"):
                st.switch_page("pages/workflow_editor.py")

else:
    # Display workflows in a grid
    cols = st.columns(2)
    
    for i, workflow in enumerate(workflows):
        with cols[i % 2]:
            with st.container():
                # Workflow header
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    # Status indicator
                    if workflow['status'] == 'running':
                        st.markdown(f"🟡 **{workflow['name']}**")
                    elif workflow['status'] == 'completed':
                        st.markdown(f"🟢 **{workflow['name']}**")
                    elif workflow['status'] == 'failed':
                        st.markdown(f"🔴 **{workflow['name']}**")
                    else:
                        st.markdown(f"⚪ **{workflow['name']}**")
                
                with col2:
                    st.caption(f"{workflow['steps']} steps")
                
                with col3:
                    if st.button("📝 Edit", key=f"edit_{workflow['name']}"):
                        st.session_state.selected_workflow = workflow['name']
                        st.switch_page("pages/workflow_editor.py")
                
                # Running batches
                if workflow['running_batches']:
                    st.markdown("**Running Batches:**")
                    for batch in workflow['running_batches']:
                        batch_col1, batch_col2 = st.columns([3, 1])
                        
                        with batch_col1:
                            st.write(f"• {batch['step_name']} ({batch['tool']})")
                            st.caption(f"Batch ID: {batch['batch_id']}")
                        
                        with batch_col2:
                            if st.button("🔍", key=f"check_{workflow['name']}_{batch['batch_id']}", 
                                       help="Check and complete batch"):
                                result = check_and_complete_batch(workflow['name'], workflow['state_file'])
                                st.toast(f"Batch result: {result}")
                                time.sleep(1)  # Brief pause before refresh
                                st.rerun()
                
                st.divider()

st.sidebar.markdown("### 📈 System Status")

# System overview in sidebar
workflows = get_all_workflows()
running_count = len([w for w in workflows if w['status'] == 'running'])
completed_count = len([w for w in workflows if w['status'] == 'completed'])
total_batches = sum(len(w['running_batches']) for w in workflows)

st.sidebar.metric("🟡 Running", running_count)
st.sidebar.metric("🟢 Completed", completed_count)
st.sidebar.metric("⚡ Active Batches", total_batches)