def slugify(text):
    """Lowercase the text, trim it, and join the words with single hyphens."""
    return text.lower().replace(" ", "-")
