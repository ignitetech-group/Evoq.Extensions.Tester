import os
import csv
import tempfile
import json
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from evoq_types import ExtensionInfo, FeatureInfo, ExtensionFeatures
import subprocess
import time
from datetime import datetime
from config import CLAUDE_MODEL, CLAUDE_ENV, CLAUDE_TIMEOUT, PROVIDER
from dotenv import load_dotenv
from utils import format_claude_output_line
from prompts import (
    get_priority_guidance,
    sanitize_filename,
    generate_feature_extraction_prompt,
    generate_feature_test_prompt,
)

load_dotenv()


class EvoqExtensionTester:
    """
    Two-step Evoq Extension Tester.
    
    Step 1: Feature Extraction - Analyze extension code and extract testable features
    Step 2: Feature Testing - Test each feature individually with focused prompts
    """
    extension_csv_path: Path
    extension_list: List[ExtensionInfo]
    repos_base_path: Path
    skip_na: bool
    v9_website_path: Path
    v10_website_path: Path
    features_cache_dir: Path

    def __init__(
        self, 
        extension_csv_path: Path, 
        repos_base_path: Path, 
        v9_website_path: Path, 
        v10_website_path: Path, 
        skip_na: bool = True,
        features_cache_dir: Optional[Path] = None
    ) -> None:
        self.extension_csv_path = extension_csv_path
        self.repos_base_path = repos_base_path
        self.skip_na = skip_na
        self.v9_website_path = v9_website_path
        self.v10_website_path = v10_website_path
        self.extension_list = []
        
        # Directory to cache extracted features JSON files
        self.features_cache_dir = features_cache_dir or (repos_base_path / "_features_cache")
        self.features_cache_dir.mkdir(exist_ok=True)
        
        self.read_extension_csv()

    def read_extension_csv(self) -> None:
        """Read the extension CSV file and populate the extension list."""
        with open(self.extension_csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if self.skip_na and row['Priority for E2E Testing'] == 'N/A':
                    continue
                self.extension_list.append(ExtensionInfo(
                    name=row['Extension Name'],
                    priority=row['Priority for E2E Testing'],
                    repo=row['Repository'],
                    extension_type=row['Extension Type']
                ))

    def get_extension_by_name(self, name: str) -> Optional[ExtensionInfo]:
        """Find an extension by name (case-insensitive)."""
        for ext in self.extension_list:
            if ext.name.lower() == name.lower():
                return ext
        return None


    # =========================================================================
    # STEP 1: FEATURE EXTRACTION
    # =========================================================================

    def get_features_cache_path(self, extension: ExtensionInfo) -> Path:
        """Get the path to the cached features JSON file for an extension."""
        return self.features_cache_dir / f"{extension.name}_features.json"

    def load_cached_features(self, extension: ExtensionInfo) -> Optional[ExtensionFeatures]:
        """Load previously extracted features from cache if available."""
        cache_path = self.get_features_cache_path(extension)
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return ExtensionFeatures.from_dict(data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Failed to load cached features for {extension.name}: {e}")
        return None

    def save_features_to_cache(self, ext_features: ExtensionFeatures) -> None:
        """Save extracted features to cache."""
        cache_path = self.get_features_cache_path(ext_features.extension)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(ext_features.to_dict(), f, indent=2)


    def extract_features(
        self,
        extension: ExtensionInfo,
        on_output: Optional[Callable[[ExtensionInfo, str], None]] = None,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> ExtensionFeatures:
        """
        Step 1: Extract features from an extension using Claude Code.
        
        Args:
            extension: The extension to analyze
            on_output: Optional callback for streaming output
            use_cache: Whether to use cached features if available
            force_refresh: Force re-extraction even if cache exists
            
        Returns:
            ExtensionFeatures object with all extracted features
        """
        # Check cache first
        if use_cache and not force_refresh:
            cached = self.load_cached_features(extension)
            if cached:
                print(f"✅ Using cached features for {extension.name} ({len(cached.features)} features)")
                return cached

        print(f"🔍 Extracting features for {extension.name}...")
        
        prompt = generate_feature_extraction_prompt(
            extension_name=extension.name,
            extension_type=extension.extension_type,
            extension_priority=extension.priority,
            extension_repo=extension.repo,
            repos_base_path=self.repos_base_path,
        )
        result = self._run_claude_code(
            prompt=prompt,
            extension=extension,
            on_output=on_output,
            output_format="text",  # We want JSON output, not stream
            allowed_tools=["Read", "Grep", "Glob", "Bash"],  # Read-only for analysis
        )
        
        # Parse the JSON output from Claude
        features = self._parse_features_output(extension, result)
        
        # Save to cache
        self.save_features_to_cache(features)
        
        print(f"✅ Extracted {len(features.features)} features for {extension.name}")
        return features

    def _parse_features_output(self, extension: ExtensionInfo, result: Dict[str, Any]) -> ExtensionFeatures:
        """Parse Claude's output to extract features JSON."""
        output = result.get("output", "")
        
        # Try to find JSON in the output
        features_list = []
        try:
            # Look for JSON object in output
            json_start = output.find('{')
            json_end = output.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = output[json_start:json_end]
                data = json.loads(json_str)
                
                for f in data.get("features", []):
                    features_list.append(FeatureInfo(
                        name=f.get("name", "Unknown"),
                        description=f.get("description", ""),
                        files=f.get("files", []),
                        ui_location=f.get("ui_location"),
                        test_scenarios=f.get("test_scenarios", []),
                        dependencies=f.get("dependencies", []),
                        priority=f.get("priority", "Medium"),
                    ))
        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse features JSON for {extension.name}: {e}")
            # Create a single default feature if parsing fails
            features_list.append(FeatureInfo(
                name=f"{extension.name} - Full Extension",
                description=f"Test the entire {extension.name} extension",
                files=[],
                ui_location=None,
                test_scenarios=["Basic functionality test"],
                dependencies=[],
                priority=extension.priority,
            ))
        
        return ExtensionFeatures(
            extension=extension,
            features=features_list,
            extraction_timestamp=datetime.now().isoformat(),
            extraction_model=CLAUDE_MODEL,
        )

    # =========================================================================
    # STEP 2: FEATURE TESTING
    # =========================================================================

    def test_feature(
        self,
        extension: ExtensionInfo,
        feature: FeatureInfo,
        feature_index: int,
        total_features: int,
        on_output: Optional[Callable[[ExtensionInfo, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Step 2: Test a single feature of an extension.
        
        Args:
            extension: The extension containing the feature
            feature: The specific feature to test
            feature_index: Index of this feature (for progress tracking)
            total_features: Total number of features in the extension
            on_output: Optional callback for streaming output
            
        Returns:
            Result dict with success, output, error, duration, etc.
        """
        print(f"🧪 Testing feature [{feature_index + 1}/{total_features}]: {feature.name}")
        
        prompt = generate_feature_test_prompt(
            extension_name=extension.name,
            extension_type=extension.extension_type,
            extension_priority=extension.priority,
            extension_repo=extension.repo,
            feature_name=feature.name,
            feature_description=feature.description,
            feature_priority=feature.priority,
            feature_ui_location=feature.ui_location,
            feature_files=feature.files,
            feature_test_scenarios=feature.test_scenarios,
            feature_dependencies=feature.dependencies,
            feature_index=feature_index,
            total_features=total_features,
            repos_base_path=self.repos_base_path,
            v10_website_path=self.v10_website_path,
        )
        
        return self._run_claude_code(
            prompt=prompt,
            extension=extension,
            on_output=on_output,
            output_format="stream-json",
            allowed_tools=[
                "Read", "Grep", "Glob", "Bash",
                "mcp__playwright__*"  # Playwright MCP for browser testing
            ],
            feature_name=feature.name,
        )

    def test_extension(
        self,
        extension: ExtensionInfo,
        on_output: Optional[Callable[[ExtensionInfo, str], None]] = None,
        use_cached_features: bool = True
    ) -> Dict[str, Any]:
        """
        Full two-step test for an extension.
        
        Step 1: Extract features (or load from cache)
        Step 2: Test each feature individually
        
        Args:
            extension: The extension to test
            on_output: Optional callback for streaming output
            use_cached_features: Whether to use cached features
            
        Returns:
            Aggregated results dict
        """
        start_time = time.time()
        
        # Step 1: Extract features
        ext_features = self.extract_features(
            extension, 
            on_output=on_output,
            use_cache=use_cached_features
        )
        
        # Step 2: Test each feature
        feature_results = []
        for i, feature in enumerate(ext_features.features):
            result = self.test_feature(
                extension=extension,
                feature=feature,
                feature_index=i,
                total_features=len(ext_features.features),
                on_output=on_output
            )
            feature_results.append({
                "feature": feature.name,
                "result": result
            })
        
        return {
            "extension": extension.name,
            "total_features": len(ext_features.features),
            "feature_results": feature_results,
            "duration_seconds": time.time() - start_time,
            "timestamp": datetime.now().isoformat(),
            "success": all(r["result"].get("success", False) for r in feature_results),
        }

    def test_extensions(
        self,
        on_output: Optional[Callable[[ExtensionInfo, str], None]] = None
    ) -> List[Dict[str, Any]]:
        """Test all extensions using the two-step process."""
        results = []
        for extension in self.extension_list:
            result = self.test_extension(extension, on_output)
            results.append(result)
        return results

    def run_test_by_name(
        self,
        name: str,
        on_output: Optional[Callable[[ExtensionInfo, str], None]] = None
    ) -> Dict[str, Any]:
        """Run the two-step test for an extension by name."""
        extension = self.get_extension_by_name(name)
        if not extension:
            available = [ext.name for ext in self.extension_list]
            raise ValueError(f"Extension '{name}' not found. Available: {available}")
        return self.test_extension(extension, on_output)

    # =========================================================================
    # CLAUDE CODE EXECUTION
    # =========================================================================

    def _run_claude_code(
        self,
        prompt: str,
        extension: ExtensionInfo,
        on_output: Optional[Callable[[ExtensionInfo, str], None]] = None,
        output_format: str = "stream-json",
        allowed_tools: Optional[List[str]] = None,
        feature_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run Claude Code CLI with the given prompt.
        
        Args:
            prompt: The prompt to send
            extension: The extension being tested
            on_output: Optional streaming callback
            output_format: "stream-json" or "text"
            allowed_tools: List of tools to allow
            feature_name: Optional feature name for logging
            
        Returns:
            Result dict with success, output, error, duration
        """
        # Create temp file for the prompt
        safe_feature_name = sanitize_filename(feature_name) if feature_name else ""
        suffix = f"_{safe_feature_name}" if safe_feature_name else ""
        temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.md',
            prefix=f'claude_prompt_{sanitize_filename(extension.name)}{suffix}_',
            dir=self.repos_base_path,
            delete=False,
            encoding='utf-8'
        )
        complex_prompt_filename = Path(temp_file.name)
        
        try:
            temp_file.write(prompt)
            temp_file.close()

            simple_prompt = f"Read the file {complex_prompt_filename} and follow ALL instructions in it completely. ULTRATHINK!!!"
            
            result = {
                "success": False,
                "output": "",
                "error": "",
                "duration_seconds": 0,
                "extension": extension.name,
                "feature": feature_name,
                "timestamp": datetime.now().isoformat(),
                "model": CLAUDE_MODEL,
            }

            start_time = time.time()

            # Build command
            import platform
            import shutil
            
            claude_cmd = "claude"
            if platform.system() == "Windows":
                claude_path = shutil.which("claude")
                if claude_path:
                    claude_cmd = claude_path
                elif shutil.which("claude.cmd"):
                    claude_cmd = "claude.cmd"
            
            cmd = [
                claude_cmd,
                "-p", simple_prompt,
                "--model", CLAUDE_MODEL,
                "--output-format", output_format,
                "--verbose",
                "--dangerously-skip-permissions",
            ]
            
            if allowed_tools:
                cmd.extend(["--allowedTools", ",".join(allowed_tools)])
            
            # Environment with Bedrock settings
            env = os.environ.copy()
            env.update(CLAUDE_ENV)
            
            # Run Claude Code
            process = subprocess.Popen(
                cmd,
                cwd=str(self.repos_base_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env,
            )

            context = f"{extension.name}"
            if feature_name:
                context += f" > {feature_name}"
            print(f"🚀 Running Claude Code for {context}")
            
            output_lines = []
            
            for line in process.stdout:
                formatted_line, raw_data = format_claude_output_line(line)
                
                if on_output:
                    on_output(extension, line)
                else:
                    if formatted_line:
                        print(formatted_line)
                
                output_lines.append(line)
            
            # Save output log
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_name = f"claude_output_{sanitize_filename(extension.name)}"
            if feature_name:
                log_name += f"_{sanitize_filename(feature_name)}"
            log_name += f"_{timestamp}.txt"
            
            # Create debug_logs directory if it doesn't exist
            debug_logs_dir = Path("debug_logs")
            debug_logs_dir.mkdir(exist_ok=True)
            
            log_path = debug_logs_dir / log_name
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(output_lines))
            
            process.wait(timeout=CLAUDE_TIMEOUT)
            result["duration_seconds"] = time.time() - start_time
            result["output"] = "\n".join(output_lines)
            result["success"] = process.returncode == 0
            result["error"] = process.stderr.read()
            
            return result
            
        finally:
            if complex_prompt_filename.exists():
                complex_prompt_filename.unlink()


# =============================================================================
# CLI USAGE
# =============================================================================

if __name__ == "__main__":
    tester = EvoqExtensionTester(
        extension_csv_path=Path("evoq_extensions.csv"),
        repos_base_path=Path("C:\\DNN\\Evoq.Extensions.Tester\\repos"),
        v9_website_path=Path("http://localhost:8091"),
        v10_website_path=Path("http://localhost:8094"),
    )
    
    # Example: Extract features only
    # features = tester.extract_features(tester.extension_list[0])
    # print(f"Found {len(features.features)} features")
    
    # Example: Full test by name
    result = tester.run_test_by_name("DNN_HTML")
    print(result)
