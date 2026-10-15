from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from db.database import initialise_database
from ui.login import LoginScreen

CSS = """
Screen { background: $surface; }

Header { background: $primary; }

#dash-body { height: 1fr; }
#dash-greeting { height: 3; background: $panel; padding: 0 1; align-vertical: middle; }
#dash-welcome { width: 1fr; text-style: bold; color: $accent; }
#logout-btn { margin-left: 2; }

TabbedContent { height: 1fr; }
TabPane { height: 1fr; }

CrudView { height: 1fr; }
.crud-title { padding: 0 1; text-style: bold; color: $accent; background: $panel; }
.crud-search { height: 3; padding: 0 1; align-vertical: middle; }
.crud-search Input { margin-right: 1; }
.crud-buttons { height: 3; padding: 0 1; align-vertical: middle; }
.crud-buttons Button { margin-right: 1; }
CrudView DataTable { height: 1fr; }

FormModal { align: center middle; }
#form-box { width: 64; height: 88%; max-height: 88%; padding: 1 2; border: round $accent; background: $panel; overflow-y: auto; }
#form-title { text-style: bold; color: $accent; margin-bottom: 1; }
#confirm-message { margin: 1 0; }
#form-box Label { margin-top: 1; }
#form-box Input, #form-box Select, #form-box TextArea { margin-top: 1; }
#form-box TextArea { height: 5; }
.form-actions { height: 3; margin-top: 1; align-horizontal: center; align-vertical: middle; }
.form-actions Button { margin-right: 1; }

#confirm-box { width: 52; padding: 1 2; border: round $error; background: $panel; }

#login-screen { height: 1fr; align: center middle; }
#login-box { width: 46; height: auto; padding: 2 3; border: round $accent; background: $panel; }
#login-title { text-align: center; text-style: bold; color: $accent; }
#login-sub { text-align: center; color: $text-muted; }
#login-box Label { margin-top: 1; }
#login-box Input { margin-top: 1; }
#login-btn { margin-top: 2; }
#login-hint { margin-top: 2; color: $text-muted; text-align: center; }

.profile-details { padding: 0 1; margin: 1 0; }
.profile-form { width: 40; padding: 0 1; }
.profile-form Input { margin-top: 1; }
#profile-change { margin-top: 2; width: 20; }
"""


class SMSApp(App):
    TITLE = "Society Management System"
    SUB_TITLE = "SMS V2"
    CSS = CSS
    BINDINGS = [Binding("ctrl+q", "quit", "Quit")]

    def on_mount(self) -> None:
        initialise_database()
        self.push_screen(LoginScreen())