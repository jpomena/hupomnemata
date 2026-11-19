"""Regressões do Nous: catálogo de modelos e transporte seguro da API key."""

import httpx

from src.services.nous_service import KNOWN_MODELS, NousAIService


def test_known_models_are_well_formed():
    # A versão anterior concatenava "gemini-3.1-flash-lite" + "gemini-2.5-flash"
    # por falta de vírgula, gerando um identificador inexistente.
    assert 'gemini-2.5-flash' in KNOWN_MODELS
    for model in KNOWN_MODELS:
        assert model.count('gemini') == 1, f'Modelo concatenado: {model}'
        assert model.startswith('gemini-'), model


def test_api_key_travels_in_header_not_in_url(monkeypatch):
    captured = {}

    class CapturingClient:
        def __init__(self, *args, **kwargs):
            captured['headers'] = kwargs.get('headers', {})
            captured['timeout'] = kwargs.get('timeout')

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, **kwargs):
            captured['url'] = url

            class Response:
                status_code = 200

                @staticmethod
                def json():
                    return {'models': []}

            return Response()

    monkeypatch.setattr(httpx, 'Client', CapturingClient)

    NousAIService().discover_available_models('AIzaSySecretKey')

    assert captured['headers'].get('x-goog-api-key') == 'AIzaSySecretKey'
    assert 'key=' not in captured['url']
    assert 'AIzaSySecretKey' not in captured['url']


def test_preferred_client_is_used_for_generation(monkeypatch):
    seen = {}

    class CapturingClient:
        def __init__(self, *args, **kwargs):
            seen['headers'] = kwargs.get('headers', {})

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None):
            seen['url'] = url

            class Response:
                status_code = 200

                @staticmethod
                def json():
                    return {
                        'candidates': [
                            {'content': {'parts': [{'text': 'OK'}]}}
                        ]
                    }

            return Response()

    monkeypatch.setattr(httpx, 'Client', CapturingClient)
    monkeypatch.setattr(
        NousAIService,
        'get_candidate_models',
        lambda self, key: ['gemini-2.5-flash'],
    )

    service = NousAIService()
    ok, _message = service.test_connection('AIzaSyHeaderKey')

    assert ok is True
    assert seen['headers'].get('x-goog-api-key') == 'AIzaSyHeaderKey'
    assert 'key=' not in seen['url']
