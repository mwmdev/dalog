"""
HTML processing for log content.
"""

import re
from typing import List, Tuple, Optional
from html.parser import HTMLParser
from rich.text import Text
from rich.style import Style

from ..config.models import HtmlConfig


class LogHTMLParser(HTMLParser):
    """Custom HTML parser for log content that extracts tags and content."""
    
    def __init__(self, enabled_tags: List[str], strip_unknown: bool = True):
        """Initialize the parser.
        
        Args:
            enabled_tags: List of HTML tags to process
            strip_unknown: Whether to strip unknown tags
        """
        super().__init__()
        self.enabled_tags = set(enabled_tags)
        self.strip_unknown = strip_unknown
        self.parts: List[Tuple[str, Optional[str]]] = []
        self.current_tag = None
        self.tag_stack = []
        
    def handle_starttag(self, tag: str, attrs: list) -> None:
        """Handle opening HTML tag."""
        if tag in self.enabled_tags:
            self.tag_stack.append(tag)
            self.current_tag = tag
        elif not self.strip_unknown:
            # Keep unknown tags as text
            self.parts.append((self.get_starttag_text(), None))
            
    def handle_endtag(self, tag: str) -> None:
        """Handle closing HTML tag."""
        if tag in self.enabled_tags and self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()
            self.current_tag = self.tag_stack[-1] if self.tag_stack else None
        elif not self.strip_unknown:
            # Keep unknown tags as text
            self.parts.append((f"</{tag}>", None))
            
    def handle_data(self, data: str) -> None:
        """Handle text data between tags."""
        if data:
            self.parts.append((data, self.current_tag))
            
    def error(self, message):
        """Ignore HTML parsing errors."""
        pass


class HTMLProcessor:
    """Process HTML in log lines."""
    
    def __init__(self, config: HtmlConfig):
        """Initialize the HTML processor.
        
        Args:
            config: HTML configuration
        """
        self.config = config
        self.tag_styles = {
            'b': Style(bold=True),
            'strong': Style(bold=True),
            'i': Style(italic=True),
            'em': Style(italic=True),
            'code': Style(color="bright_cyan", bgcolor="black"),
            'a': Style(color="blue", underline=True),
            'span': Style(),  # No default style for span
        }
        
    def process_html(self, text: str) -> List[Tuple[str, Optional[Style]]]:
        """Process HTML in text and return styled segments.
        
        Args:
            text: Text containing HTML
            
        Returns:
            List of (text, style) tuples
        """
        # Quick check if text contains HTML
        if '<' not in text or '>' not in text:
            return [(text, None)]
            
        parser = LogHTMLParser(
            enabled_tags=self.config.enabled_tags,
            strip_unknown=self.config.strip_unknown_tags
        )
        
        try:
            parser.feed(text)
        except Exception:
            # If parsing fails, return original text
            return [(text, None)]
            
        # Convert parsed parts to styled segments
        segments = []
        for content, tag in parser.parts:
            if tag and tag in self.tag_styles:
                segments.append((content, self.tag_styles[tag]))
            else:
                segments.append((content, None))
                
        return segments
        
    def apply_html_styling(self, text: Text) -> Text:
        """Apply HTML styling to a Rich Text object.
        
        Args:
            text: Rich Text object to process
            
        Returns:
            New Text object with HTML styling applied
        """
        # Get the plain text
        plain_text = text.plain
        
        # Process HTML
        segments = self.process_html(plain_text)
        
        # Create new Text object with HTML styling
        styled_text = Text()
        for content, style in segments:
            if style:
                styled_text.append(content, style=style)
            else:
                styled_text.append(content)
                
        # Preserve any existing styles from the original text
        # by merging them with HTML styles
        for start, end, style in text._spans:
            styled_text.stylize(style, start, end)
            
        return styled_text 