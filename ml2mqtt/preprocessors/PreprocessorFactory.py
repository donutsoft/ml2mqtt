import os
import importlib
import logging
from typing import Dict, Any, Type, List, Optional

from .base import BasePreprocessor

class PreprocessorFactory:
    """Factory for creating preprocessor instances."""
    
    def __init__(self):
        self._logger = logging.getLogger("ml2mqtt")
        self._preprocessor_types: Dict[str, Type[BasePreprocessor]] = {}
        self._load_preprocessors()
    
    def _load_preprocessors(self) -> None:
        """Dynamically load all preprocessor modules from the preprocessors directory."""
        preprocessors_dir = os.path.dirname(__file__)
        
        for filename in os.listdir(preprocessors_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                module_name = filename[:-3]
                try:
                    module = importlib.import_module(f'.{module_name}', package='preprocessors')

                    # Look for classes that inherit from BasePreprocessor
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, BasePreprocessor) and 
                            attr != BasePreprocessor):
                            self._preprocessor_types[attr.type] = attr
                except Exception as e:
                    self._logger.error(f"Failed to load preprocessor module {module_name}: {e}")
    
    def get_available_preprocessors(self) -> List[Dict[str, Any]]:

        """Get a list of all available preprocessors with their metadata."""
        preprocessors = []
        for processor in self._preprocessor_types.values():
            # Skip the base processor
            if processor.type == "base" or processor == BasePreprocessor:
                continue
                
            preprocessors.append({
                "type": processor.type,
                "name": processor.name,
                "description": processor.description,
            })
        return preprocessors
     
    def create(self, preprocessor_type: str, dbId: int, params: Dict[str, Any] = None) -> BasePreprocessor:
        """
        Create a preprocessor instance.
        
        Args:
            preprocessor_type: Type of preprocessor to create
            entity: Optional entity to process
            params: Configuration parameters for the preprocessor
            
        Returns:
            Instance of the specified preprocessor
            
        Raises:
            ValueError: If preprocessor type is unknown
        """
        if preprocessor_type not in self._preprocessor_types:
            raise ValueError(f"Unknown preprocessor type: {preprocessor_type}")
            
        preprocessor_class = self._preprocessor_types[preprocessor_type]
        return preprocessor_class(dbId, **(params or {})) 