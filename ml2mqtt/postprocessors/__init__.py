import os
import importlib
from typing import Dict, Type

from .base import BasePostprocessor

# Dictionary to store all available postprocessors
postprocessors: Dict[str, Type[BasePostprocessor]] = {}

# Automatically load all postprocessor modules
for filename in os.listdir(os.path.dirname(__file__)):
    if filename.endswith('.py') and not filename.startswith('__'):
        module_name = filename[:-3]
        module = importlib.import_module(f'.{module_name}', package=__name__)
        
        # Look for classes that inherit from BasePostprocessor
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                issubclass(attr, BasePostprocessor) and 
                attr != BasePostprocessor):
                postprocessors[attr.name] = attr 