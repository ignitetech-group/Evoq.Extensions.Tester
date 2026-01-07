from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils import format_claude_output_line
from evoq_types import ExtensionInfo, FeatureInfo, ExtensionFeatures
from tester import EvoqExtensionTester


class Parallelizer:
    """
    Parallelized Evoq Extension Tester.
    
    Supports parallel execution of:
    - Step 1: Feature extraction for multiple extensions
    - Step 2: Feature testing (both across extensions and within extensions)
    
    SCALING GUIDE:
    - Local machine (16GB RAM): 20-50 workers
    - Local machine (32GB RAM): 50-100 workers  
    - EC2 r6i.xlarge (32GB): 50-100 workers
    - EC2 r6i.2xlarge (64GB): 100-200 workers
    - EC2 r6i.4xlarge (128GB): 200-400 workers
    
    Check Bedrock quotas at: AWS Console > Service Quotas > Amazon Bedrock
    Key quotas to increase:
    - Requests per minute for Claude models
    - Tokens per minute for Claude models
    """
    extension_list: List[ExtensionInfo]
    tester: EvoqExtensionTester
    parallel: bool
    max_workers: int

    def __init__(
        self,
        extension_csv_path: Path,
        repos_base_path: Path,
        v9_website_path: Path,
        v10_website_path: Path,
        parallel: bool = True,
        max_workers: int = 50,  # Higher default for I/O-bound work
    ) -> None:
        self.extension_list = []
        self.tester = EvoqExtensionTester(
            extension_csv_path=extension_csv_path,
            repos_base_path=repos_base_path,
            v9_website_path=v9_website_path,
            v10_website_path=v10_website_path
        )
        self.extension_list = self.tester.extension_list
        self.parallel = parallel
        self.max_workers = max_workers

    # =========================================================================
    # STEP 1: PARALLEL FEATURE EXTRACTION
    # =========================================================================

    def extract_all_features(
        self,
        extensions_to_extract: Optional[List[str]] = None,
        on_output: Optional[Callable[[ExtensionInfo, str], None]] = None,
        use_cache: bool = True,
        force_refresh: bool = False,
    ) -> Dict[str, ExtensionFeatures]:
        """
        Extract features from multiple extensions (optionally in parallel).
        
        Args:
            extensions_to_extract: List of extension names to process (None = all)
            on_output: Optional callback for streaming output
            use_cache: Whether to use cached features
            force_refresh: Force re-extraction even if cache exists
            
        Returns:
            Dict mapping extension name -> ExtensionFeatures
        """
        # Filter extensions
        if extensions_to_extract:
            ext_list = [
                ext for ext in self.extension_list
                if ext.name in extensions_to_extract
            ]
        else:
            ext_list = self.extension_list

        if self.parallel:
            return self._extract_features_parallel(
                ext_list, on_output, use_cache, force_refresh
            )
        else:
            return self._extract_features_sequential(
                ext_list, on_output, use_cache, force_refresh
            )

    def _extract_features_sequential(
        self,
        ext_list: List[ExtensionInfo],
        on_output: Optional[Callable[[ExtensionInfo, str], None]],
        use_cache: bool,
        force_refresh: bool,
    ) -> Dict[str, ExtensionFeatures]:
        """Extract features sequentially."""
        results = {}
        for ext in ext_list:
            features = self.tester.extract_features(
                ext, on_output, use_cache, force_refresh
            )
            results[ext.name] = features
        return results

    def _extract_features_parallel(
        self,
        ext_list: List[ExtensionInfo],
        on_output: Optional[Callable[[ExtensionInfo, str], None]],
        use_cache: bool,
        force_refresh: bool,
    ) -> Dict[str, ExtensionFeatures]:
        """Extract features in parallel."""
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_ext = {
                executor.submit(
                    self.tester.extract_features,
                    ext, on_output, use_cache, force_refresh
                ): ext
                for ext in ext_list
            }
            
            for future in as_completed(future_to_ext):
                ext = future_to_ext[future]
                try:
                    features = future.result()
                    results[ext.name] = features
                    print(f"✅ Extracted features for {ext.name} ({len(features.features)} features)")
                except Exception as e:
                    print(f"❌ Failed to extract features for {ext.name}: {e}")
                    
        return results

    # =========================================================================
    # STEP 2: PARALLEL FEATURE TESTING
    # =========================================================================

    def test_extensions(
        self,
        extensions_to_test_name_list: Optional[List[str]] = None,
        on_output: Optional[Callable[[ExtensionInfo, str], None]] = None,
        use_cached_features: bool = True,
        parallelize_features: bool = True,  # Also parallelize within extension
    ) -> List[Dict[str, Any]]:
        """
        Run the full two-step test process for multiple extensions.
        
        Args:
            extensions_to_test_name_list: Extension names to test (None = all)
            on_output: Optional callback for streaming output
            use_cached_features: Use cached features from Step 1
            parallelize_features: Also parallelize feature testing within each extension
            
        Returns:
            List of result dicts for each extension
        """
        # Filter extensions
        if extensions_to_test_name_list:
            ext_list = [
                ext for ext in self.extension_list
                if ext.name in extensions_to_test_name_list
            ]
        else:
            ext_list = self.extension_list

        if self.parallel:
            return self._test_extensions_parallel(
                ext_list, on_output, use_cached_features, parallelize_features
            )
        else:
            return self._test_extensions_sequential(
                ext_list, on_output, use_cached_features
            )

    def _test_extensions_sequential(
        self,
        ext_list: List[ExtensionInfo],
        on_output: Optional[Callable[[ExtensionInfo, str], None]],
        use_cached_features: bool,
    ) -> List[Dict[str, Any]]:
        """Test extensions sequentially."""
        results = []
        for ext in ext_list:
            result = self.tester.test_extension(ext, on_output, use_cached_features)
            results.append(result)
        return results

    def _test_extensions_parallel(
        self,
        ext_list: List[ExtensionInfo],
        on_output: Optional[Callable[[ExtensionInfo, str], None]],
        use_cached_features: bool,
        parallelize_features: bool,
    ) -> List[Dict[str, Any]]:
        """Test extensions in parallel."""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            if parallelize_features:
                # Flatten: parallelize at the feature level across all extensions
                results = self._test_all_features_parallel(
                    ext_list, on_output, use_cached_features, executor
                )
            else:
                # Parallelize at the extension level only
                future_to_ext = {
                    executor.submit(
                        self.tester.test_extension,
                        ext, on_output, use_cached_features
                    ): ext
                    for ext in ext_list
                }
                
                for future in as_completed(future_to_ext):
                    ext = future_to_ext[future]
                    try:
                        result = future.result()
                        results.append(result)
                        print(f"✅ Completed: {ext.name}")
                    except Exception as e:
                        print(f"❌ Failed: {ext.name}: {e}")
                        results.append({
                            "extension": ext.name,
                            "success": False,
                            "error": str(e),
                        })
                        
        return results

    def _test_all_features_parallel(
        self,
        ext_list: List[ExtensionInfo],
        on_output: Optional[Callable[[ExtensionInfo, str], None]],
        use_cached_features: bool,
        executor: ThreadPoolExecutor,
    ) -> List[Dict[str, Any]]:
        """
        Parallelize testing at the feature level across all extensions.
        This gives maximum parallelism but may be harder to track.
        """
        # First, extract features for all extensions (in parallel if needed)
        all_features: Dict[str, ExtensionFeatures] = self.extract_all_features(
            extensions_to_extract=[ext.name for ext in ext_list],
            on_output=on_output,
            use_cache=use_cached_features,
        )
        
        # Build list of (extension, feature, index, total) tuples
        test_tasks = []
        for ext_name, ext_features in all_features.items():
            total = len(ext_features.features)
            for i, feature in enumerate(ext_features.features):
                test_tasks.append((ext_features.extension, feature, i, total))
        
        print(f"📋 Testing {len(test_tasks)} features across {len(ext_list)} extensions")
        
        # Submit all feature tests
        future_to_task = {
            executor.submit(
                self.tester.test_feature,
                ext, feature, idx, total, on_output
            ): (ext, feature)
            for ext, feature, idx, total in test_tasks
        }
        
        # Collect results grouped by extension
        feature_results: Dict[str, List[Dict[str, Any]]] = {ext.name: [] for ext in ext_list}
        
        for future in as_completed(future_to_task):
            ext, feature = future_to_task[future]
            try:
                result = future.result()
                feature_results[ext.name].append({
                    "feature": feature.name,
                    "result": result,
                })
                print(f"✅ [{ext.name}] Feature done: {feature.name}")
            except Exception as e:
                print(f"❌ [{ext.name}] Feature failed: {feature.name}: {e}")
                feature_results[ext.name].append({
                    "feature": feature.name,
                    "result": {"success": False, "error": str(e)},
                })
        
        # Aggregate into extension-level results
        final_results = []
        for ext in ext_list:
            ext_features_data = all_features.get(ext.name)
            feature_res = feature_results.get(ext.name, [])
            final_results.append({
                "extension": ext.name,
                "total_features": len(ext_features_data.features) if ext_features_data else 0,
                "feature_results": feature_res,
                "success": all(r["result"].get("success", False) for r in feature_res),
            })
        
        return final_results

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def extract_features_by_name(
        self,
        name: str,
        on_output: Optional[Callable[[ExtensionInfo, str], None]] = None,
        force_refresh: bool = False,
    ) -> ExtensionFeatures:
        """Extract features for a single extension by name."""
        ext = self.tester.get_extension_by_name(name)
        if not ext:
            available = [e.name for e in self.extension_list]
            raise ValueError(f"Extension '{name}' not found. Available: {available}")
        return self.tester.extract_features(ext, on_output, use_cache=True, force_refresh=force_refresh)

    def test_by_name(
        self,
        name: str,
        on_output: Optional[Callable[[ExtensionInfo, str], None]] = None,
    ) -> Dict[str, Any]:
        """Run full two-step test for a single extension by name."""
        return self.tester.run_test_by_name(name, on_output)


# =============================================================================
# CLI USAGE
# =============================================================================

def default_output_handler(ext: ExtensionInfo, line: str) -> None:
    """Default output handler that formats and prints Claude output."""
    formatted, _ = format_claude_output_line(line)
    if formatted:
        # Add extension context prefix for parallel runs
        prefix = f"[{ext.name}] " if ext else ""
        for output_line in formatted.split('\n'):
            if output_line.strip():
                print(f"{prefix}{output_line}")


if __name__ == "__main__":
    parallelizer = Parallelizer(
        extension_csv_path=Path("evoq_extensions.csv"),
        repos_base_path=Path("C:\\DNN\\Evoq.Extensions.Tester\\repos"),
        v9_website_path=Path("http://localhost:8091"),
        v10_website_path=Path("http://localhost:8081"),
        parallel=True,
        max_workers=5,  # Increase this for more parallelism (50-200 recommended)
    )
    
    # Example: Extract features only (Step 1)
    # features = parallelizer.extract_all_features(
    #     extensions_to_extract=["DNN_HTML"],
    # )
    # for name, ext_features in features.items():
    #     print(f"{name}: {len(ext_features.features)} features")
    
    # Example: Full test (Step 1 + Step 2)
    results = parallelizer.test_extensions(
        extensions_to_test_name_list=[
            # 'DNN_HTML',
            'ContentLayout',
            'DotNetNuke.Professional.SearchCrawler',
            'Evoq.GoogleAnalyticsConnector',
            'DNNPro_ActiveDirectoryAuthentication',
            'Publisher',
            'Evoq.Content.GoogleAnalyticsConnector',
            'Evoq.GoogleTagManagerConnector',
            'Evoq.Social.ActivityStream',
            'Evoq.Social.Wiki',
            'Evoq.PersonaBar.UI',
            'Evoq.PersonaBar.AccountSettings',
            'Evoq.PersonaBar.Assets',
            'Evoq.PersonaBar.Pages',
            'Evoq.PersonaBar.SiteSettings',
            'Evoq.PersonaBar.Templates',
            'Evoq.PersonaBar.UrlManagement',
            'Evoq.PersonaBar.Users',
            'Evoq.PersonaBar.Workflow',
            'Evoq.PersonaBar.CommunityAnalytics',
            'Evoq.PersonaBar.CommunitySettings',
        ],
        on_output=default_output_handler,
    )

    # Final: Test All Extensions
    # results = parallelizer.test_extensions(
    #     on_output=default_output_handler,
    # )
    
    # Print summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    for r in results:
        status = "✅" if r.get("success") else "❌"
        print(f"{status} {r['extension']}: {r.get('total_features', 0)} features tested")
