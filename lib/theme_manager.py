import streamlit as st
from typing import Dict, Any

class ThemeManager:
    """Dark mode theme management for the Canis.lab application"""
    
    def __init__(self):
        self.colors = self._get_dark_theme()
    
    def _get_dark_theme(self) -> Dict[str, Any]:
        return {
            'name': 'dark',
            'background': '#0E1117',
            'secondary_background': '#262730',
            'text_primary': '#FAFAFA',
            'text_secondary': '#A3A8B8',
            'border': '#3D4551',
            'accent_primary': '#FF6B6B',
            'accent_secondary': '#4FC3F7',
            'success': '#00E1A8',
            'warning': '#FFB347',
            'error': '#FF6B6B',
            'info': '#4FC3F7',
            
            # Workflow node colors
            'node_background': '#262730',
            'node_border': '#4FC3F7',
            'node_text': '#FAFAFA',
            'llm_node': '#4FC3F7',
            'code_node': '#FFB347',
            'chip_node': '#BA68C8',
            
            # Data type colors
            'json_data': '#FFD54F',
            'string_data': '#4DB6AC',
            'list_data': '#BA68C8',
            'integer_data': '#81C784',
            'file_data': '#FAFAFA',
            'single_data': '#424242',
            'huggingface_data': '#424242',
            
            # Status colors
            'completed_bg': '#1B4332',
            'failed_bg': '#4A1E1E',
            'running_bg': '#3D3B1F',
            'idle_bg': '#262730',
            
            # Test step colors
            'test_completed': '#3D3B1F',
            'test_failed': '#4A1E1E',
            'test_pending': '#3D3B1F',
            
            # Connection colors
            'connection_color': '#4DB6AC',
            'edge_color': '#A3A8B8'
        }
    
    def get_theme_colors(self) -> Dict[str, Any]:
        """Get dark theme colors"""
        return self.colors
    
    def apply_theme_css(self):
        """Apply dark theme CSS"""
        colors = self.get_theme_colors()
        
        css = f"""
        <style>
        /* Global dark theme variables */
        :root {{
            --bg-color: {colors['background']};
            --secondary-bg: {colors['secondary_background']};
            --text-primary: {colors['text_primary']};
            --text-secondary: {colors['text_secondary']};
            --border-color: {colors['border']};
            --accent-primary: {colors['accent_primary']};
            --accent-secondary: {colors['accent_secondary']};
        }}
        
        /* Main app background */
        .stApp {{
            background-color: {colors['background']};
            color: {colors['text_primary']};
        }}
        
        /* Sidebar styling */
        .css-1d391kg, .css-1cypcdb {{
            background-color: {colors['secondary_background']};
            border-right: 1px solid {colors['border']};
        }}
        
        /* Main content area */
        .main .block-container {{
            background-color: {colors['background']};
            color: {colors['text_primary']};
        }}
        
        /* Metric cards */
        .metric-card {{
            background-color: {colors['secondary_background']};
            border: 1px solid {colors['border']};
            border-radius: 8px;
            padding: 1rem;
            color: {colors['text_primary']};
        }}
        
        /* Button styling */
        .stButton > button {{
            background-color: {colors['accent_primary']};
            color: white;
            border: none;
            border-radius: 6px;
            transition: all 0.3s ease;
        }}
        
        .stButton > button:hover {{
            background-color: {colors['accent_secondary']};
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        
        /* Input fields */
        .stTextInput > div > div > input {{
            background-color: {colors['secondary_background']};
            color: {colors['text_primary']};
            border: 1px solid {colors['border']};
        }}
        
        .stSelectbox > div > div > div {{
            background-color: {colors['secondary_background']};
            color: {colors['text_primary']};
        }}
        
        /* Container styling */
        .stContainer {{
            background-color: {colors['secondary_background']};
            border: 1px solid {colors['border']};
            border-radius: 8px;
        }}
        
        /* Expander styling */
        .streamlit-expanderHeader {{
            background-color: {colors['secondary_background']};
            color: {colors['text_primary']};
        }}
        
        /* Success/Error/Warning messages */
        .stAlert > div {{
            background-color: {colors['secondary_background']};
            border-radius: 6px;
        }}
        
        .stSuccess {{
            background-color: {colors['success']}20;
            border-left: 4px solid {colors['success']};
        }}
        
        .stError {{
            background-color: {colors['error']}20;
            border-left: 4px solid {colors['error']};
        }}
        
        .stWarning {{
            background-color: {colors['warning']}20;
            border-left: 4px solid {colors['warning']};
        }}
        
        .stInfo {{
            background-color: {colors['info']}20;
            border-left: 4px solid {colors['info']};
        }}
        
        /* Divider styling */
        .stDivider > div {{
            border-color: {colors['border']};
        }}
        
        /* Code blocks */
        .stCode {{
            background-color: {colors['secondary_background']};
            border: 1px solid {colors['border']};
        }}
        
        /* JSON viewer */
        .stJson {{
            background-color: {colors['secondary_background']};
            color: {colors['text_primary']};
        }}
        
        /* Workflow flow styling */
        .react-flow {{
            background-color: {colors['background']};
        }}
        
        .react-flow__minimap {{
            background-color: {colors['secondary_background']};
            border: 1px solid {colors['border']};
        }}
        
        .react-flow__controls {{
            background-color: {colors['secondary_background']};
            border: 1px solid {colors['border']};
        }}
        
        /* Chat messages */
        .stChatMessage {{
            background-color: {colors['secondary_background']};
            border: 1px solid {colors['border']};
        }}
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {{
            background-color: {colors['secondary_background']};
        }}
        
        .stTabs [data-baseweb="tab"] {{
            color: {colors['text_secondary']};
        }}
        
        .stTabs [aria-selected="true"] {{
            color: {colors['accent_secondary']};
        }}
        
        /* Metrics */
        .metric-container {{
            background-color: {colors['secondary_background']};
            border: 1px solid {colors['border']};
            border-radius: 8px;
        }}
        
        /* Radio buttons */
        .stRadio > div {{
            background-color: {colors['secondary_background']};
        }}
        
        /* Checkboxes */
        .stCheckbox > label {{
            color: {colors['text_primary']};
        }}
        
        /* Text areas */
        .stTextArea > div > div > textarea {{
            background-color: {colors['secondary_background']};
            color: {colors['text_primary']};
            border: 1px solid {colors['border']};
        }}
        
        /* Number inputs */
        .stNumberInput > div > div > input {{
            background-color: {colors['secondary_background']};
            color: {colors['text_primary']};
            border: 1px solid {colors['border']};
        }}
        
        /* Columns */
        .stColumn {{
            background-color: transparent;
        }}
        
        /* Progress bars */
        .stProgress > div > div > div {{
            background-color: {colors['accent_secondary']};
        }}
        </style>
        """
        
        st.markdown(css, unsafe_allow_html=True)

# Global theme manager instance
theme_manager = ThemeManager()
