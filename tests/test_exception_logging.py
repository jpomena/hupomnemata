"""Testes de observabilidade: falhas recuperáveis devem ser registradas."""

from unittest.mock import patch

from src.controllers.core_controller import CoreController
from src.services.cloud_sync_service import CloudSyncService
from src.services.metadata_service import MetadataService
from src.views.sidebar import SidebarData


class _ExplodingClient:
    def get(self, *_args, **_kwargs):
        raise RuntimeError("falha simulada de rede")


class _ExplodingService:
    def list_works(self):
        raise RuntimeError("falha simulada de banco")


def test_brasil_api_failure_is_logged_and_returns_none():
    service = MetadataService()

    with patch("src.services.metadata_service.log_exception") as log:
        result = service._fetch_brasil_api_isbn("9780000000000", _ExplodingClient())

    assert result is None
    log.assert_called_once()
    context, error = log.call_args.args
    assert "_fetch_brasil_api_isbn" in context
    assert isinstance(error, RuntimeError)


def test_schema_version_failure_is_logged_and_returns_unknown(tmp_path):
    service = CloudSyncService(
        base_dir=tmp_path,
        config_dir=tmp_path / "config",
        db_path=tmp_path / "inexistente" / "db.sqlite",
    )

    with patch("src.services.cloud_sync_service.log_exception") as log:
        result = service.get_current_schema_version()

    assert result == "unknown"
    log.assert_called_once()
    assert "get_current_schema_version" in log.call_args.args[0]


def test_sidebar_failure_is_logged_and_returns_empty_data():
    controller = CoreController.__new__(CoreController)
    controller.service = _ExplodingService()

    with patch("src.controllers.core_controller.log_exception") as log:
        result = controller.sidebar_data()

    assert isinstance(result, SidebarData)
    assert result.works is None
    assert result.fragments is None
    log.assert_called_once()
    assert "sidebar_data" in log.call_args.args[0]
