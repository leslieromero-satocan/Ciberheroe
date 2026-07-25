import json
import logging
from enum import Enum

from typing import MutableMapping, Any

logger = logging.getLogger(f"kb4_integration.{__name__}")


def enum_serializer(obj: Any) -> Any:
    """Devuelve el literal de cada elemento del Enum"""
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(
        f"Object of type {type(obj).__name__} is not JSON serializable"
    )


def save_json(info: MutableMapping | dict, file: str):
    """Vuelca los datos pasados por parámetro a un archivo JSON"""
    try:
        with open(f"C:/TFT/out/{file}.json", "w") as f:
            json.dump(info, f, default=enum_serializer)
    except TypeError as e:
        logger.error(
            f"ERROR DE SERIALIZACIÓN: No se puede guardar '{file}.json'. Los datos contienen tipos no compatibles con JSON: {e}"
        )
    except OSError as e:
        logger.error(
            f"ERROR I/O: Fallo al escribir el archivo '{file}.json'. Revise los permisos o la ruta del archivo: {e}"
        )
    except Exception as e:
        logger.error(
            f"Ocurrió un error inesperado intentando guardar el archivo {file}.json: {e}"
        )
        raise
