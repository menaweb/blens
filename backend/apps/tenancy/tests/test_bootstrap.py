"""El worker de Celery no pasa por manage.py: el path lo prepara `config/__init__`."""

import sys
from pathlib import Path


def test_la_raiz_del_repo_esta_en_el_path():
    """Sin esto, `celery -A config` arranca pero no puede importar `engines`."""
    import config

    raiz = str(Path(config.__file__).resolve().parents[2])
    assert raiz in sys.path


def test_los_motores_se_importan_desde_el_backend():
    import engines.ens_applicability  # noqa: F401
    import engines.oscal_io  # noqa: F401
