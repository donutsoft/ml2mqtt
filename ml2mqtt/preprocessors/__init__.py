from .PreprocessorFactory import PreprocessorFactory

# Create a singleton instance of the factory
factory = PreprocessorFactory()

# Export the factory instance
__all__ = ['factory'] 