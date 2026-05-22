import os
import importlib.util
import streamlit as st
from typing import Dict, Any

@st.cache_resource
def load_plugins(plugin_dir: str) -> Dict[str, Any]:
    schemas = {}
    if not os.path.exists(plugin_dir):
        os.makedirs(plugin_dir, exist_ok=True)
        return schemas
        
    for filename in os.listdir(plugin_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            name = filename[:-3]
            filepath = os.path.join(plugin_dir, filename)
            spec = importlib.util.spec_from_file_location(name, filepath)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "SCHEMA"):
                    schema = module.SCHEMA
                    schemas[schema["type"]] = schema
    return schemas

def get_literature_schemas(): return load_plugins("plugins/literatures")
def get_event_schemas(): return load_plugins("plugins/events")
def get_sample_schemas(): return load_plugins("plugins/samples")
def get_measurement_schemas(): return load_plugins("plugins/measurements")
def get_visualization_schemas(): return load_plugins("plugins/visualizations")
