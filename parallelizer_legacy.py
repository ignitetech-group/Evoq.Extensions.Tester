from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils import format_claude_output_line
from evoq_types import ExtensionInfo
from tester import EvoqExtensionTester


class Parallelizer:
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
        max_workers: int = 10
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

    def test_extensions(
        self,
        extensions_to_test_name_list: Optional[List[str]] = None,
        on_output: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> List[Dict[str, Any]]:
        # Filter extension list based on provided names, or use all extensions
        if extensions_to_test_name_list:
            extension_list = [
                ext for ext in self.extension_list
                if ext.name in extensions_to_test_name_list
            ]
        else:
            extension_list = self.extension_list
        
        if self.parallel:
            return self._test_extensions_parallel(extension_list, on_output)
        else:
            return self.tester.test_extensions(extension_list, on_output)

    def _test_extensions_parallel(
        self,
        extension_list: List[ExtensionInfo],
        on_output: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self.tester.test_extension, extension, on_output)
                for extension in extension_list
            ]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                if on_output:
                    on_output(f"✅ Completed: {result.get('extension', 'unknown')}", result)
        return results

if __name__ == "__main__":
    parallelizer = Parallelizer(
        extension_csv_path=Path("evoq_extensions.csv"),
        repos_base_path=Path("C:\\DNN\\Evoq.Extensions.Tester\\repos"),
        v9_website_path=Path("http://localhost:8091"),
        v10_website_path=Path("http://localhost:8094")
    )
    
    # results = parallelizer.test_extensions(on_output=lambda x, y: print(format_claude_output_line(y)[0]))
    results = parallelizer.test_extensions(extensions_to_test_name_list=[
        "DNN_HTML",
        # "ContentLayout",
        # "Evoq.PersonaBar.AccountSettings",
        # "Evoq.PersonaBar.Assets",
        # "Evoq.PersonaBar.CommunityAnalytics",
        # "Evoq.PersonaBar.CommunitySettings",
        # "Evoq.PersonaBar.Pages",
        # "Evoq.PersonaBar.Templates",
        # "Evoq.PersonaBar.UI",
        # "Evoq.Social.Wiki",
        # "Publisher",
        ], on_output=lambda x, y: print(format_claude_output_line(y)[0]))
