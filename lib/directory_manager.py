import os
import json
from pathlib import Path
from datetime import datetime

def normalize_path(path_input):
    """Ensure all paths are Path objects"""
    if isinstance(path_input, str):
        return Path(path_input).resolve()
    elif isinstance(path_input, Path):
        return path_input.resolve()
    else:
        raise ValueError(f"Invalid path type: {type(path_input)}")

def validate_path_security(path_input):
    """Validate that paths are within allowed directories"""
    path = normalize_path(path_input)
    allowed_dirs = [
        Path.cwd() / 'runs', 
        Path.cwd() / 'seed_files',
        Path.cwd() / 'lib',
        Path.cwd() / 'templates'
    ]
    
    # Check if path is within any allowed directory
    for allowed_dir in allowed_dirs:
        try:
            path.relative_to(allowed_dir)
            return path  # Path is safe
        except ValueError:
            continue
    
    raise ValueError(f"Path not in allowed directory: {path}")
    
def safe_path_join(*path_parts):
    """Safely join path parts and normalize"""
    if not path_parts:
        return Path.cwd()
    
    result = Path(path_parts[0])
    for part in path_parts[1:]:
        result = result / part
    
    return normalize_path(result)

class DirectoryManager:
    """Centralized directory management for the entire application"""
    
    def __init__(self):
        self.base_dir = Path.cwd()
        self.ensure_base_directories()
    
    def ensure_base_directories(self):
        """Ensure all required base directories exist"""
        required_dirs = [
            "runs",
            "seed_files", 
            "lib",
            "lib/tools",
            "pages"
        ]
        
        for dir_path in required_dirs:
            full_path = self.base_dir / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Ensured directory exists: {full_path}")
    
    def ensure_workflow_directory(self, workflow_name):
        """Ensure a specific workflow directory exists with proper structure"""
        workflow_dir = self.base_dir / "runs" / workflow_name
        workflow_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure CORRECT subdirectories exist for your workflow
        subdirs = [
            "batch",     # for batch.jsonl files
            "data",      # for extracted data JSON files  
            "datasets"   # for finalized Huggingface datasets
        ]
        
        for subdir in subdirs:
            (workflow_dir / subdir).mkdir(exist_ok=True)
            print(f"✅ Created workflow subdir: {workflow_dir / subdir}")
        
        return workflow_dir
    
    def get_workflow_path(self, workflow_name):
        """Get the full path to a workflow directory"""
        return self.base_dir / "runs" / workflow_name
    
    def get_state_file_path(self, workflow_name):
        """Get the full path to a workflow's state file"""
        return self.get_workflow_path(workflow_name) / "state.json"
    
    def get_batch_dir(self, workflow_name):
        """Get the batch directory for a workflow"""
        batch_dir = self.get_workflow_path(workflow_name) / "batch"
        batch_dir.mkdir(exist_ok=True)
        return batch_dir
    
    def get_data_dir(self, workflow_name):
        """Get the data directory for a workflow"""
        data_dir = self.get_workflow_path(workflow_name) / "data"
        data_dir.mkdir(exist_ok=True)
        return data_dir
    
    def get_datasets_dir(self, workflow_name):
        """Get the datasets directory for a workflow"""
        datasets_dir = self.get_workflow_path(workflow_name) / "datasets"
        datasets_dir.mkdir(exist_ok=True)
        return datasets_dir
    
    def create_dataset_version_dir(self, workflow_name, version_name=None):
        """Create a new dataset version directory"""
        datasets_dir = self.get_datasets_dir(workflow_name)
        
        if version_name is None:
            # Auto-generate version name based on timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            version_name = f"version_{timestamp}"
        
        version_dir = datasets_dir / version_name
        version_dir.mkdir(exist_ok=True)
        
        print(f"✅ Created dataset version: {version_dir}")
        return version_dir
    
    def list_dataset_versions(self, workflow_name):
        """List all dataset versions for a workflow"""
        datasets_dir = self.get_datasets_dir(workflow_name)
        
        if not datasets_dir.exists():
            return []
        
        versions = []
        for item in datasets_dir.iterdir():
            if item.is_dir():
                versions.append({
                    'name': item.name,
                    'path': str(item),
                    'created': datetime.fromtimestamp(item.stat().st_ctime).isoformat()
                })
        
        # Sort by creation time (newest first)
        versions.sort(key=lambda x: x['created'], reverse=True)
        return versions
    
    def get_batch_file_path(self, workflow_name, step_name):
        """Get the path for a batch JSONL file"""
        batch_dir = self.get_batch_dir(workflow_name)
        return batch_dir / f"{step_name}_batch.jsonl"
    
    def get_data_file_path(self, workflow_name, step_name, data_type="extracted"):
        """Get the path for a data JSON file"""
        data_dir = self.get_data_dir(workflow_name)
        return data_dir / f"{step_name}_{data_type}.json"
    
    def save_batch_jsonl(self, workflow_name, step_name, batch_data):
        """Save batch data as JSONL file"""
        batch_file_path = self.get_batch_file_path(workflow_name, step_name)
        
        with open(batch_file_path, 'w') as f:
            for item in batch_data:
                f.write(json.dumps(item) + '\\n')
        
        print(f"✅ Saved batch file: {batch_file_path}")
        return str(batch_file_path)
    
    def load_batch_jsonl(self, workflow_name, step_name):
        """Load batch data from JSONL file"""
        batch_file_path = self.get_batch_file_path(workflow_name, step_name)
        
        if not batch_file_path.exists():
            raise FileNotFoundError(f"Batch file not found: {batch_file_path}")
        
        batch_data = []
        with open(batch_file_path, 'r') as f:
            for line in f:
                batch_data.append(json.loads(line.strip()))
        
        return batch_data
    
    def save_extracted_data(self, workflow_name, step_name, extracted_data):
        """Save extracted data as JSON file"""
        data_file_path = self.get_data_file_path(workflow_name, step_name, "extracted")
        self.save_json(data_file_path, extracted_data)
        
        print(f"✅ Saved extracted data: {data_file_path}")
        return str(data_file_path)
    
    def load_extracted_data(self, workflow_name, step_name):
        """Load extracted data from JSON file"""
        data_file_path = self.get_data_file_path(workflow_name, step_name, "extracted")
        return self.load_json(data_file_path)
    
    def save_huggingface_dataset(self, workflow_name, dataset, version_name=None, dataset_name="dataset"):
        """Save Huggingface dataset to a version directory"""
        version_dir = self.create_dataset_version_dir(workflow_name, version_name)
        
        # Save the dataset
        dataset_path = version_dir / dataset_name
        dataset.save_to_disk(str(dataset_path))
        
        # Save metadata
        metadata = {
            "created": datetime.now().isoformat(),
            "version_name": version_dir.name,
            "dataset_name": dataset_name,
            "num_rows": len(dataset),
            "features": list(dataset.features.keys()) if hasattr(dataset, 'features') else [],
            "workflow_name": workflow_name
        }
        
        metadata_path = version_dir / "metadata.json"
        self.save_json(metadata_path, metadata)
        
        print(f"✅ Saved Huggingface dataset: {dataset_path}")
        print(f"✅ Saved metadata: {metadata_path}")
        
        return {
            'dataset_path': str(dataset_path),
            'metadata_path': str(metadata_path),
            'version_dir': str(version_dir),
            'version_name': version_dir.name
        }
    
    def load_huggingface_dataset(self, workflow_name, version_name, dataset_name="dataset"):
        """Load Huggingface dataset from a version directory"""
        from datasets import load_from_disk
        
        datasets_dir = self.get_datasets_dir(workflow_name)
        version_dir = datasets_dir / version_name
        dataset_path = version_dir / dataset_name
        
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {dataset_path}")
        
        dataset = load_from_disk(str(dataset_path))
        
        # Load metadata if available
        metadata_path = version_dir / "metadata.json"
        metadata = None
        if metadata_path.exists():
            metadata = self.load_json(metadata_path)
        
        return dataset, metadata
    
    def get_seed_files_dir(self):
        """Get the seed files directory"""
        seed_dir = self.base_dir / "seed_files"
        seed_dir.mkdir(exist_ok=True)
        return seed_dir
    
    def get_chats_dir(self):
        """Get or create chats directory"""
        chats_dir = self.base_dir / "chats"
        chats_dir.mkdir(exist_ok=True)
        return chats_dir
    
    def list_workflows(self):
        """List all available workflows"""
        runs_dir = self.base_dir / "runs"
        if not runs_dir.exists():
            return []
        
        workflows = []
        for item in runs_dir.iterdir():
            if item.is_dir() and (item / "state.json").exists():
                workflows.append(item.name)
        
        return workflows
    
    def list_seed_files(self):
        """List all available seed files"""
        seed_dir = self.get_seed_files_dir()
        seed_files = []
        
        for file_path in seed_dir.glob("*.json"):
            try:
                with open(file_path, 'r') as f:
                    seed_data = json.load(f)
                
                # Validate seed file structure
                if isinstance(seed_data, dict):
                    # Handle both direct seeds and progress files
                    actual_seed = seed_data.get('seed_file', seed_data)
                    
                    if ('variables' in actual_seed and 
                        'constants' in actual_seed and 
                        'call' in actual_seed):
                        seed_files.append({
                            'filename': file_path.name,
                            'path': str(file_path),
                            'display_name': file_path.stem.replace('_', ' ').title()
                        })
            
            except (json.JSONDecodeError, KeyError):
                continue
        
        return seed_files
    
    def save_json(self, file_path, data):
        """Safely save JSON data to a file with atomic operations"""
        file_path = normalize_path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use atomic write with temporary file
        temp_path = file_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            temp_path.replace(file_path)
            print(f"✅ Atomically saved JSON: {file_path}")
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise e
    
    def atomic_save_json(self, file_path, data):
        """Atomically save JSON data to prevent corruption"""
        return self.save_json(file_path, data)
    
    def load_json(self, file_path):
        """Safely load JSON data from a file with security validation"""
        file_path = normalize_path(file_path)
        
        # Validate path security
        try:
            validate_path_security(file_path)
        except ValueError as e:
            print(f"⚠️  Security validation failed: {e}")
            raise
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Check file size to prevent memory exhaustion
        file_size = file_path.stat().st_size
        max_file_size = 50 * 1024 * 1024  # 50MB limit
        
        if file_size > max_file_size:
            raise ValueError(f"File too large: {file_size} bytes (max: {max_file_size})")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in file {file_path}: {e}")
    
    def sanitize_filename(self, filename):
        """Sanitize filename to prevent directory traversal attacks"""
        import re
        
        # Remove any path separators and special characters
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
        
        # Remove leading dots and spaces
        sanitized = sanitized.lstrip('. ')
        
        # Limit length
        if len(sanitized) > 255:
            sanitized = sanitized[:255]
        
        # Ensure it's not empty
        if not sanitized:
            sanitized = "unnamed_file"
        
        return sanitized
    
    def get_workflow_summary(self, workflow_name):
        """Get a comprehensive summary of a workflow's files and datasets"""
        workflow_path = self.get_workflow_path(workflow_name)
        
        if not workflow_path.exists():
            return None
        
        summary = {
            'workflow_name': workflow_name,
            'workflow_path': str(workflow_path),
            'batch_files': [],
            'data_files': [],
            'dataset_versions': [],
            'total_size': 0
        }
        
        # List batch files
        batch_dir = workflow_path / "batch"
        if batch_dir.exists():
            for batch_file in batch_dir.glob("*.jsonl"):
                summary['batch_files'].append({
                    'name': batch_file.name,
                    'path': str(batch_file),
                    'size': batch_file.stat().st_size
                })
        
        # List data files
        data_dir = workflow_path / "data"
        if data_dir.exists():
            for data_file in data_dir.glob("*.json"):
                summary['data_files'].append({
                    'name': data_file.name,
                    'path': str(data_file),
                    'size': data_file.stat().st_size
                })
        
        # List dataset versions
        summary['dataset_versions'] = self.list_dataset_versions(workflow_name)
        
        # Calculate total size
        for item in summary['batch_files'] + summary['data_files']:
            summary['total_size'] += item['size']
        
        return summary

    def resolve_path(self, file_path):
        """Resolve path to absolute, trying multiple strategies"""
        if not file_path:
            return None
            
        path = Path(file_path)
        
        # Strategy 1: If absolute path exists, use it
        if path.is_absolute() and path.exists():
            return path
        
        # Strategy 2: Resolve relative to base directory
        if not path.is_absolute():
            resolved = self.base_dir / path
            if resolved.exists():
                return resolved
        
        # Strategy 3: If absolute path doesn't exist, try making it relative
        if path.is_absolute():
            path_str = str(path)
            # Look for 'runs/' in the path and extract from there
            if '/runs/' in path_str:
                runs_index = path_str.find('/runs/')
                relative_part = path_str[runs_index + 1:]  # Remove leading slash
                resolved = self.base_dir / relative_part
                if resolved.exists():
                    return resolved
        
        # Strategy 4: Search for the filename in common locations
        filename = path.name
        search_paths = [
            self.base_dir / 'runs',
            self.base_dir,
        ]
        
        for search_dir in search_paths:
            if search_dir.exists():
                for found_file in search_dir.rglob(filename):
                    if found_file.is_file():
                        return found_file
        
        return None



# Create global instance
dir_manager = DirectoryManager()