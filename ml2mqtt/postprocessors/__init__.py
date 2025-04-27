from .PostprocessorFactory import PostprocessorFactory

# Create a singleton instance of the factory
factory = PostprocessorFactory()

# Export the factory instance
__all__ = ['factory'] 