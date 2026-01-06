from typing import TypedDict, List, Optional
from dataclasses import dataclass, field


class ExtensionInfo:
    """Information about an Evoq extension loaded from CSV."""
    name: str
    priority: str
    repo: str
    extension_type: str

    def __init__(self, name: str, priority: str, repo: str, extension_type: str) -> None:
        self.name = name
        self.priority = priority
        self.repo = repo
        self.extension_type = extension_type


@dataclass
class FeatureInfo:
    """
    Represents a single testable feature within an extension.
    Generated during Step 1 (Feature Extraction).
    """
    name: str                          # Feature name (e.g., "User Profile Editing")
    description: str                   # What the feature does
    files: List[str]                   # Relevant source files for this feature
    ui_location: Optional[str] = None  # Where to find it in the UI (e.g., "Admin > Users > Edit Profile")
    test_scenarios: List[str] = field(default_factory=list)  # Suggested test scenarios
    dependencies: List[str] = field(default_factory=list)    # Other features this depends on
    priority: str = "Medium"           # Feature-level priority (can differ from extension priority)


@dataclass
class ExtensionFeatures:
    """
    Container for an extension and its extracted features.
    This is the output of Step 1 (Feature Extraction).
    """
    extension: ExtensionInfo
    features: List[FeatureInfo] = field(default_factory=list)
    extraction_timestamp: Optional[str] = None
    extraction_model: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "extension": {
                "name": self.extension.name,
                "priority": self.extension.priority,
                "repo": self.extension.repo,
                "extension_type": self.extension.extension_type,
            },
            "features": [
                {
                    "name": f.name,
                    "description": f.description,
                    "files": f.files,
                    "ui_location": f.ui_location,
                    "test_scenarios": f.test_scenarios,
                    "dependencies": f.dependencies,
                    "priority": f.priority,
                }
                for f in self.features
            ],
            "extraction_timestamp": self.extraction_timestamp,
            "extraction_model": self.extraction_model,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ExtensionFeatures":
        """Create from dictionary (JSON deserialization)."""
        ext_data = data["extension"]
        extension = ExtensionInfo(
            name=ext_data["name"],
            priority=ext_data["priority"],
            repo=ext_data["repo"],
            extension_type=ext_data["extension_type"],
        )
        features = [
            FeatureInfo(
                name=f["name"],
                description=f["description"],
                files=f["files"],
                ui_location=f.get("ui_location"),
                test_scenarios=f.get("test_scenarios", []),
                dependencies=f.get("dependencies", []),
                priority=f.get("priority", "Medium"),
            )
            for f in data.get("features", [])
        ]
        return cls(
            extension=extension,
            features=features,
            extraction_timestamp=data.get("extraction_timestamp"),
            extraction_model=data.get("extraction_model"),
        )
