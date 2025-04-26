def slugify(name: str) -> str:
    """Convert a string to a URL-friendly slug."""
    return ''.join(c if c.isalnum() else '-' for c in name.lower()).strip('-') 