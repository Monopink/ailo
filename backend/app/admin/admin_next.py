"""Starlette-Admin extension that preserves list state via `next` query."""

from __future__ import annotations

from urllib.parse import quote

from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.status import (
    HTTP_303_SEE_OTHER,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
)
from starlette_admin._types import RequestAction
from starlette_admin.contrib.sqla import Admin
from starlette_admin.exceptions import FormValidationError

from .navigation import get_admin_list_url, get_admin_next_url


class AdminWithNext(Admin):
    """Preserve list state after create/edit actions."""

    @staticmethod
    def _append_next_query(target_url: str, next_url: str | None) -> str:
        if not next_url:
            return target_url
        separator = "&" if "?" in target_url else "?"
        return f"{target_url}{separator}next={quote(next_url, safe='')}"

    async def _render_create(self, request: Request) -> Response:
        request.state.action = RequestAction.CREATE
        identity = request.path_params.get("identity")
        model = self._find_model_from_identity(identity)
        config = {"title": model.title(request), "model": model}
        if not model.is_accessible(request) or not model.can_create(request):
            raise HTTPException(HTTP_403_FORBIDDEN)
        if request.method == "GET":
            return self.templates.TemplateResponse(
                request=request,
                name=model.create_template,
                context=config,
            )

        form = await request.form()
        dict_obj = await self.form_to_dict(request, form, model, RequestAction.CREATE)
        try:
            obj = await model.create(request, dict_obj)
        except FormValidationError as exc:
            config.update(
                {
                    "errors": exc.errors,
                    "obj": dict_obj,
                }
            )
            return self.templates.TemplateResponse(
                request=request,
                name=model.create_template,
                context=config,
                status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            )

        pk = await model.get_pk_value(request, obj)
        identity_value = str(model.identity)
        next_url = get_admin_next_url(request)
        url = get_admin_list_url(request, identity_value)
        if form.get("_continue_editing", None) is not None:
            url = str(request.url_for(self.route_name + ":edit", identity=identity_value, pk=pk))
            url = self._append_next_query(url, next_url)
        elif form.get("_add_another", None) is not None:
            url = str(request.url_for(self.route_name + ":create", identity=identity_value))
            url = self._append_next_query(url, next_url)
        return RedirectResponse(url, status_code=HTTP_303_SEE_OTHER)

    async def _render_edit(self, request: Request) -> Response:
        request.state.action = RequestAction.EDIT
        identity = request.path_params.get("identity")
        model = self._find_model_from_identity(identity)
        if not model.is_accessible(request) or not model.can_edit(request):
            raise HTTPException(HTTP_403_FORBIDDEN)

        pk = request.path_params.get("pk")
        obj = await model.find_by_pk(request, pk)
        if obj is None:
            raise HTTPException(HTTP_404_NOT_FOUND)

        config = {
            "title": model.title(request),
            "model": model,
            "raw_obj": obj,
            "obj": await model.serialize(obj, request, RequestAction.EDIT),
        }
        if request.method == "GET":
            return self.templates.TemplateResponse(
                request=request,
                name=model.edit_template,
                context=config,
            )

        form = await request.form()
        dict_obj = await self.form_to_dict(request, form, model, RequestAction.EDIT)
        try:
            obj = await model.edit(request, pk, dict_obj)
        except FormValidationError as exc:
            config.update(
                {
                    "errors": exc.errors,
                    "obj": dict_obj,
                }
            )
            return self.templates.TemplateResponse(
                request=request,
                name=model.edit_template,
                context=config,
                status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            )

        pk = await model.get_pk_value(request, obj)
        identity_value = str(model.identity)
        next_url = get_admin_next_url(request)
        url = get_admin_list_url(request, identity_value)
        if form.get("_continue_editing", None) is not None:
            url = str(request.url_for(self.route_name + ":edit", identity=identity_value, pk=pk))
            url = self._append_next_query(url, next_url)
        elif form.get("_add_another", None) is not None:
            url = str(request.url_for(self.route_name + ":create", identity=identity_value))
            url = self._append_next_query(url, next_url)
        return RedirectResponse(url, status_code=HTTP_303_SEE_OTHER)
