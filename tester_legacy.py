import os
import csv
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from evoq_types import ExtensionInfo
import subprocess
import json
import time
from datetime import datetime
from config import BEDROCK_MODEL, BEDROCK_ENV, CLAUDE_TIMEOUT
from dotenv import load_dotenv
from utils import format_claude_output_line
load_dotenv()

class EvoqExtensionTester:
    extension_csv_path: Path
    extension_list: List[ExtensionInfo]
    repos_base_path: Path
    skip_na: bool
    v9_website_path: Path
    v10_website_path: Path

    def __init__(self, extension_csv_path: Path, repos_base_path: Path, v9_website_path: Path, v10_website_path: Path, skip_na: bool = True) -> None:
        self.extension_csv_path = extension_csv_path
        self.repos_base_path = repos_base_path
        self.skip_na = skip_na
        self.v9_website_path = v9_website_path
        self.v10_website_path = v10_website_path
        self.extension_list = []
        return self.read_extension_csv()

    def read_extension_csv(self) -> None:
        """
        Read the extension CSV file and populate the extension list in self.extension_list.
        """
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
        """
        Find an extension by name (case-insensitive).
        
        Args:
            name: Name of the extension to find
            
        Returns:
            ExtensionInfo if found, None otherwise
        """
        for ext in self.extension_list:
            if ext.name.lower() == name.lower():
                return ext
        return None

    def test_extensions(
        self, 
        on_output: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Test all extensions in self.extension_list
        
        Args:
            on_output: Optional callback called for each output line.
                       Signature: on_output(formatted_line: str, raw_data: dict)
                       
        Returns:
            List of result dicts for each extension
            
        TODO: Parallelize this and include easily visible progress tracking
        """
        results = []
        for extension in self.extension_list:
            result = self.test_extension(extension, on_output)
            results.append(result)
        return results

    def test_extension(
        self, 
        extension: ExtensionInfo, 
        on_output: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Testing a single extension.
        
        Args:
            extension: The extension to test
            on_output: Optional callback called for each output line.
                       Signature: on_output(formatted_line: str, raw_data: dict)
                       
        Returns:
            Result dict with success, output, error, duration_seconds, etc.
        """
        claude_prompt = self.generate_prompt(extension)
        return self.run_claude_code(claude_prompt, extension, on_output)
    
    def run_test_by_name(
        self, 
        name: str, 
        on_output: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Run a test for an extension by name.
        
        Args:
            name: Name of the extension to test (case-insensitive)
            on_output: Optional callback called for each output line.
                       Signature: on_output(formatted_line: str, raw_data: dict)
                       
        Returns:
            Result dict with success, output, error, duration_seconds, etc.
            
        Raises:
            ValueError: If extension not found
        """
        extension = self.get_extension_by_name(name)
        if not extension:
            available = [ext.name for ext in self.extension_list]
            raise ValueError(f"Extension '{name}' not found. Available: {available}")
        return self.test_extension(extension, on_output)

    def get_priority_guidance(self, priority: str) -> str:
        """
        Get the priority guidance for a given priority.
        :param priority: The priority to get the guidance for
        :return: The priority guidance
        """
        priority_guidance = {
            "Top": """This is a really really important extension. It is a CRITICAL extension. We need exhaustive coverage of absolutely everything!!! Top priority is generally for only one extension meaning it has the most issues raised in customer service as well!""",
            "High": """This is one of the most important extensions. We need thorough coverage of absolutely everything. This would mean we test things as much as practically possible!""",
            "Medium": """This is a medium priority extension. We need to test the most important features and scenarios but do not need to go deep as such, just make sure the critical things work as expected.""",
            "Low": """This is a low priority extension, just basic smoke testing to make sure the extension is working as expected is all we need to do.""",
            "N/A": """This would basically meaan that this extension should be already tested when other libraries are tested, so we don't need to test it again."""
        }
        return priority_guidance[priority]

    def generate_prompt(self, extension: ExtensionInfo) -> str:
        """
        Generate a prompt to test an extension.
        :param extension: The extension to test
        :return: The prompt to send to Claude Code
        """

        prompt = f"""I have been working on the upgrade of a private mirror of an open source application called DNN.
        The private mirror is called Evoq.
        Evoq is built in layers with multiple repos and has three tiers, Basic, Content and Social (also known as Engage).
        The first layer is Evoq.Dnn.Platform which is meant to be the copy of the community repository Dnn.Platform but has some added code into it.
        Then the second layer is Dnn.Evoq.Basic, the artifact (and built DLLs) from the first build of Evoq.Dnn.Platform and used and both added together to build Evoq Basic.
        Then the third layer is Dnn.Evoq.Content where similar to previous, artifact (and built DLLs) from Evoq Basic are added to build Evoq Content.
        Then finally the fourth layer is Dnn.Evoq.Social which is added to the artifact (and built DLLs) from the third layer to build Evoq Social.
        
        Now parallel to this there are 2 more repositories of note, Dnn.AdminExperience.Basic and Dnn.AdminExperience.Engage
        Build artifact (and built DLLs) from Dnn.AdminExperience.Basic is added in the step when building Evoq Basic and then are subsequently used for Evoq Content as well.
        Build artifact (and built DLLs) from Dnn.AdminExperience.Engage is added in the step when building Evoq Social and therefore add more functionality in Evoq Engage.
        
        Another thing is that any of the repos, build artifacts, etc. do not replace any existing functionality but rather add functionality.
        
        I am responsible for upgrading Evoq from DNN v9 to DNN v10.
        The process so far for this has been merging the v10 community repo with our private repo Evoq.Dnn.Platform
        Resolving any merge conflicts
        Run builds, resolve any errors during builds
        Resolve and CS0618 warnings, which are for usage of any deprecated code
        Run installation of all three tiers of Evoq, which is run after extracting the built .zips and extracting them into a folder which is pointed to a localhost port using IIS. Resolving any issues and running new builds if any new errors pop up.

        After we have fixed and verified everything is working fine till the installation of all three tiers of Evoq. We ran E2E testing for the DNN side of things to ensure nothing is broken there which already have a defined list of tests in a repo called e2e-tests.

        What we need to do now is to test the extensions added by Evoq.

        Please test the extension {extension.name}.

        This extension is a {extension.priority} priority extension and is of type {extension.extension_type}.

        Basically what the priority means is - {self.get_priority_guidance(extension.priority)}

        For general testing, we have the v10 website running at {self.v10_website_path}.

        You can look at basically all the code since all the repos should be available to you in the {self.repos_base_path} folder and the code for the extension is in {self.repos_base_path}/{extension.repo} directory. Look at the code, investigate the code as thoroughly as possible and regardless of the priority, making sure you have looked at all the relative code for the extension so you have all the context required to actually decide what to test and how to test it.

        Superuser Login Credentials:
        Username: {os.getenv("EVOQ_USERNAME")}
        Password: {os.getenv("EVOQ_PASSWORD")}

        Handle any unexpected popup gracefully. If possible, select the option to never show them again so it doesn't interfere else just close it.
        
        Do NOT use write and run code for using the browser AT ALL. ALWAYS use the Playwright MCP browser tools to check the website(s) functionality. (Plawright MCP Config Options - https://github.com/microsoft/playwright-mcp)

        Put the results of all the tests you ran, put them in an HTML document. No need to beautify the HTML, just format it with text for what you did, why you did it and reference the screenshots using the <img> tag. Screenshots are really important because they are proof that you ran the test and how the test was successful or failed. Please place it all inside {extension.name}_result/ folder so the HTML file is able to reference the screenshots.

        When you take screenshots, make sure you verify that the screenshot(s) actually contain the proper scenarios and can be used to determine if the test was successful or failed.

        EACH test should have AT LEAST ONE screenshot FOR EACH STEP of the test. A test becomes completely useless and invalid if it does not have at least one screenshot for each ste
        You have all the permissions completely, so you do not need to ask for any permissions.

        ULTRATHINK!!!
        """
        return prompt


    def run_claude_code(
        self,
        prompt: str,
        extension: ExtensionInfo,
        on_output: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Run Claude Code CLI in headless mode with Bedrock.
        
        Args:
            prompt: The prompt to send to Claude Code
            extension: The extension to test
            on_output: Optional callback called for each output line.
                       Signature: on_output(formatted_line: str, raw_data: dict)
                       
        Returns a dict with:
        - success: bool
        - output: str (the generated tests)
        - error: str (if any)
        - duration_seconds: float
        """

        # Create temp file for the prompt (delete=False because subprocess needs to read it)
        temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.md',
            prefix=f'claude_prompt_{extension.name}_',
            dir=self.repos_base_path,
            delete=False,
            encoding='utf-8'
        )
        complex_prompt_filename = Path(temp_file.name)
        
        try:
            # Write prompt to temp file and close it so subprocess can read
            temp_file.write(prompt)
            temp_file.close()

            simple_prompt = f"Read the file {complex_prompt_filename} in the current directory and follow the instructions in it. This file contains your complete task so please make sure you read the COMPLETE file. ULTRATHINK!!!"
            
            result = {
                "success": False,
                "output": "",
                "error": "",
                "duration_seconds": 0,
                "extension": extension.name,
                "timestamp": datetime.now().isoformat(),
                "model": BEDROCK_MODEL,
            }

            start_time = time.time()

            # Build the command - handle Windows .cmd files
            import platform
            claude_cmd = "claude"
            if platform.system() == "Windows":
                # On Windows, explicitly use .cmd extension or full path
                import shutil
                claude_path = shutil.which("claude")
                if claude_path:
                    claude_cmd = claude_path
                elif shutil.which("claude.cmd"):
                    claude_cmd = "claude.cmd"
            
            cmd = [
                claude_cmd,
                "-p", simple_prompt,
                "--model", BEDROCK_MODEL,
                "--output-format", "stream-json",
                "--verbose",  # Helps with debugging
                # "--permission-mode", "acceptEdits",
                "--dangerously-skip-permissions",
                "--allowedTools", ",".join([
                    "Read", "Grep", "Glob", "Bash",
                    "mcp__playwright__*"  # Allow all Playwright MCP tools
                ]),
            ]

            # run_yourself = " ".join(cmd)
            # print(run_yourself)
            # exit()
            
            # # Add allowed tools
            # if ALLOWED_TOOLS:
            #     cmd.extend(["--allowedTools", ",".join(ALLOWED_TOOLS)])
            
            # Build environment with Bedrock settings
            env = os.environ.copy()
            env.update(BEDROCK_ENV)
            
            # Run Claude Code
            # Use Popen to stream output in real-time
            process = subprocess.Popen(
                cmd,
                cwd=str(self.repos_base_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',  # Handle any malformed bytes gracefully
                env=env,
            )

            print(f"Running Claude Code for {extension.name} in {self.repos_base_path}")
            
            output_lines = []
            
            for line in process.stdout:
                formatted_line, raw_data = format_claude_output_line(line)
                
                # Call the streaming callback if provided
                if on_output:
                    on_output(extension, line)
                else:
                    # Default behavior: print to stdout
                    if formatted_line:
                        print(formatted_line)
                
                output_lines.append(line)
            
            # Writing complete output to a file
            output_file_path = f"claude_output_{extension.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(output_file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(output_lines))
            
            process.wait(timeout=CLAUDE_TIMEOUT)
            result["duration_seconds"] = time.time() - start_time
            result["output"] = "\n".join(output_lines)
            result["success"] = process.returncode == 0
            result["error"] = process.stderr.read()
            return result
        finally:
            # Clean up temp file even on KeyboardInterrupt or other exceptions
            if complex_prompt_filename.exists():
                complex_prompt_filename.unlink()


# if __name__ == "__main__":
#     tester = EvoqExtensionTester(
#         extension_csv_path=Path("evoq_extensions.csv"),
#         repos_base_path=Path("C:\\DNN\\Evoq.Extensions.Tester\\repos"),
#         v9_website_path=Path("http://localhost:8091"),
#         v10_website_path=Path("http://localhost:8094"),
#     )
#     tester.test_extensions()