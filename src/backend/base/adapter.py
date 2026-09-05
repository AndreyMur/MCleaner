from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PackageInfo:
    name: str
    version: str
    size: int
    description: str
    is_installed: bool = True


@dataclass
class RemovalPlan:
    packages: List[PackageInfo]
    total_size: int
    can_proceed: bool
    blocked_packages: List[str]


class PackageManagerAdapter(ABC):
    @abstractmethod
    def get_installed_packages(self) -> List[PackageInfo]:
        pass

    @abstractmethod
    def get_cache_size(self) -> int:
        pass

    @abstractmethod
    def clean_cache(self) -> bool:
        pass

    @abstractmethod
    def simulate_removal(self, package_names: List[str]) -> RemovalPlan:
        pass

    @abstractmethod
    def remove_packages(self, package_names: List[str]) -> bool:
        pass

    @abstractmethod
    def get_orphaned_packages(self) -> List[PackageInfo]:
        pass

    @abstractmethod
    def autoremove(self) -> bool:
        pass
