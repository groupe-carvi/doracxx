"""
doracxx - A cross-platform C++ build system for Dora dataflow nodes

This package provides tools to build C++ nodes for the Dora dataflow framework
with automatic dependency resolution and modern project structure.
"""

__version__ = "0.1.0"
__author__ = "Groupe Carvi"
__email__ = "contact@carvi.com"

from .cli import main, build_node, prepare_dora
from .config import load_config, create_example_config, DoracxxConfig
from .dependencies import setup_dependencies, DependencyManager

__all__ = [
    "main", 
    "build_node", 
    "prepare_dora", 
    "load_config", 
    "create_example_config", 
    "DoracxxConfig",
    "setup_dependencies",
    "DependencyManager"
]
