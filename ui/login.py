from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from db.database import authenticate, build_session


class LoginScreen(Screen):
    def compose(self) -> ComposeResult:
        with Vertical(id="login-screen"):
            with Vertical(id="login-box"):
                yield Static("Society Management System", id="login-title")
                yield Static("Admin / Security / Resident", id="login-sub")
                yield Label("Username")
                yield Input(id="login-user", placeholder="admin")
                yield Label("Password")
                yield Input(id="login-pass", password=True)
                yield Button("Login", variant="primary", id="login-btn")
                yield Static("Default admin login: admin / admin123", id="login-hint")

    @on(Button.Pressed, "#login-btn")
    async def _login(self) -> None:
        await self._do_login()

    @on(Input.Submitted)
    async def _submit(self, event: Input.Submitted) -> None:
        if event.input.id in ("login-user", "login-pass"):
            await self._do_login()

    async def _do_login(self) -> None:
        from ui.dashboards import DashboardScreen

        user_box = self.query_one("#login-user", Input)
        pass_box = self.query_one("#login-pass", Input)
        user = authenticate(user_box.value.strip(), pass_box.value)
        if user is None:
            self.notify("Invalid username or password.", severity="error")
            return
        ctx = build_session(user)
        self.app.current_user = ctx
        await self.app.push_screen(DashboardScreen(ctx))