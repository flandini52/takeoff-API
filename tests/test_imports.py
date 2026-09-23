"""Importa ogni modulo del progetto: intercetta import rotti, errori di
sintassi e problemi di import circolare senza bisogno di rete o database
(landini_etl non chiama get_settings()/si connette a nulla a import time —
solo dentro le funzioni, vedi config.py/load/postgres.py/api/client.py)."""

import importlib
import pkgutil

import landini_etl


def _all_submodule_names(package):
    names = [package.__name__]
    if hasattr(package, "__path__"):
        for _, name, _ in pkgutil.walk_packages(package.__path__, prefix=package.__name__ + "."):
            names.append(name)
    return names


def test_import_all_landini_etl_modules():
    for name in _all_submodule_names(landini_etl):
        importlib.import_module(name)


def test_import_streamlit_app_modules():
    import components.charts  # noqa: F401
    import components.kpi  # noqa: F401
    import components.sidebar  # noqa: F401
    import services.database  # noqa: F401
    import services.documents  # noqa: F401
    import services.etl  # noqa: F401
    import utils.access  # noqa: F401
    import utils.status  # noqa: F401
