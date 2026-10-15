from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static, TabbedContent, TabPane

from ui.modules import (
    AmenityBookingsView,
    AnnouncementsView,
    ComplaintsView,
    MaintenanceView,
    MyBookingsView,
    MyDuesView,
    ParkingView,
    ProfileView,
    ResidentsView,
    SecurityView,
    VisitorsView,
)


class _Tab:
    def __init__(self, label: str, view, pane_id: str):
        self.label = label
        self.view = view
        self.pane_id = pane_id


class DashboardScreen(Screen):
    BINDINGS = [
        Binding("ctrl+l", "logout", "Logout"),
    ]

    def __init__(self, ctx: dict):
        super().__init__()
        self.ctx = ctx
        self.role = ctx["role"]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        tabs = self._tabs()
        with Vertical(id="dash-body"):
            with Horizontal(id="dash-greeting"):
                yield Static(f"Welcome, {self.ctx.get('display_name', self.ctx.get('username'))}", id="dash-welcome")
                yield Button("Logout", id="logout-btn", variant="error")
            with TabbedContent(initial=tabs[0].pane_id):
                for tab in tabs:
                    with TabPane(tab.label, id=tab.pane_id):
                        yield tab.view
        yield Footer()

    def action_logout(self) -> None:
        from ui.login import LoginScreen

        self.app.switch_screen(LoginScreen())

    @on(Button.Pressed, "#logout-btn")
    def _logout_button(self) -> None:
        self.action_logout()

    @staticmethod
    def _slug(label: str) -> str:
        return "tab-" + "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in label.strip().lower()).strip("-")

    def _tabs(self) -> list[_Tab]:
        role = self.role
        ctx = self.ctx

        def build(label, view) -> _Tab:
            return _Tab(label, view, self._slug(label))

        if role == "admin":
            return [
                build("Residents", ResidentsView(ctx=ctx, role=role)),
                build("Visitors", VisitorsView(ctx=ctx, role=role)),
                build("Security", SecurityView(ctx=ctx, role=role)),
                build("Complaints", ComplaintsView(ctx=ctx, role=role)),
                build("Announcements", AnnouncementsView(ctx=ctx, role=role)),
                build("Maintenance", MaintenanceView(ctx=ctx, role=role)),
                build("Amenities", AmenityBookingsView(ctx=ctx, role=role)),
                build("Parking", ParkingView(ctx=ctx, role=role)),
            ]
        if role == "staff":
            return [
                build("Visitors", VisitorsView(ctx=ctx, role=role)),
                build("Residents", ResidentsView(ctx=ctx, role=role)),
                build("Complaints", ComplaintsView(ctx=ctx, role=role)),
                build("Announcements", AnnouncementsView(ctx=ctx, role=role)),
                build("Parking", ParkingView(ctx=ctx, role=role)),
            ]
        return [
            build("Announcements", AnnouncementsView(ctx=ctx, role=role)),
            build("My Complaints", ComplaintsView(ctx=ctx, role=role, resident_id=ctx.get("resident_id"))),
            build("My Bookings", MyBookingsView(ctx=ctx, role=role, resident_id=ctx.get("resident_id"))),
            build("My Dues", MyDuesView(ctx=ctx, role=role, resident_id=ctx.get("resident_id"))),
            build("Profile", ProfileView(ctx)),
        ]