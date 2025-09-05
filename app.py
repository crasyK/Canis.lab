import streamlit as st
import json
import os
import time
from lib.state_managment import complete_running_step
from lib.directory_manager import dir_manager
from lib.progress_tracker import ProgressTracker, BatchProgressTracker
from datetime import datetime, timedelta


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

def get_batch_progress_info(workflow_name, batch_id):
    """Get detailed progress information for a batch"""
    try:
        batch_tracker = BatchProgressTracker(workflow_name)
        batch_data = batch_tracker.get_batch_progress(batch_id)
        return batch_data
    except:
        return None

def format_duration(duration):
    """Format duration in a human-readable way"""
    if isinstance(duration, (int, float)):
        duration = timedelta(seconds=duration)
    
    total_seconds = int(duration.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def estimate_remaining_time(batch_data):
    """Estimate remaining time for batch completion"""
    progress_pct = batch_data.get('progress_pct', 0)
    created_time = batch_data.get('created_time')
    
    if progress_pct <= 0 or not created_time:
        return None
    
    elapsed = time.time() - created_time
    estimated_total = elapsed / (progress_pct / 100)
    remaining = estimated_total - elapsed
    
    if remaining > 0:
        return format_duration(remaining)
    return None

def get_enhanced_workflow_info(workflow):
    """Get enhanced workflow information with progress details"""
    enhanced_info = workflow.copy()
    
    # Add progress information for running batches
    enhanced_batches = []
    for batch in workflow['running_batches']:
        batch_progress = get_batch_progress_info(workflow['name'], batch['batch_id'])
        enhanced_batch = batch.copy()
        
        if batch_progress:
            enhanced_batch.update({
                'progress_pct': batch_progress.get('progress_pct', 0),
                'elapsed_time': None,
                'estimated_remaining': None
            })
            
            # Calculate elapsed time
            if 'created_time' in batch_progress:
                created_time = datetime.fromtimestamp(batch_progress['created_time'])
                elapsed = datetime.now() - created_time
                enhanced_batch['elapsed_time'] = format_duration(elapsed)
                enhanced_batch['estimated_remaining'] = estimate_remaining_time(batch_progress)
        
        enhanced_batches.append(enhanced_batch)
    
    enhanced_info['running_batches'] = enhanced_batches
    return enhanced_info


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

if workflows:
    st.subheader("🌍 Global Progress Overview")
    
    # Calculate global statistics
    total_steps = sum(w['steps'] for w in workflows)
    total_running_batches = sum(len(w['running_batches']) for w in workflows)
    
    # Global progress metrics
    progress_col1, progress_col2, progress_col3, progress_col4 = st.columns(4)
    
    with progress_col1:
        st.metric("📊 Total Workflows", len(workflows))
    
    with progress_col2:
        st.metric("🔧 Total Steps", total_steps)
    
    with progress_col3:
        active_workflows = len([w for w in workflows if w['status'] in ['running', 'running_chip']])
        st.metric("⚡ Active Workflows", active_workflows)
    
    with progress_col4:
        st.metric("🚀 Running Operations", total_running_batches)
    
    # Global progress bar - UPDATED to treat "finalized" as the true completion
    if len(workflows) > 0:
        finalized_workflows = len([w for w in workflows if w['status'] == 'finalized'])
        completed_workflows = len([w for w in workflows if w['status'] in ['completed', 'finalized']])
        global_progress = finalized_workflows / len(workflows)  # Only count finalized as truly complete
        st.progress(global_progress)
        st.caption(f"Global Finalization: {global_progress:.1%} ({finalized_workflows}/{len(workflows)} workflows finalized)")
        
        # Additional info about completion vs finalization
        if completed_workflows > finalized_workflows:
            st.caption(f"📋 Additional {completed_workflows - finalized_workflows} workflows completed but not yet finalized")
    
    st.divider()


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
    # Add progress view toggle - THIS WAS IN THE WRONG PLACE BEFORE
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📊 All Workflows")
    with col2:
        detailed_view = st.toggle("📈 Detailed Progress", key="detailed_progress_view")
    
    # Display workflows in a grid
    cols = st.columns(2)
    
    for i, workflow in enumerate(workflows):
        enhanced_workflow = get_enhanced_workflow_info(workflow)
        
        with cols[i % 2]:
            with st.container():
                # Workflow header
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    # Enhanced status indicator with "finalized"
                    if workflow['status'] == 'running':
                        st.markdown(f"🟡 **{workflow['name']}**")
                    elif workflow['status'] == 'running_chip':
                        st.markdown(f"🟠 **{workflow['name']}** (Chip)")
                    elif workflow['status'] == 'completed':
                        st.markdown(f"🟢 **{workflow['name']}** (Completed)")
                    elif workflow['status'] == 'finalized':
                        st.markdown(f"✅ **{workflow['name']}** (Finalized)")
                    elif workflow['status'] == 'failed':
                        st.markdown(f"🔴 **{workflow['name']}**")
                    else:
                        st.markdown(f"⚪ **{workflow['name']}**")
                
                with col2:
                    st.caption(f"{workflow['steps']} steps")
                    # Add overall progress if available - FIXED to account for finalized
                    if workflow['status'] in ['running', 'running_chip'] and workflow['steps'] > 0:
                        try:
                            state_data = dir_manager.load_json(workflow['state_file'])
                            completed_steps = len([s for s in state_data.get('state_steps', []) 
                                                 if s.get('status') in ['completed', 'finalized']])
                            progress_pct = completed_steps / workflow['steps']
                            st.progress(progress_pct)
                            st.caption(f"{progress_pct:.0%} complete")
                        except:
                            pass
                    elif workflow['status'] == 'finalized':
                        st.progress(1.0)  # 100% for finalized workflows
                        st.caption("✅ 100% finalized")
                
                with col3:
                    if st.button("📝 Edit", key=f"edit_{workflow['name']}"):
                        st.session_state.selected_workflow = workflow['name']
                        st.switch_page("pages/workflow_editor.py")
                
                # Enhanced running batches display
                if enhanced_workflow['running_batches']:
                    if detailed_view:
                        # Detailed progress view
                        st.markdown("**🚀 Running Operations:**")
                        for batch in enhanced_workflow['running_batches']:
                            with st.expander(f"🔄 {batch['step_name']} ({batch['tool']})", expanded=True):
                                batch_col1, batch_col2 = st.columns([2, 1])
                                
                                with batch_col1:
                                    # Progress bar if available
                                    progress_pct = batch.get('progress_pct', 0)
                                    if progress_pct > 0:
                                        st.progress(progress_pct / 100)
                                        st.caption(f"Progress: {progress_pct:.1f}%")
                                    else:
                                        st.progress(0.5)  # Indeterminate
                                        st.caption("Processing...")
                                    
                                    # Time information
                                    if batch.get('elapsed_time'):
                                        st.write(f"**Running for:** {batch['elapsed_time']}")
                                    
                                    if batch.get('estimated_remaining'):
                                        st.write(f"**Est. remaining:** {batch['estimated_remaining']}")
                                    
                                    st.caption(f"Batch ID: {batch['batch_id']}")
                                
                                with batch_col2:
                                    if st.button("🔍 Check", key=f"check_detailed_{workflow['name']}_{batch['batch_id']}", 
                                               help="Check and complete batch"):
                                        result = check_and_complete_batch(workflow['name'], workflow['state_file'])
                                        st.toast(f"Batch result: {result}")
                                        time.sleep(1)
                                        st.rerun()
                    else:
                        # Simple view (your original)
                        st.markdown("**Running Batches:**")
                        for batch in workflow['running_batches']:
                            batch_col1, batch_col2 = st.columns([3, 1])
                            
                            with batch_col1:
                                st.write(f"• {batch['step_name']} ({batch['tool']})")
                                # Add mini progress bar if available
                                progress_pct = batch.get('progress_pct', 0)
                                if progress_pct > 0:
                                    st.progress(progress_pct / 100)
                                    st.caption(f"{progress_pct:.0f}% complete")
                                else:
                                    st.caption(f"Batch ID: {batch['batch_id']}")
                            
                            with batch_col2:
                                if st.button("🔍", key=f"check_{workflow['name']}_{batch['batch_id']}", 
                                           help="Check and complete batch"):
                                    result = check_and_complete_batch(workflow['name'], workflow['state_file'])
                                    st.toast(f"Batch result: {result}")
                                    time.sleep(1)
                                    st.rerun()
                
                st.divider()

st.sidebar.markdown("### 📈 System Status")

workflows = get_all_workflows()
running_count = len([w for w in workflows if w['status'] in ['running', 'running_chip']])
completed_count = len([w for w in workflows if w['status'] == 'completed'])
finalized_count = len([w for w in workflows if w['status'] == 'finalized'])
failed_count = len([w for w in workflows if w['status'] == 'failed'])
total_batches = sum(len(w['running_batches']) for w in workflows)

# Metrics with enhanced styling - UPDATED
col1, col2 = st.sidebar.columns(2)
with col1:
    st.metric("🟡 Running", running_count)
    st.metric("🟢 Completed", completed_count)
with col2:
    st.metric("✅ Finalized", finalized_count)
    st.metric("🔴 Failed", failed_count)

# Show active batches count
st.sidebar.metric("⚡ Active Batches", total_batches)

# Active batches detail
if total_batches > 0:
    st.sidebar.markdown("---")
    st.sidebar.markdown("**⚡ Active Operations**")
    
    for workflow in workflows:
        if workflow['running_batches']:
            st.sidebar.markdown(f"**{workflow['name']}:**")
            for batch in workflow['running_batches']:
                # Get progress info
                batch_progress = get_batch_progress_info(workflow['name'], batch['batch_id'])
                
                if batch_progress and batch_progress.get('progress_pct', 0) > 0:
                    progress_pct = batch_progress['progress_pct']
                    st.sidebar.write(f"🔄 {batch['step_name']}")
                    st.sidebar.progress(progress_pct / 100)
                    st.sidebar.caption(f"{progress_pct:.0f}% complete")
                else:
                    st.sidebar.write(f"🔄 {batch['step_name']}")
                    st.sidebar.progress(0.5)  # Indeterminate
                    st.sidebar.caption("Processing...")

# Auto-refresh status
st.sidebar.markdown("---")
current_time = time.time()
if current_time - st.session_state.last_refresh > REFRESH_INTERVAL:
    st.sidebar.success("🔄 Auto-refreshing...")
    st.session_state.last_refresh = current_time
    st.rerun()
else:
    next_refresh = REFRESH_INTERVAL - (current_time - st.session_state.last_refresh)
    st.sidebar.info(f"⏱️ Next refresh in {next_refresh:.0f}s")
