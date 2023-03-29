import sys
from pathlib import Path
from typing import List, Sequence

from trunner.config import ConfigParser
from trunner.harness import HarnessError, FlashError
from trunner.text import bold, green, red, yellow
from trunner.types import Status, TestOptions, TestResult


def _add_tests_module_to_syspath(project_path: Path):
    # Add phoenix-rtos-tests to python path to make sure that module is visible for tests, whenever they are
    sys.path.insert(0, str(project_path / Path("phoenix-rtos-tests")))


def resolve_project_path():
    file_path = Path(__file__).resolve()
    # file_path is phoenix-rtos-project/phoenix-rtos-tests/trunner/test_runner.py
    project_dir = file_path.parent.parent.parent
    return project_dir


class TestRunner:
    """Class responsible for loading, building and running tests"""

    def __init__(self, ctx, test_paths):
        self.ctx = ctx
        self.target = self.ctx.target
        self.test_configs = []
        self.test_paths = test_paths

    def search_for_tests(self) -> List[Path]:
        """Returns test*.yaml files that are searched in directories given in test_paths attribute."""

        paths = []
        for path in self.test_paths:
            yamls = []

            if path.is_dir():
                yamls = list(path.rglob("test*.yaml")) + list(path.rglob("test*.yml"))
                if not yamls:
                    raise ValueError(f"{path} does not contain .yaml test configuration")
            elif path.is_file():
                if path.suffix != ".yaml" and path.suffix != ".yml":
                    raise ValueError("Test configuration must be a file with .yaml or .yml extension")

                yamls = [path]
            else:
                raise ValueError(f"Test configuration {path} is neither a directory nor a file.")

            paths.extend(yamls)

        return paths

    def parse_tests(self) -> Sequence[TestOptions]:
        """Returns test options that can be used to build test harness."""

        test_yamls = self.search_for_tests()
        parser = ConfigParser(self.ctx)

        tests = []
        for path in test_yamls:
            tests.extend(parser.parse(path))

        return tests

    def flash(self):
        """Flashes the device under test."""

        print("Flashing an image to device...")

        try:
            self.target.flash_dut()
        except (FlashError, HarnessError) as e:
            print(bold("ERROR WHILE FLASHING THE DEVICE"))
            print(e)
            sys.exit(1)

        print("Done!")

    def run_tests(self, tests: Sequence[TestOptions]):
        """It builds and runs tests based on given test options.

        For each test description in tests this method builds the test, runs it and prints the result.
        Additionally, reboot strategy is chosen based on the result of previous executed tests.

        Arguments:
            tests: Sequence of test options that describe how test looks like.
        """

        fail, skip = 0, 0

        for idx, test in enumerate(tests):
            result = TestResult(test.name)
            print(f"{result.get_name()}: ", end="", flush=True)

            if test.ignore:
                result.skip()
            else:
                harness = self.target.build_test(test)
                assert harness is not None

                try:
                    result = harness()
                except HarnessError as e:
                    result.fail(str(e))

                if result is None:
                    # Returned type of harness is None, reinit result with default
                    result = TestResult(test.name, status=Status.OK)

            print(result, end="", flush=True)

            if result.is_fail():
                fail += 1
            elif result.is_skip():
                skip += 1

            def set_reboot_flag(tests, idx, result):
                # If the test is successful and the next test doesn't require loading via
                # the plo we don't want to reboot the entire device (to speed up the test execution).
                # There are three exceptions to this rule:
                # 1. Runner runs in the "nightly" mode when we are not concerned about slow execution.
                # 2. The test has failed.
                # 3. We have to enter the bootloader in order to load applications.
                if idx == len(tests) - 1:
                    return

                tests[idx + 1].should_reboot = False

                if result.is_skip():
                    tests[idx + 1].should_reboot = tests[idx].should_reboot

                if (
                    result.is_fail()
                    or self.ctx.nightly
                    or (tests[idx + 1].bootloader is not None and tests[idx + 1].bootloader.apps)
                ):
                    tests[idx + 1].should_reboot = True

            set_reboot_flag(tests, idx, result)

        return fail, skip

    def run(self) -> bool:
        """Runs the entire test campaign based on yamls given in test_paths attribute.

        Returns true if there are no failed tests.
        """

        tests = self.parse_tests()

        if self.ctx.should_flash:
            self.flash()

        if not self.ctx.should_test:
            return True

        _add_tests_module_to_syspath(self.ctx.project_path)

        fails, skips = self.run_tests(tests)
        passes = len(tests) - fails - skips

        print(f"TESTS: {len(tests)} {green('PASSED')}: {passes} {red('FAILED')}: {fails} {yellow('SKIPPED')}: {skips}")

        return fails == 0
