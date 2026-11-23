"""Implementações de generation do compositor Nous."""

from __future__ import annotations

from typing import TYPE_CHECKING

import asyncio
import flet as ft
from src.utils.ui_thread import run_on_ui
from src.utils.control_safety import safe_update
import threading

if TYPE_CHECKING:
    from src.views.nous_composer import NousComposer


def handle_single_generate(self: NousComposer, work_id: int) -> None:
    """Dispara a geração de descrição para uma única obra com feedback visual imediato em tempo real."""
    if work_id in self.generating_work_ids or self.is_batch_running:
        return

    self.generating_work_ids.add(work_id)
    work_item = next((w for w in self.works_data if w["id"] == work_id), None)
    actions_ctrl = self.work_actions_containers.get(work_id)
    if actions_ctrl is not None and work_item is not None:
        actions_ctrl.content = self._build_work_actions(work_item)
        safe_update(actions_ctrl)

    if hasattr(self.page, "overlay") and self.page.overlay is not None:
        snack = ft.SnackBar(ft.Text("Gerando síntese epistemológica com Nous..."))
        self.page.overlay.append(snack)
        snack.open = True
        safe_update(self.page)

    def _apply_generation_result(ok: bool, msg: str) -> None:
        self.generating_work_ids.discard(work_id)
        if ok:
            if hasattr(self.page, "overlay") and self.page.overlay is not None:
                res_snack = ft.SnackBar(ft.Text("✓ Síntese gerada e salva com sucesso!"))
                self.page.overlay.append(res_snack)
                res_snack.open = True
            self._update_single_work_ui(work_id)
        else:
            if hasattr(self.page, "overlay") and self.page.overlay is not None:
                res_snack = ft.SnackBar(ft.Text(f"Erro: {msg}"))
                self.page.overlay.append(res_snack)
                res_snack.open = True
            target_w = next((w for w in self.works_data if w["id"] == work_id), None)
            act_box = self.work_actions_containers.get(work_id)
            if act_box is not None and target_w is not None:
                act_box.content = self._build_work_actions(target_w)
                safe_update(act_box)
        safe_update(self.page)

    async def _async_generate():
        try:
            ok, msg = await asyncio.to_thread(self.nous_service.generate_work_description, work_id)
        except Exception as err:
            ok, msg = False, str(err)

        _apply_generation_result(ok, msg)

    run_task = getattr(self.page, "run_task", None)
    if run_task is not None:
        run_task(_async_generate)
    else:
        def _thread_fallback():
            try:
                ok, msg = self.nous_service.generate_work_description(work_id)
            except Exception as err:
                ok, msg = False, str(err)
            run_on_ui(self.page, lambda: _apply_generation_result(ok, msg))

        threading.Thread(target=_thread_fallback, daemon=True).start()


def handle_batch_generation(self: NousComposer, _e: ft.ControlEvent) -> None:
    """Executa processamento em lote com atualização viva e granular em tempo real."""
    if self.is_batch_running:
        return

    self.is_batch_running = True
    self.batch_progress_bar.visible = True
    self.batch_progress_text.visible = True
    self.batch_progress_bar.value = 0.0
    self.batch_progress_text.value = "Iniciando processamento com motor Nous..."
    safe_update(self.page)

    def update_progress(curr: int, total: int, title: str) -> None:
        def _apply() -> None:
            self.batch_progress_bar.value = curr / max(1, total)
            self.batch_progress_text.value = f"Processando ({curr}/{total}): {title}"
            safe_update(self.batch_progress_bar)
            safe_update(self.batch_progress_text)

        run_on_ui(self.page, _apply)

    def on_item_completed(w_id: int, ok: bool, msg: str) -> None:
        run_on_ui(self.page, lambda: self._update_single_work_ui(w_id))

    def _apply_batch_completion(res_msg: str) -> None:
        self.is_batch_running = False
        self.batch_progress_bar.visible = False
        self.batch_progress_text.visible = False

        if hasattr(self.page, "overlay") and self.page.overlay is not None:
            snack = ft.SnackBar(ft.Text(res_msg))
            self.page.overlay.append(snack)
            snack.open = True
        self._refresh_works_data()
        safe_update(self.page)

    async def _async_batch():
        try:
            results = await asyncio.to_thread(
                self.nous_service.generate_batch_pending,
                on_progress=update_progress,
                on_work_completed=on_item_completed,
            )
            res_msg = f"Concluído: {results['success']} obras processadas com sucesso, {results['failed']} falhas."
        except Exception as err:
            res_msg = f"Falha no processamento em lote: {err}"

        _apply_batch_completion(res_msg)

    run_task = getattr(self.page, "run_task", None)
    if run_task is not None:
        run_task(_async_batch)
    else:
        def _thread_batch_fallback():
            try:
                results = self.nous_service.generate_batch_pending(
                    on_progress=update_progress,
                    on_work_completed=on_item_completed,
                )
                res_msg = f"Concluído: {results['success']} obras processadas com sucesso, {results['failed']} falhas."
            except Exception as err:
                res_msg = f"Falha no processamento em lote: {err}"

            run_on_ui(self.page, lambda: _apply_batch_completion(res_msg))

        threading.Thread(target=_thread_batch_fallback, daemon=True).start()
