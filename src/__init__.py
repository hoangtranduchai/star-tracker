"""Star tracker subsystem."""

from .attitude import WahbaSolver
from .camera import CameraModel, demo_camera
from .catalog import CatalogManager, StarCatalog
from .centroid import CentroidDetector
from .identification import StarIdentifier
from .kvector import KVectorTable
from .pipeline import StarTrackerPipeline, TrackerResult
from .quaternion import angular_error_arcsec, boresight_ra_dec_deg, to_dcm
from .simulator import SkySimulator

__all__ = [
    "CameraModel",
    "demo_camera",
    "CatalogManager",
    "StarCatalog",
    "KVectorTable",
    "SkySimulator",
    "CentroidDetector",
    "StarIdentifier",
    "WahbaSolver",
    "StarTrackerPipeline",
    "TrackerResult",
    "angular_error_arcsec",
    "boresight_ra_dec_deg",
    "to_dcm",
]
