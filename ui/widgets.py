from __future__ import annotations

import uuid
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, Static, TextArea

from db.database import get_connection

FieldSpec = dict[str, Any]


def safe_str(value: Any) -> str:
    return "" if value is None else str(value)


class FormModal(ModalScreen[dict | None]):
    """Generic modal form. Returns a dict of field values, or None on cancel."""

    def __init__(self, title: str, fields: list[FieldSpec], initial: dict | None = None):
        super().__init__()
        self._title = title
        self._fields = fields
        self._initial = initial or {}

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="form-box"):
            yield Static(self._title, id="form-title")
            for field in self._fields:
                name = field["name"]
                yield Label(field["label"] + (" *" if field.get("required") else ""))
                yield self._build_widget(field)
            yield Horizontal(
                Button("Save", variant="primary", id="form-save"),
                Button("Cancel", variant="default", id="form-cancel"),
                classes="form-actions",
            )

    def _build_widget(self, field: FieldSpec):
        name = field["name"]
        value = self._initial.get(name)
        ftype = field.get("type", "input")

        if ftype == "select":
            options = list(field.get("options") or [])
            if not field.get("required"):
                options = [("Select...", "")] + options
            valid_values = [opt[1] for opt in options]
            if value not in valid_values:
                value = options[0][1] if field.get("required") and options else None
            return Select(options, value=value, allow_blank=value is None, id=f"field-{name}")
        if ftype == "text_area":
            return TextArea(safe_str(value), id=f"field-{name}")
        if ftype == "password":
            return Input(safe_str(value), password=True, id=f"field-{name}")
        if ftype == "number":
            return Input(safe_str(value), type="number", id=f"field-{name}")
        return Input(safe_str(value), id=f"field-{name}")

    def _collect(self) -> dict:
        data: dict[str, Any] = {}
        for field in self._fields:
            name = field["name"]
            widget = self.query_one(f"#field-{name}")
            if isinstance(widget, Input):
                data[name] = widget.value.strip()
            elif isinstance(widget, TextArea):
                data[name] = widget.text.strip()
            elif isinstance(widget, Select):
                data[name] = "" if widget.value is None else widget.value
        return data

    def _validate(self, data: dict) -> str | None:
        for field in self._fields:
            if field.get("required") and not data.get(field["name"]):
                return f"'{field['label']}' is required."
        return None

    @on(Button.Pressed, "#form-save")
    def _save(self) -> None:
        data = self._collect()
        error = self._validate(data)
        if error:
            self.notify(error, severity="error")
            return
        self.dismiss(data)

    @on(Button.Pressed, "#form-cancel")
    def _cancel(self) -> None:
        self.dismiss(None)


class ConfirmModal(ModalScreen[bool]):
    def __init__(self, message: str, title: str = "Confirm"):
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Static(self._title, id="form-title")
            yield Static(self._message, id="confirm-message")
            yield Horizontal(
                Button("Yes", variant="primary", id="confirm-yes"),
                Button("No", variant="default", id="confirm-no"),
                classes="form-actions",
            )

    @on(Button.Pressed, "#confirm-yes")
    def _yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#confirm-no")
    def _no(self) -> None:
        self.dismiss(False)


class CrudView(Vertical):
    """Reusable CRUD table with a search bar, action buttons and modal forms."""

    title = "Records"
    headers: list[str] = []
    select_sql = ""
    order_by_sql = ""
    base_where = ""
    params_fixed: tuple = ()
    search_cols: list[str] = []
    pk_index = 0

    can_add = True
    can_edit = True
    can_delete = True

    def __init__(
        self,
        *,
        ctx: dict | None = None,
        role: str = "admin",
        resident_id: int | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.ctx = ctx or {}
        self.role = role
        self.resident_id = resident_id
        self._uid = uuid.uuid4().hex[:8]
        self._rows: list[tuple] = []
        self._apply_role_permissions()

    # -- configuration hooks -------------------------------------------------
    def _apply_role_permissions(self) -> None:
        pass

    def can(self, action: str) -> bool:
        return getattr(self, f"can_{action}", True)

    def custom_actions(self) -> list[tuple[str, str]]:
        return []

    def get_rows(self, keyword: str | None = None) -> list[tuple]:
        conn = get_connection()
        try:
            where = self.base_where
            params = list(self.params_fixed)
            if keyword and self.search_cols:
                conds = " OR ".join(f"{col} LIKE ?" for col in self.search_cols)
                extra = f"({conds})"
                where = (where + " AND " + extra) if where else "WHERE " + extra
                params += [f"%{keyword}%"] * len(self.search_cols)
            sql = f"{self.select_sql} {where} {self.order_by_sql}".strip()
            return [tuple(r) for r in conn.execute(sql, params)]
        finally:
            conn.close()

    # -- CRUD hooks -----------------------------------------------------------
    def get_form_fields(self) -> list[FieldSpec]:
        raise NotImplementedError

    def get_edit_values(self, pk) -> dict:
        return {}

    def insert_row(self, data: dict) -> None:
        raise NotImplementedError

    def update_row(self, pk, data: dict) -> None:
        raise NotImplementedError

    def delete_row(self, pk) -> None:
        raise NotImplementedError

    async def handle_extra(self, action_id: str) -> None:
        self.notify(f"Unhandled action: {action_id}")

    # -- compose / wiring ------------------------------------------------------
    def _tid(self, base: str) -> str:
        return f"{base}-{self._uid}"

    def compose(self) -> ComposeResult:
        yield Static(self.title, id=self._tid("crud-title"), classes="crud-title")
        with Horizontal(classes="crud-search"):
            yield Input(placeholder=f"Search {self.title.lower()}...", id=self._tid("searchbox"))
            yield Button("Search", id=self._tid("btn-search"))
            yield Button("Clear", id=self._tid("btn-clear"))
        yield DataTable(id=self._tid("table"), cursor_type="row", zebra_stripes=True)
        with Horizontal(classes="crud-buttons"):
            if self.can("add"):
                yield Button("Add", id=self._tid("btn-add"), variant="primary")
            if self.can("edit"):
                yield Button("Edit", id=self._tid("btn-edit"))
            if self.can("delete"):
                yield Button("Delete", id=self._tid("btn-delete"), variant="error")
            yield Button("Refresh", id=self._tid("btn-refresh"))
            for action_id, label in self.custom_actions():
                yield Button(label, id=self._tid(f"act-{action_id}"))

    def on_mount(self) -> None:
        table = self.query_one(f"#{self._tid('table')}", DataTable)
        for header in self.headers:
            table.add_column(header)
        self.refresh_table()

    def refresh_table(self, keyword: str | None = None) -> None:
        self._rows = self.get_rows(keyword)
        table = self.query_one(f"#{self._tid('table')}", DataTable)
        table.clear()
        for row in self._rows:
            table.add_row(*[safe_str(c) for c in row], key=str(row[self.pk_index]))
        self.query_one(f"#{self._tid('searchbox')}", Input).value = keyword or ""

    def _selected(self) -> tuple | None:
        table = self.query_one(f"#{self._tid('table')}", DataTable)
        idx = table.cursor_row
        if idx is None or idx >= len(self._rows):
            return None
        return self._rows[idx]

    async def _open_add(self) -> None:
        fields = self.get_form_fields()
        result = await self.app.push_screen(FormModal(f"Add {self.title}", fields), wait_for_dismiss=True)
        if result is None:
            return
        try:
            self.insert_row(result)
        except Exception as exc:
            self.notify(str(exc), severity="error")
            return
        self.refresh_table()
        self.notify(f"{self.title}: record added.")

    async def _open_edit(self) -> None:
        row = self._selected()
        if row is None:
            self.notify("Select a record first.", severity="warning")
            return
        pk = row[self.pk_index]
        fields = self.get_form_fields()
        initial = self.get_edit_values(pk)
        result = await self.app.push_screen(
            FormModal(f"Edit {self.title}", fields, initial), wait_for_dismiss=True
        )
        if result is None:
            return
        try:
            self.update_row(pk, result)
        except Exception as exc:
            self.notify(str(exc), severity="error")
            return
        self.refresh_table()
        self.notify(f"{self.title}: record updated.")

    async def _open_delete(self) -> None:
        row = self._selected()
        if row is None:
            self.notify("Select a record first.", severity="warning")
            return
        pk = row[self.pk_index]
        confirmed = await self.app.push_screen(
            ConfirmModal(f"Delete this {self.title.lower()} record? This cannot be undone."),
            wait_for_dismiss=True,
        )
        if not confirmed:
            return
        try:
            self.delete_row(pk)
        except Exception as exc:
            self.notify(str(exc), severity="error")
            return
        self.refresh_table()
        self.notify(f"{self.title}: record deleted.")

    async def _open_extra(self, action_id: str) -> None:
        await self.handle_extra(action_id)

    @on(Button.Pressed)
    def _on_button(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if not btn_id:
            return
        if btn_id == self._tid("btn-add"):
            self.run_worker(self._open_add(), exclusive=True, name=f"{self._tid('add')}")
        elif btn_id == self._tid("btn-edit"):
            self.run_worker(self._open_edit(), exclusive=True, name=f"{self._tid('edit')}")
        elif btn_id == self._tid("btn-delete"):
            self.run_worker(self._open_delete(), exclusive=True, name=f"{self._tid('delete')}")
        elif btn_id == self._tid("btn-refresh"):
            self.refresh_table()
        elif btn_id == self._tid("btn-search"):
            box = self.query_one(f"#{self._tid('searchbox')}", Input)
            self.refresh_table(box.value.strip() or None)
        elif btn_id == self._tid("btn-clear"):
            self.refresh_table()
        elif btn_id.startswith("act-") and btn_id.endswith(f"-{self._uid}"):
            action_id = btn_id[len("act-"):-len(f"-{self._uid}")]
            self.run_worker(
                self._open_extra(action_id),
                exclusive=True,
                name=f"{self._tid('extra')}",
            )

    @on(Input.Submitted)
    def _on_submit(self, event: Input.Submitted) -> None:
        if event.input.id == self._tid("searchbox"):
            self.refresh_table(event.value.strip() or None)