"""Ciclo de vida do app: autosave periódico e confirmação de saída."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import flet as ft

from src.controllers.core_controller import CoreController
from src.services.cloud_sync_service import SyncResult, SyncStatus


def _make_controller(view_config, sync_service=None):
    controller = CoreController.__new__(CoreController)
    dialogs = []
    controller.page = SimpleNamespace(
        show_dialog=lambda dialog: dialogs.append(dialog),
        pop_dialog=lambda: dialogs.pop() if dialogs else None,
        update=lambda: None,
        window=SimpleNamespace(prevent_close=False, close=lambda: None),
        run_task=None,
        overlay=[],
    )
    controller.view_config = view_config
    controller.cloud_sync_service = sync_service or MagicMock()
    controller._auto_sync_started = False
    controller._shutting_down = False
    controller._close_dialog_open = False
    controller._close_dialog = None
    controller._closing_sync = False
    controller._close_watchdog_timer = None
    controller._auto_conflict_dialog_open = False
    controller._auto_conflict_dialog = None
    controller._last_auto_conflict_signature = None
    controller.work_insert_modal = None
    controller._deleting_databases = False
    controller._cloud_pull_suspended = False
    controller._dialogs = dialogs
    return controller


def test_request_close_starts_automatic_sync(view_config, monkeypatch):
    controller = _make_controller(view_config)
    started = []

    class FakeThread:
        def __init__(self, target, daemon):
            started.append(target)

        def start(self):
            pass

    monkeypatch.setattr(
        'src.controllers.core_controller.threading.Thread',
        FakeThread,
    )
    controller.show_message = MagicMock()

    controller.request_close()

    assert controller.page.window.prevent_close is True
    assert controller._closing_sync is True
    assert controller._close_dialog_open is False
    assert started == [controller._close_sync_worker]
    controller.show_message.assert_called_once()


def test_after_close_sync_success_shuts_down(view_config):
    controller = _make_controller(view_config)
    controller._shutdown = MagicMock()

    controller._after_close_sync(
        SyncResult(status=SyncStatus.SUCCESS, message='ok', direction='push')
    )

    controller._shutdown.assert_called_once()


def test_after_close_sync_unauthenticated_shuts_down(view_config):
    controller = _make_controller(view_config)
    controller._shutdown = MagicMock()

    controller._after_close_sync(
        SyncResult(
            status=SyncStatus.UNAUTHENTICATED,
            message='sem nuvem',
        )
    )

    controller._shutdown.assert_called_once()


def test_after_close_sync_conflict_opens_decision_modal(view_config):
    controller = _make_controller(view_config)
    controller._shutdown = MagicMock()

    controller._after_close_sync(
        SyncResult(
            status=SyncStatus.CONFLICT,
            message='conflito',
            direction='conflict',
            details={
                'remote_manifest': {
                    'counts': {
                        'resources': 10,
                        'fragments': 20,
                        'compilations': 1,
                    }
                }
            },
        )
    )

    assert controller._close_dialog_open is True
    assert len(controller._dialogs) == 1
    dialog = controller._dialogs[0]
    assert [action.data['label'].value for action in dialog.actions] == [
        'Cancelar',
        'Manter Nuvem',
        'Manter Local',
    ]
    controller._shutdown.assert_not_called()

    dialog.actions[0].on_click(None)
    assert controller._close_dialog_open is False
    assert controller._closing_sync is False


def test_after_close_sync_error_opens_retry_modal(view_config):
    controller = _make_controller(view_config)

    controller._after_close_sync(
        SyncResult(status=SyncStatus.ERROR, message='falha de rede')
    )

    assert controller._close_dialog_open is True
    dialog = controller._dialogs[0]
    assert [action.data['label'].value for action in dialog.actions] == [
        'Cancelar',
        'Sair mesmo assim',
        'Tentar novamente',
    ]


def test_close_window_event_requests_close(view_config, monkeypatch):
    controller = _make_controller(view_config)
    controller.request_close = MagicMock()

    controller.handle_window_event(
        SimpleNamespace(type=ft.WindowEventType.CLOSE, data="")
    )

    controller.request_close.assert_called_once()


def test_auto_sync_rebuilds_ui_only_after_pull(view_config):
    service = MagicMock()
    service.sync.return_value = SyncResult(
        status=SyncStatus.SUCCESS,
        message="Database successfully updated from Google Drive.",
        direction="pull",
    )
    controller = _make_controller(view_config, service)
    controller.rebuild_ui = MagicMock()

    result = asyncio.run(controller.perform_auto_sync())

    assert result.status == SyncStatus.SUCCESS
    controller.rebuild_ui.assert_called_once()

    service.sync.return_value = SyncResult(
        status=SyncStatus.SUCCESS,
        message="Local changes successfully uploaded to Google Drive.",
        direction="push",
    )
    controller.rebuild_ui.reset_mock()
    asyncio.run(controller.perform_auto_sync())
    controller.rebuild_ui.assert_not_called()


def test_shutdown_disables_prevent_close_and_destroys_window(view_config):
    controller = _make_controller(view_config)
    destroyed = []
    controller.page.window.destroy = lambda: destroyed.append(True)

    controller._shutdown()

    assert controller._shutting_down is True
    assert controller.page.window.prevent_close is False
    assert destroyed == [True]


def test_auto_sync_conflict_opens_modal_once(view_config, monkeypatch):
    result = SyncResult(
        status=SyncStatus.CONFLICT,
        message="Conflict detected.",
        direction="conflict",
        details={
            "remote_manifest": {
                "db_sha256": "remote-hash",
                "counts": {"resources": 30, "fragments": 50, "compilations": 2},
            },
            "local_sha256": "local-hash",
        },
    )
    service = MagicMock()
    service.sync.return_value = result
    controller = _make_controller(view_config, service)
    monkeypatch.setattr(controller, "_show_auto_conflict", MagicMock())
    monkeypatch.setattr(controller, "show_message", MagicMock())

    asyncio.run(controller.perform_auto_sync())
    controller._show_auto_conflict.assert_called_once_with(result)

    controller._auto_conflict_dialog_open = False
    asyncio.run(controller.perform_auto_sync())
    assert controller._show_auto_conflict.call_count == 2


def test_auto_conflict_modal_offers_selection(view_config):
    result = SyncResult(
        status=SyncStatus.CONFLICT,
        message="Conflict detected.",
        direction="conflict",
        details={
            "remote_manifest": {
                "db_sha256": "remote-hash",
                "counts": {"resources": 30, "fragments": 50, "compilations": 2},
            },
            "local_sha256": "local-hash",
        },
    )
    controller = _make_controller(view_config)

    controller._show_auto_conflict(result)

    assert controller._auto_conflict_dialog_open is True
    assert len(controller._dialogs) == 1
    dialog = controller._dialogs[0]
    assert [action.data["label"].value for action in dialog.actions] == [
        'Depois',
        'Manter Nuvem',
        'Manter Local',
    ]


def test_delete_databases_local_only_suspends_auto_pull(view_config, monkeypatch):
    from contextlib import contextmanager

    service = MagicMock()

    @contextmanager
    def exclusive():
        yield

    service.sync_exclusive = exclusive
    controller = _make_controller(view_config, service)
    deleted = []
    recreated = []
    monkeypatch.setattr(
        'src.controllers.core_controller.delete_local_databases',
        lambda: deleted.append(True) or [],
    )
    monkeypatch.setattr(
        'src.controllers.core_controller.init_db',
        lambda: recreated.append(True),
    )
    controller.rebuild_ui = MagicMock()
    controller.show_message = MagicMock()

    controller.delete_databases(delete_cloud=False)

    assert deleted == [True]
    assert recreated == [True]
    assert controller._cloud_pull_suspended is True
    assert controller._deleting_databases is False
    controller.rebuild_ui.assert_called_once()
    controller.show_message.assert_called_once()


def test_shutdown_forces_exit_if_window_destroy_fails(view_config):
    controller = _make_controller(view_config)
    controller.page.run_task = MagicMock(side_effect=RuntimeError('loop fechado'))
    controller._force_exit = MagicMock()

    controller._shutdown()

    controller._force_exit.assert_called_once()


def test_close_sync_worker_arms_watchdog_for_terminal_result(view_config):
    service = MagicMock()
    service.sync.return_value = SyncResult(
        status=SyncStatus.SUCCESS,
        message='ok',
        direction='push',
    )
    controller = _make_controller(view_config, service)
    controller._after_close_sync = MagicMock()
    controller._arm_close_watchdog = MagicMock()

    controller._close_sync_worker()

    assert [
        arm.args[0] for arm in controller._arm_close_watchdog.call_args_list
    ] == [45.0, 6.0]
    controller._after_close_sync.assert_called_once()


def test_force_exit_closes_desktop_before_backend(view_config, monkeypatch):
    controller = _make_controller(view_config)
    calls = []
    monkeypatch.setattr(
        'src.controllers.core_controller.close_desktop_view',
        lambda: calls.append('desktop'),
    )
    monkeypatch.setattr(
        'src.controllers.core_controller.os._exit',
        lambda code: calls.append(('backend', code)),
    )

    controller._force_exit()

    assert calls == ['desktop', ('backend', 0)]
