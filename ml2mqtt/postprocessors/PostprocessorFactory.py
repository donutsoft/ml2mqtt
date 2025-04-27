import os
import importlib
import logging
from typing import Dict, Any, Type, List, Optional

from .base import BasePostprocessor

class PostprocessorFactory:
    """Factory for creating postprocessor instances."""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._postprocessor_types: Dict[str, Type[BasePostprocessor]] = {}
        self._load_postprocessors()
    
    def _load_postprocessors(self) -> None:
        """Dynamically load all postprocessor modules from the postprocessors directory."""
        postprocessors_dir = os.path.dirname(__file__)
        
        for filename in os.listdir(postprocessors_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                module_name = filename[:-3]
                try:
                    module = importlib.import_module(f'.{module_name}', package='postprocessors')
                    
                    # Look for classes that inherit from BasePostprocessor
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, BasePostprocessor) and 
                            attr != BasePostprocessor):
                            self._postprocessor_types[attr.type] = attr
                            self._logger.info(f"Loaded postprocessor: {attr.type}")
                except Exception as e:
                    self._logger.error(f"Failed to load postprocessor module {module_name}: {e}")
    
    def get_available_postprocessors(self) -> List[Dict[str, Any]]:
        """Get a list of all available postprocessors with their metadata."""
        postprocessors = []
        for processor in self._postprocessor_types.values():
            # Skip the base processor
            if processor.type == "base" or processor == BasePostprocessor:
                continue
                
            self._logger.info(f"Processor: {processor}")
            schema = processor.config_schema
            if schema and "required" in schema and isinstance(schema["required"], set):
                schema = schema.copy()
                schema["required"] = list(schema["required"])  # sets -> lists

            postprocessors.append({
                "type": processor.type,
                "description": processor.description,
                "config_schema": schema
            })
        return postprocessors
    
    def create(self, postprocessor_type: str, dbId: int, params: Dict[str, Any] = None) -> BasePostprocessor:
        """
        Create a postprocessor instance.
        
        Args:
            postprocessor_type: Type of postprocessor to create
            dbId: Database ID for this postprocessor
            params: Configuration parameters for the postprocessor
            
        Returns:
            Instance of the specified postprocessor
            
        Raises:
            ValueError: If postprocessor type is unknown
        """
        if postprocessor_type not in self._postprocessor_types:
            raise ValueError(f"Unknown postprocessor type: {postprocessor_type}")
            
        postprocessor_class = self._postprocessor_types[postprocessor_type]
        return postprocessor_class(dbId=dbId, **(params or {})) 