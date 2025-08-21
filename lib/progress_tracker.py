import time
from contextlib import contextmanager

class ProgressTracker:
    """Utility for tracking progress of long-running operations"""
    
    def __init__(self):
        self.current_operation = None
        self.start_time = None
        
    @contextmanager 
    def track_operation(self, description, total_steps=None):
        """Context manager for tracking operation progress"""
        self.current_operation = description
        self.start_time = time.time()
        
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
                
                yield update_progress
                
                # Complete
                progress_bar.progress(1.0)
                elapsed = time.time() - self.start_time
                status_text.text(f"Completed {description} ({elapsed:.1f}s)")
                
            else:
                # Simple spinner for unknown duration
                with st.spinner(f"Processing {description}..."):
                    yield lambda step, msg="": print(f"{description}: {msg}")
                    
        except ImportError:
            # Not in Streamlit context, use console output
            print(f"⏳ Starting {description}...")
            yield lambda step, msg="": print(f"  - {msg}")
            elapsed = time.time() - self.start_time
            print(f"✅ Completed {description} ({elapsed:.1f}s)")

def execute_with_progress(operation, description, total_steps=None):
    """Execute operation with progress tracking"""
    tracker = ProgressTracker()
    
    with tracker.track_operation(description, total_steps) as update_progress:
        try:
            if total_steps:
                return operation(update_progress)
            else:
                return operation()
        except Exception as e:
            print(f"❌ Failed {description}: {e}")
            raise

# Progress tracking decorators
def track_progress(description):
    """Decorator to add progress tracking to functions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            return execute_with_progress(
                lambda: func(*args, **kwargs),
                description
            )
        return wrapper
    return decorator

# Batch operation progress tracker
class BatchProgressTracker:
    """Specialized progress tracker for batch operations"""
    
    def __init__(self, batch_id, description="Batch Operation"):
        self.batch_id = batch_id
        self.description = description
        self.last_check = 0
        
    def check_and_update(self):
        """Check batch status and update progress"""
        try:
            from lib.tools.batch import check_batch_job
            import streamlit as st
            
            current_time = time.time()
            
            # Only check every 5 seconds to avoid rate limiting
            if current_time - self.last_check < 5:
                return None
                
            self.last_check = current_time
            status, counts = check_batch_job(self.batch_id)
            
            if status == "completed":
                st.success(f"✅ {self.description} completed!")
                return "completed"
            elif status == "failed":
                st.error(f"❌ {self.description} failed!")
                return "failed"
            else:
                total = counts.get('total', 0)
                completed = counts.get('completed', 0)
                failed = counts.get('failed', 0)
                
                progress = completed / total if total > 0 else 0
                st.progress(progress)
                st.text(f"{self.description}: {completed}/{total} completed, {failed} failed")
                return "in_progress"
                
        except Exception as e:
            print(f"Error checking batch progress: {e}")
            return None

# Global progress tracker instance
progress_tracker = ProgressTracker()
