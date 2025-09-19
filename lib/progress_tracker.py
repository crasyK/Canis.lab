import time
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Optional, Callable, Dict, Any
from .directory_manager import dir_manager
from .tools.batch import check_batch_job, download_batch_results


class ProgressTracker:
    """Comprehensive progress tracking for workflow operations and batch jobs"""
    
    def __init__(self):
        self.current_operation = None
        self.start_time = None
        self.progress_file = None
    
    @contextmanager 
    def track_operation(self, description, total_steps=None, workflow_name=None):
        """Context manager for tracking operation progress"""
        self.current_operation = description
        self.start_time = time.time()
        
        # Create progress file for persistence
        if workflow_name:
            self.progress_file = dir_manager.get_workflow_path(workflow_name) / "progress.json"
            self._save_progress_state({
                'operation': description,
                'start_time': self.start_time,
                'status': 'running',
                'total_steps': total_steps,
                'current_step': 0
            })
        
        try:
            import streamlit as st
            
            if total_steps:
                progress_bar = st.progress(0)
                status_text = st.empty()
                status_text.text(f"Starting {description}...")
                
                # Create progress update function
                def update_progress(step, message=""):
                    progress = min(step / total_steps, 1.0)
                    progress_bar.progress(progress)
                    elapsed = time.time() - self.start_time
                    status_text.text(f"{description}: {message} ({elapsed:.1f}s)")
                    
                    # Update progress file
                    if self.progress_file:
                        progress_data = self._load_progress_state()
                        progress_data.update({
                            'current_step': step,
                            'message': message,
                            'elapsed_time': elapsed
                        })
                        self._save_progress_state(progress_data)
                
                yield update_progress
                
                # Complete
                progress_bar.progress(1.0)
                elapsed = time.time() - self.start_time
                status_text.text(f"Completed {description} ({elapsed:.1f}s)")
                
            else:
                # Simple spinner for unknown duration
                with st.spinner(f"Processing {description}..."):
                    yield lambda step, msg="": self._update_simple_progress(msg)
            
            # Mark as completed
            if self.progress_file:
                progress_data = self._load_progress_state()
                progress_data.update({
                    'status': 'completed',
                    'end_time': time.time(),
                    'total_elapsed': time.time() - self.start_time
                })
                self._save_progress_state(progress_data)
                
        except ImportError:
            # Not in Streamlit context, use console output
            print(f"🚀 Starting {description}...")
            yield lambda step, msg="": print(f"  - {msg}")
            elapsed = time.time() - self.start_time
            print(f"✅ Completed {description} ({elapsed:.1f}s)")
    
    def _update_simple_progress(self, message):
        """Update progress for operations without known steps"""
        print(f"  - {message}")
        if self.progress_file:
            progress_data = self._load_progress_state()
            progress_data.update({
                'message': message,
                'elapsed_time': time.time() - self.start_time
            })
            self._save_progress_state(progress_data)
    
    def _save_progress_state(self, data):
        """Save progress state to file"""
        if self.progress_file:
            try:
                dir_manager.save_json(self.progress_file, data)
            except Exception as e:
                print(f"Warning: Could not save progress state: {e}")
    
    def _load_progress_state(self):
        """Load progress state from file"""
        if self.progress_file and self.progress_file.exists():
            try:
                return dir_manager.load_json(self.progress_file)
            except:
                pass
        return {}


class BatchProgressTracker:
    """Specialized progress tracking for OpenAI batch jobs"""
    
    def __init__(self, workflow_name):
        self.workflow_name = workflow_name
        self.batch_progress_file = dir_manager.get_workflow_path(workflow_name) / "batch_progress.json"
        self.last_check_time = {}
        self.check_interval = 30  # seconds between checks
    
    def register_batch(self, batch_id, step_name, estimated_duration=3600):
        """Register a new batch job for tracking"""
        batch_data = {
            'batch_id': batch_id,
            'step_name': step_name,
            'status': 'uploaded',
            'created_time': time.time(),
            'estimated_duration': estimated_duration,
            'last_checked': time.time(),
            'check_count': 0,
            'progress_log': []
        }
        
        # Load existing batch progress
        all_batches = self._load_batch_progress()
        all_batches[batch_id] = batch_data
        self._save_batch_progress(all_batches)
        
        print(f"📋 Registered batch {batch_id} for step '{step_name}'")
        return batch_data
    
    def update_batch_status(self, batch_id, force_check=False):
        """Check and update batch status"""
        all_batches = self._load_batch_progress()
        
        if batch_id not in all_batches:
            return None
        
        batch_data = all_batches[batch_id]
        current_time = time.time()
        
        # Check if enough time has passed since last check
        if not force_check and current_time - batch_data.get('last_checked', 0) < self.check_interval:
            return batch_data
        
        try:
            # Check batch status with OpenAI API
            status, counts = check_batch_job(batch_id)
            
            # Update batch data
            batch_data.update({
                'status': status,
                'last_checked': current_time,
                'check_count': batch_data.get('check_count', 0) + 1,
                'counts': counts
            })
            
            # Add to progress log
            log_entry = {
                'timestamp': current_time,
                'status': status,
                'counts': counts
            }
            batch_data.setdefault('progress_log', []).append(log_entry)
            
            # Keep only last 20 log entries
            if len(batch_data['progress_log']) > 20:
                batch_data['progress_log'] = batch_data['progress_log'][-20:]
            
            # Save updated data
            all_batches[batch_id] = batch_data
            self._save_batch_progress(all_batches)
            
            print(f"🔄 Batch {batch_id}: {status} - {counts}")
            
            return batch_data
            
        except Exception as e:
            print(f"❌ Error checking batch {batch_id}: {e}")
            batch_data['last_error'] = str(e)
            all_batches[batch_id] = batch_data
            self._save_batch_progress(all_batches)
            return batch_data
    
    def get_batch_progress(self, batch_id):
        """Get current progress information for a batch"""
        all_batches = self._load_batch_progress()
        batch_data = all_batches.get(batch_id)
        
        if not batch_data:
            return None
        
        # Calculate progress percentage
        status = batch_data.get('status', 'unknown')
        counts = batch_data.get('counts', {})
        
        if status in ['completed', 'expired']:
            progress_pct = 100
        elif status == 'failed':
            progress_pct = 0
        elif status in ['uploaded', 'validating', 'in_progress', 'finalizing']:
            total = counts.get('total', 0)
            completed = counts.get('completed', 0)
            if total > 0:
                progress_pct = (completed / total) * 100
            else:
                # Estimate based on time elapsed
                elapsed = time.time() - batch_data.get('created_time', time.time())
                estimated = batch_data.get('estimated_duration', 3600)
                progress_pct = min((elapsed / estimated) * 100, 95)  # Cap at 95% until complete
        else:
            progress_pct = 0
        
        return {
            'batch_id': batch_id,
            'step_name': batch_data.get('step_name'),
            'status': status,
            'progress_pct': progress_pct,  # Add alias for UI compatibility
            'progress_percentage': progress_pct,  # Keep original for backward compatibility
            'counts': counts,
            'elapsed_time': time.time() - batch_data.get('created_time', time.time()),
            'estimated_remaining': max(0, batch_data.get('estimated_duration', 3600) - (time.time() - batch_data.get('created_time', time.time()))),
            'last_checked': batch_data.get('last_checked'),
            'check_count': batch_data.get('check_count', 0)
        }
    
    def get_all_active_batches(self):
        """Get all currently active batch jobs"""
        all_batches = self._load_batch_progress()
        active_batches = []
        
        for batch_id, batch_data in all_batches.items():
            status = batch_data.get('status', 'unknown')
            if status in ['uploaded', 'validating', 'in_progress', 'finalizing']:
                progress = self.get_batch_progress(batch_id)
                if progress:
                    active_batches.append(progress)
        
        return active_batches
    
    def cleanup_old_batches(self, max_age_days=7):
        """Remove old batch tracking data"""
        all_batches = self._load_batch_progress()
        current_time = time.time()
        cutoff_time = current_time - (max_age_days * 24 * 3600)
        
        cleaned_batches = {}
        removed_count = 0
        
        for batch_id, batch_data in all_batches.items():
            created_time = batch_data.get('created_time', current_time)
            status = batch_data.get('status', 'unknown')
            
            # Keep recent batches or active ones
            if created_time > cutoff_time or status in ['uploaded', 'validating', 'in_progress', 'finalizing']:
                cleaned_batches[batch_id] = batch_data
            else:
                removed_count += 1
        
        if removed_count > 0:
            self._save_batch_progress(cleaned_batches)
            print(f"🧹 Cleaned up {removed_count} old batch records")
        
        return removed_count
    
    def _load_batch_progress(self):
        """Load batch progress data from file"""
        if self.batch_progress_file.exists():
            try:
                return dir_manager.load_json(self.batch_progress_file)
            except:
                pass
        return {}
    
    def _save_batch_progress(self, data):
        """Save batch progress data to file"""
        try:
            dir_manager.save_json(self.batch_progress_file, data)
        except Exception as e:
            print(f"Warning: Could not save batch progress: {e}")


def execute_with_progress(operation, description, total_steps=None, workflow_name=None):
    """Execute operation with progress tracking"""
    tracker = ProgressTracker()
    
    with tracker.track_operation(description, total_steps, workflow_name) as update_progress:
        try:
            if total_steps:
                return operation(update_progress)
            else:
                return operation()
        except Exception as e:
            print(f"❌ Failed {description}: {e}")
            raise


# Progress tracking decorators
def track_progress(description, workflow_name=None):
    """Decorator to add progress tracking to functions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            return execute_with_progress(
                lambda: func(*args, **kwargs),
                description,
                workflow_name=workflow_name
            )
        return wrapper
    return decorator


def track_batch_progress(workflow_name):
    """Decorator for batch operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            batch_tracker = BatchProgressTracker(workflow_name)
            return func(batch_tracker, *args, **kwargs)
        return wrapper
    return decorator


# Utility functions for Streamlit integration
def render_batch_progress_ui(workflow_name):
    """Render batch progress in Streamlit UI"""
    try:
        import streamlit as st
        
        batch_tracker = BatchProgressTracker(workflow_name)
        active_batches = batch_tracker.get_all_active_batches()
        
        if active_batches:
            st.subheader("🔄 Active Batch Jobs")
            
            for batch_progress in active_batches:
                with st.expander(f"Step: {batch_progress['step_name']}", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Status", batch_progress['status'])
                    with col2:
                        st.metric("Progress", f"{batch_progress['progress_percentage']:.1f}%")
                    with col3:
                        if batch_progress['estimated_remaining'] > 0:
                            remaining_mins = batch_progress['estimated_remaining'] / 60
                            st.metric("Est. Remaining", f"{remaining_mins:.0f}m")
                        else:
                            st.metric("Elapsed", f"{batch_progress['elapsed_time']/60:.0f}m")
                    
                    # Progress bar
                    st.progress(batch_progress['progress_percentage'] / 100)
                    
                    # Counts information
                    counts = batch_progress.get('counts', {})
                    if counts:
                        st.caption(f"Completed: {counts.get('completed', 0)}/{counts.get('total', 0)} | Failed: {counts.get('failed', 0)}")
                    
                    # Last checked
                    if batch_progress['last_checked']:
                        last_check = datetime.fromtimestamp(batch_progress['last_checked'])
                        st.caption(f"Last checked: {last_check.strftime('%H:%M:%S')}")
        else:
            st.info("No active batch jobs")
            
    except ImportError:
        print("Streamlit not available for UI rendering")


def auto_update_batch_progress(workflow_name, max_age_minutes=5):
    """Automatically update batch progress for active jobs"""
    batch_tracker = BatchProgressTracker(workflow_name)
    
    # Clean up old batches first
    batch_tracker.cleanup_old_batches()
    
    # Update active batches
    active_batches = batch_tracker.get_all_active_batches()
    updated_count = 0
    
    for batch_progress in active_batches:
        batch_id = batch_progress['batch_id']
        
        # Check if it's time to update
        last_checked = batch_progress.get('last_checked', 0)
        if time.time() - last_checked > (max_age_minutes * 60):
            batch_tracker.update_batch_status(batch_id, force_check=True)
            updated_count += 1
    
    if updated_count > 0:
        print(f"🔄 Auto-updated {updated_count} batch jobs")
    
    return updated_count