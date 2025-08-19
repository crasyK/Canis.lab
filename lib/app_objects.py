from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
import json

def create_styled_steps_from_state(state_data):
    """Create step instances from state file data with proper styling and real names"""


    steps = state_data["state_steps"]
    nodes = state_data["nodes"]
    step_instances = []
    
    for i, step_data in enumerate(steps, 1):
        inputs = step_data['data']['in'] if 'data' in step_data and 'in' in step_data['data'] else {}
        outputs = step_data['data']['out'] if 'data' in step_data and 'out' in step_data['data'] else {}
        
        markers_map = {'in': len(inputs), 'out': len(outputs)}
        
        # Create step with metadata for styling and real names
        step_instance = step(
            markers_map=markers_map,
            step_type=step_data.get('type', 'code'),
            status=step_data.get('status', 'completed'),
            step_data={'in': inputs, 'out': outputs},
            step_name=step_data.get('name', f'Step {i}'),
            nodes_info=nodes
        )
        step_instances.append(step_instance)
    
    return step_instances

def create_complete_flow_from_state(state_data):
    """Create step instances and edges from state file data"""
    # Reset class state to avoid accumulation
    step.reset_class_state()
    
    # Create all step instances
    step_instances = create_styled_steps_from_state(state_data)
    
    # Then create edges between them
    complete_flow = step.return_complete_flow()
    
    return complete_flow


class step(object):
    num_of_steps = 0
    steps_arr = []
    instances = {}
    edges_arr = []

    def __init__(self, markers_map, step_type="code", status="completed", step_data=None, step_name="Step", nodes_info=None):
        self.markers_map = markers_map
        step.num_of_steps += 1
        self.step_number = step.num_of_steps
        step.instances[self.step_number] = self
        self.markers_count_column = max(self.markers_map.values()) if self.markers_map.values() else 1
        
        # Store step metadata for styling
        self.step_type = step_type # "llm" or "code"
        self.status = status # "running" or "completed"
        self.step_data = step_data or {} # Contains input/output data info
        self.step_name = step_name
        self.nodes_info = nodes_info or {} # Contains actual node information from state file
        
        self.arr = []
        self.return_step((0, 0))
        step.steps_arr.append(self.arr)

    def get_parent_style(self):
        """Get styling for parent node based on type and status"""
        # Border color based on type (changed from text color)
        border_color = '#0066cc' if self.step_type == 'llm' else '#ff8c00' # blue for llm, orange for code
        
        # Background color based on status
        backgroundColor = '#808080' if self.status == 'uploaded' else 'white' # grey for running, white for completed
        
        return {
            'color': 'black',  # Text color is always black now
            'backgroundColor': backgroundColor,
            'border': f'2px solid {border_color}',
            'width': '200px',
            'height': f'{self.markers_count_column*50+self.markers_count_column*10+40+10}px'
        }

    def is_single_data(self, file_path):
        """Check if the data is single (not a file path)"""
        if not isinstance(file_path, str):
            return False
        # Single data doesn't start with 'runs/' and doesn't end with file extensions
        return not (file_path.startswith('runs/') or file_path.endswith(('.json', '.jsonl', '.txt', '.csv')))

    def get_child_style(self, marker_name, file_path):
        """Get styling for child nodes based on data type from nodes_info"""
        style = {
            'color': 'black',
            'width': '100px',
            'height': '50px'
        }
        
        # Check if it's single data first
        if self.is_single_data(file_path):
            # For single data, use white border and determine background by content type
            style['border'] = '2px solid white'
            
            # Try to determine type from content for single data
            if isinstance(file_path, str):
                file_path_lower = file_path.lower()
                if any(json_indicator in file_path_lower for json_indicator in ['{', '}', '"role"', '"content"']):
                    style['backgroundColor'] = 'yellow'  # JSON-like content
                elif file_path_lower in ['true', 'false'] or file_path.isdigit():
                    style['backgroundColor'] = 'green'  # String/boolean/number
                else:
                    style['backgroundColor'] = 'green'  # Default to string for single data
            else:
                style['backgroundColor'] = 'green'  # Default for single data
            
            return style
        
        # Find the node info for this marker (for file-based data)
        node_info = self.find_node_by_file_path(file_path)
        
        if not node_info:
            # Only grey out if it's not single data and node not found
            style['backgroundColor'] = 'lightgray'
            style['border'] = '2px solid black'
            return style
        
        # Check if it's huggingface_dataset
        if node_info.get('type') == 'huggingface_dataset':
            style['backgroundColor'] = 'white'
            style['border'] = '2px solid red'
            return style
        
        # Get type information
        type_info = node_info.get('type', {})
        
        # Set background color based on data type
        if isinstance(type_info, dict):
            if 'json' in type_info:
                style['backgroundColor'] = 'yellow'
            elif 'str' in type_info:
                style['backgroundColor'] = 'green'
            elif 'list' in type_info:
                style['backgroundColor'] = 'purple'
            else:
                style['backgroundColor'] = 'lightgray'
        else:
            style['backgroundColor'] = 'lightgray'
        
        # Set border color (black for file-based data)
        style['border'] = '2px solid black'
        
        return style

    def find_node_by_file_path(self, file_path):
        """Find node information by file path"""
        for node in self.nodes_info:
            if node.get('file_name') == file_path:
                return node
        return None

    def get_marker_display_name(self, marker_key, file_path):
        """Get the actual marker name from the node info"""
        # For single data, use the marker key as display name
        if self.is_single_data(file_path):
            return marker_key
        
        node_info = self.find_node_by_file_path(file_path)
        if node_info:
            return node_info.get('name', marker_key)
        return marker_key

    def return_step(self, position=(0, 0)):
        self.arr = []
        
        # Create parent node with dynamic styling and real name
        parent_style = self.get_parent_style()
        self.arr.append(StreamlitFlowNode(
            f'{self.step_number}-parent-{0}',
            position,
            {'content': f"{self.step_name}", 'prev_pos': position},
            'input',
            'right',
            draggable=True,
            connectable=False,
            style=parent_style
        ))

        # Create child nodes with real names and dynamic styling
        input_counter = 0
        output_counter = 0
        
        for marker_type in self.markers_map.keys():
            if marker_type == 'in':
                # Get input markers from step_data
                input_data = self.step_data.get('in', {})
                for marker_key, file_path in input_data.items():
                    input_counter += 1
                    display_name = self.get_marker_display_name(marker_key, file_path)
                    child_style = self.get_child_style(marker_key, file_path)
                    
                    self.arr.append(StreamlitFlowNode(
                        f'{self.step_number}-in-{input_counter}',
                        (position[0] - 10, position[1] + 40 + 10 + (input_counter-1) * (50 + 10)),
                        {'content': display_name},
                        'output',
                        target_position='left',
                        draggable=False,
                        style=child_style
                    ))
            
            elif marker_type == 'out':
                # Get output markers from step_data
                output_data = self.step_data.get('out', {})
                for marker_key, file_path in output_data.items():
                    output_counter += 1
                    display_name = self.get_marker_display_name(marker_key, file_path)
                    child_style = self.get_child_style(marker_key, file_path)
                    
                    self.arr.append(StreamlitFlowNode(
                        f'{self.step_number}-out-{output_counter}',
                        (position[0] + 110, position[1] + 40 + 10 + (output_counter-1) * (50 + 10)),
                        {'content': display_name},
                        'input',
                        'right',
                        draggable=False,
                        style=child_style
                    ))
        
        return self.arr

    @classmethod
    def create_edges_between_steps(cls):
        """Create edges connecting output nodes to input nodes based on file paths"""
        edges = []
        
        # Create a snapshot of instances to avoid dictionary modification during iteration
        all_instances = list(cls.instances.values())
        
        for step_instance in all_instances:
            # Get output data for this step
            output_data = step_instance.step_data.get('out', {})
            
            for out_marker_key, out_file_path in output_data.items():
                # Find which input nodes in other steps use this output
                target_steps = cls.find_steps_using_file_as_input(out_file_path)
                
                for target_step, in_marker_key in target_steps:
                    # Create edge from output to input
                    source_node_id = cls.find_output_node_id(step_instance, out_marker_key)
                    target_node_id = cls.find_input_node_id(target_step, in_marker_key)
                    
                    if source_node_id and target_node_id:
                        edge = StreamlitFlowEdge(
                            f"edge-{source_node_id}-to-{target_node_id}",
                            source_node_id,
                            target_node_id,
                            style={'stroke': '#333', 'strokeWidth': 2}
                        )
                        edges.append(edge)
        
        cls.edges_arr = edges
        return edges

    @classmethod
    def find_steps_using_file_as_input(cls, file_path):
        """Find all steps that use the given file path as input"""
        using_steps = []
        
        # Create a snapshot of instances to avoid dictionary modification during iteration
        all_instances = list(cls.instances.values())
        
        for step_instance in all_instances:
            input_data = step_instance.step_data.get('in', {})
            for in_marker_key, in_file_path in input_data.items():
                if in_file_path == file_path:
                    using_steps.append((step_instance, in_marker_key))
        
        return using_steps


    @classmethod
    def find_output_node_id(cls, step_instance, marker_key):
        """Find the node ID for a specific output marker in a step"""
        output_data = step_instance.step_data.get('out', {})
        output_counter = 0
        
        for out_key, _ in output_data.items():
            output_counter += 1
            if out_key == marker_key:
                return f'{step_instance.step_number}-out-{output_counter}'
        
        return None

    @classmethod
    def find_input_node_id(cls, step_instance, marker_key):
        """Find the node ID for a specific input marker in a step"""
        input_data = step_instance.step_data.get('in', {})
        input_counter = 0
        
        for in_key, _ in input_data.items():
            input_counter += 1
            if in_key == marker_key:
                return f'{step_instance.step_number}-in-{input_counter}'
        
        return None

    @classmethod
    def return_all_steps_combined(cls):
        """Returns all self.arr arrays from every instance combined into one big array"""
        combined_arr = []
        for step_arr in cls.steps_arr:
            combined_arr.extend(step_arr)
        return combined_arr

    @classmethod
    def return_all_edges(cls):
        """Returns all edges connecting the steps"""
        return cls.edges_arr

    @classmethod
    def return_complete_flow(cls):
        """Returns both nodes and edges for the complete flow"""
        nodes = cls.return_all_steps_combined()
        edges = cls.create_edges_between_steps()
        return {'nodes': nodes, 'edges': edges}

    @classmethod
    def return_steps(cls):
        """Returns the list of all step arrays (each as separate arrays)"""
        return cls.steps_arr

    @classmethod
    def get_instance_by_number(cls, step_number):
        return cls.instances.get(step_number)
    
    @classmethod
    def reset_class_state(cls):
        """Reset class variables - useful when creating a new flow"""
        cls.num_of_steps = 0
        cls.steps_arr = []
        cls.instances = {}
        cls.edges_arr = []

