from .base.adapter import PackageManagerAdapter, PackageInfo, RemovalPlan
from .detect import ADAPTERS, create_adapter, detect_package_manager
from . import guards, operations, privileges, recovery

__all__ = [
    "PackageManagerAdapter",
    "PackageInfo",
    "RemovalPlan",
    "ADAPTERS",
    "create_adapter",
    "detect_package_manager",
    "guards",
    "operations",
    "privileges",
    "recovery",
]
