import os
import importlib
from typing import Dict, Type

from .base import BasePreprocessor
from .PreprocessorFactory import PreprocessorFactory

# Dictionary to store all available preprocessors
preprocessors: Dict[str, Type[BasePreprocessor]] = {}

# Automatically load all preprocessor modules
for filename in os.listdir(os.path.dirname(__file__)):
    if filename.endswith('.py') and not filename.startswith('__'):
        module_name = filename[:-3]
        module = importlib.import_module(f'.{module_name}', package=__name__)
        
        # Look for classes that inherit from BasePreprocessor
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                issubclass(attr, BasePreprocessor) and 
                attr != BasePreprocessor):
                preprocessors[attr.name] = attr 

# Create a singleton instance of the factory
factory = PreprocessorFactory()

# Export the factory instance
__all__ = ['factory'] 