"""
EZID plugin template tag to normalize ORCID identifiers
"""
import re
from django import template

register = template.Library()

@register.filter
def normalize_orcid(value):
    """Normalize an ORCID identifier to the standard format."""
    pattern = r"(\d{4}-\d{4}-\d{4}-[\dX]{4})"
    match = re.search(pattern, value)
    return f"https://orcid.org/{match.group(0)}" if match else ""
