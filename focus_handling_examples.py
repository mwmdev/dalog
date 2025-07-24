"""
Examples of proper focus event handling in Textual.

This file demonstrates the correct approaches to handle focus events,
including the limitations of the @on decorator with CSS selectors.
"""

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.events import Focus, Blur, DescendantFocus
from textual.widgets import Button, Input, ListView, ListItem, Label
from textual import on


class FocusHandlingExamples:
    """Examples of different focus handling approaches."""
    
    # ============================================================================
    # APPROACH 1: Traditional event handlers (RECOMMENDED for Focus/Blur events)
    # ============================================================================
    
    def on_focus(self, event: Focus) -> None:
        """Handle focus events using traditional event handlers.
        
        This is the RECOMMENDED approach for Focus events because:
        1. Focus events don't have a 'control' attribute
        2. You can't use @on decorator with CSS selectors for Focus events
        3. Traditional handlers receive all focus events and you can filter by widget
        """
        # Check if the focused widget is our specific widget
        if event.widget.id == "pattern-list":
            pattern_list = self.query_one("#pattern-list", ListView)
            if pattern_list.children:
                # Focus the first ListItem
                first_item = pattern_list.children[0]
                if isinstance(first_item, ListItem):
                    first_item.focus()
    
    def on_blur(self, event: Blur) -> None:
        """Handle blur events using traditional event handlers."""
        if event.widget.id == "some-specific-widget":
            # Do something when this specific widget loses focus
            pass
    
    # ============================================================================
    # APPROACH 2: Using DescendantFocus (Alternative for parent widgets)
    # ============================================================================
    
    def on_descendant_focus(self, event: DescendantFocus) -> None:
        """Handle when a descendant widget gains focus.
        
        This is useful when you want to react to focus changes within
        a container widget without handling every individual focus event.
        """
        # This fires when any descendant of this widget gains focus
        focused_widget = event.widget
        if hasattr(focused_widget, 'id') and focused_widget.id == "pattern-list":
            # Handle ListView gaining focus
            pass
    
    # ============================================================================
    # APPROACH 3: What WORKS with @on decorator and CSS selectors
    # ============================================================================
    
    @on(Button.Pressed, "#my-button")
    def handle_specific_button(self) -> None:
        """This WORKS because Button.Pressed has a 'control' attribute."""
        pass
    
    @on(Input.Submitted, "#search-input")
    def handle_specific_input(self) -> None:
        """This WORKS because Input.Submitted has a 'control' attribute."""
        pass
    
    # ============================================================================
    # APPROACH 4: What DOESN'T WORK with @on decorator and CSS selectors
    # ============================================================================
    
    # @on(Focus, "#pattern-list")  # ❌ DOESN'T WORK
    # def broken_focus_handler(self) -> None:
    #     """This DOESN'T WORK because Focus events don't have a 'control' attribute."""
    #     pass
    
    # @on(Blur, "#pattern-list")  # ❌ DOESN'T WORK
    # def broken_blur_handler(self) -> None:
    #     """This DOESN'T WORK because Blur events don't have a 'control' attribute."""
    #     pass
    
    # ============================================================================
    # APPROACH 5: Custom widget with overridden focus behavior
    # ============================================================================


class CustomListView(ListView):
    """Custom ListView that automatically focuses first item when it gains focus."""
    
    def on_focus(self, event: Focus) -> None:
        """Override focus handling to automatically focus first item."""
        # Call parent's focus handler first
        super().on_focus(event)
        
        # Focus first item if available
        if self.children:
            first_item = self.children[0]
            if isinstance(first_item, ListItem):
                first_item.focus()


class FocusRedirectionDemo(App):
    """Demo app showing proper focus redirection techniques."""
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Input(placeholder="Press Tab to navigate", id="input1")
            yield CustomListView(
                ListItem(Label("Item 1")),
                ListItem(Label("Item 2")),
                ListItem(Label("Item 3")),
                id="custom-list"
            )
            yield Button("Test Button", id="test-button")
    
    def on_focus(self, event: Focus) -> None:
        """Handle focus events for regular ListView."""
        self.log(f"Widget {event.widget.id} gained focus")
        
        # Handle regular ListView focus redirection
        if event.widget.id == "some-regular-listview":
            list_view = self.query_one("#some-regular-listview", ListView)
            if list_view.children:
                first_item = list_view.children[0]
                if isinstance(first_item, ListItem):
                    first_item.focus()
    
    @on(Button.Pressed, "#test-button")
    def handle_button(self) -> None:
        """This works because Button.Pressed has 'control' attribute."""
        self.log("Button pressed!")


# ============================================================================
# SUMMARY OF BEST PRACTICES
# ============================================================================

"""
BEST PRACTICES FOR FOCUS HANDLING IN TEXTUAL:

1. USE TRADITIONAL HANDLERS for Focus/Blur events:
   - def on_focus(self, event: Focus) -> None:
   - def on_blur(self, event: Blur) -> None:
   - Filter by event.widget.id or other properties

2. USE @on DECORATOR WITH CSS SELECTORS for events with 'control' attribute:
   - @on(Button.Pressed, "#button-id")
   - @on(Input.Submitted, "#input-id")
   - @on(ListView.Selected, "#list-id")

3. USE CUSTOM WIDGETS when you need consistent behavior:
   - Inherit from base widget class
   - Override on_focus/on_blur methods
   - Implement desired focus redirection logic

4. USE DESCENDANT FOCUS EVENTS for container-level focus management:
   - def on_descendant_focus(self, event: DescendantFocus) -> None:
   - Useful for parent widgets tracking child focus changes

5. EVENTS THAT WORK WITH @on + CSS SELECTORS:
   - Button.Pressed (has 'control' attribute)
   - Input.Submitted (has 'control' attribute)
   - Input.Changed (has 'control' attribute)
   - ListView.Selected (has 'control' attribute)
   - Custom messages with 'control' or other matchable attributes

6. EVENTS THAT DON'T WORK WITH @on + CSS SELECTORS:
   - Focus (no 'control' attribute)
   - Blur (no 'control' attribute)
   - DescendantFocus (no 'control' attribute)
   - DescendantBlur (no 'control' attribute)
   - Key events (no 'control' attribute)
   - Mouse events (no 'control' attribute)

7. ERROR MESSAGE EXPLANATION:
   "The message class must have a 'control' to match with the on decorator"
   
   This error occurs when you try to use @on decorator with CSS selectors
   on events that don't have a 'control' attribute. The CSS selector matching
   in @on decorator requires the event to have a 'control' attribute that
   points to the widget, which allows Textual to match against the CSS selector.
"""


if __name__ == "__main__":
    # Note: Don't run this in the current environment as noted in CLAUDE.md
    # This is for reference only
    pass