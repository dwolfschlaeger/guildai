#!/usr/bin/env python

# Copyright 2017-2018 TensorHub, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import yaml


class Build(object):

    cache_scheme_version = 18

    name = None
    python = None
    env = None

    python_cmd = "python"
    pip_cmd = "python -m pip"

    build_dir = "build-env"
    test_dir = "test-env"
    examples_dir = "examples"

    uat_skips = {}

    cache_dep_files = [
        "requirements.txt",
        "guild/view/package.json",
    ]

    def job(self):
        assert self.env
        return {
            self.env: self.env_config(),
            "working_directory": "~/repo",
            "steps": self.steps(),
        }

    def steps(self):
        return [
            self.checkout(),
            self.restore_cache(),
            self.install_build_deps(),
            self.save_cache(),
            self.build(),
            self.install_dist(),
            self.test(),
            self.store_artifacts(),
            self.upload_to_pypi(),
        ]

    @staticmethod
    def checkout():
        return "checkout"

    def restore_cache(self):
        return {"restore_cache": {"keys": [self._cache_key()]}}

    def _cache_key(self):
        assert self.name
        checksums = "-".join(
            ["{{ checksum \"%s\" }}" % path for path in self.cache_dep_files]
        )
        return "%s-%i-%s" % (self.name, self.cache_scheme_version, checksums)

    def install_build_deps(self):
        return self._run("Install build dependencies", self._install_build_deps_cmd())

    def _install_build_deps_cmd(self):
        return [
            self._upgrade_pip(),
            self._ensure_virtual_env_cmd(),
            self._init_env(self.build_dir),
            self._activate_env(self.build_dir),
            self._install_guild_reqs(self.build_dir),
            self._install_guild_view_reqs(),
        ]

    def _pip_install(self, pkgs, sudo=False, venv=None):
        sudo_part = "sudo -H " if sudo else ""
        # pipe to cat effectively disables progress bar
        pkgs_part = " ".join([self._pkg_spec(pkg) for pkg in pkgs])
        pip_cmd = self.pip_cmd if not venv else "%s/bin/pip" % venv
        return "{sudo}{pip} install --upgrade {pkgs} | cat".format(
            sudo=sudo_part, pip=pip_cmd, pkgs=pkgs_part
        )

    @staticmethod
    def _pkg_spec(pkg):
        if pkg.endswith(".txt"):
            return "-r {}".format(pkg)
        return pkg

    def _upgrade_pip(self):
        return self._pip_install(["pip"], sudo=True)

    def _ensure_virtual_env_cmd(self):
        return self._pip_install(["virtualenv"], sudo=True)

    def _init_env(self, path):
        return "rm -rf {path} && {venv_init}".format(
            path=path, venv_init=self._venv_init_cmd(path)
        )

    def _venv_init_cmd(self, path):
        return "%s -m virtualenv %s" % (self.python_cmd, path)

    @staticmethod
    def _activate_env(path):
        return ". %s/bin/activate" % path

    def _install_guild_reqs(self, venv):
        return self._pip_install(["requirements.txt"], venv=venv)

    @staticmethod
    def _install_guild_view_reqs():
        return "cd guild/view && npm install"

    def save_cache(self):
        return {"save_cache": {"paths": [self.build_dir], "key": self._cache_key()}}

    def build(self):
        return self._run(
            "Build",
            [
                ". %s/bin/activate" % self.build_dir,
                self._bdist_wheel_cmd(),
            ],
        )

    def _bdist_wheel_cmd(self):
        return "%s setup.py bdist_wheel" % self.python_cmd

    def install_dist(self):
        return self._run("Install dist", [self._pip_install(["dist/*.whl"], sudo=True)])

    def test(self):
        return self._run(
            "Test",
            [
                (
                    "guild init -y"
                    " --no-progress"
                    " --name guild-test"
                    " --no-reqs"
                    " --guild dist/*.whl {}".format(self.test_dir)
                ),
                "TERM=xterm-256color source guild-env {}".format(self.test_dir),
                "guild check -v --offline",
                (
                    "WORKSPACE={workspace} "
                    "UAT_SKIP={uat_skip},remote-*,hiplot-* "
                    "COLUMNS=999 "
                    "EXAMPLES={examples} "
                    "guild check --uat".format(
                        workspace=self.test_dir,
                        examples=self.examples_dir,
                        uat_skip=",".join(self.uat_skip),
                    )
                ),
            ],
        )

    @staticmethod
    def store_artifacts():
        return {"store_artifacts": {"path": "dist", "destination": "dist"}}

    def upload_to_pypi(self):
        return self._run(
            "Upload to PyPI",
            [
                self._activate_env(self.build_dir),
                self._pip_install(["twine"]),
                "twine upload --skip-existing dist/*.whl",
            ],
        )

    @staticmethod
    def _run(name, cmd_lines):
        return {
            "run": {
                "name": name,
                "command": "\n".join(cmd_lines),
                "no_output_timeout": 1800,
            }
        }

    def workflow_job(self):
        return {
            self.name: {"filters": {"branches": {"only": ["release", "pre-release"]}}}
        }


# Skip tests related to TensorFlow. Apply these skips on targets where
# the required version of TensorFlow because isn't available.
#
TENSORFLOW_UAT_SKIP = [
    "*keras*",
    "*logreg*",
    "*mnist*",
    "*tensorflow*",
    "simple-example",
    "test-flags",  # uses get-started example which requires Keras
]


class LinuxBuild(Build):

    env = "docker"

    images = {
        "linux-python_2.7": "circleci/python:2.7-stretch-node",
        "linux-python_3.5": "circleci/python:3.5-stretch-node",
        "linux-python_3.6": "circleci/python:3.6-stretch-node",
        "linux-python_3.7": "circleci/python:3.7-stretch-node",
        "linux-python_3.8": "circleci/python:3.8.1-node",
    }

    uat_skips = {"3.8": TENSORFLOW_UAT_SKIP}

    def __init__(self, python):
        self.python = python
        self.name = "linux-python_%s" % python
        self.uat_skip = self.uat_skips.get(python) or []

    def env_config(self):
        return [{"image": self.images[self.name]}]

    def _bdist_wheel_cmd(self):
        return "%s setup.py bdist_wheel -p manylinux1_x86_64" % self.python_cmd


class MacBuild(Build):

    cache_scheme_version = 19

    env = "macos"

    xcode_versions = {
        "10.14": "11.1.0",
        "10.15": "11.2.1",
    }

    pyenv_versions = {
        "3.6": "3.6.11",
        "3.7": "3.7.9",
        "3.8": "3.8.6",
    }

    python_cmds = {
        "2.7": "python2",
        "3.6": "~/.pyenv/versions/3.6.11/bin/python",
        "3.7": "~/.pyenv/versions/3.7.9/bin/python",
        "3.8": "~/.pyenv/versions/3.8.6/bin/python",
    }

    pip_cmds = {
        "2.7": "python2 -m pip",
        "3.6": "~/.pyenv/versions/3.6.11/bin/python -m pip",
        "3.7": "~/.pyenv/versions/3.7.9/bin/python -m pip",
        "3.8": "~/.pyenv/versions/3.8.6/bin/python -m pip",
    }

    ##uat_skips = {"3.8": TENSORFLOW_UAT_SKIP}

    def __init__(self, os_version, python):
        self.xcode_version = self.xcode_versions[os_version]
        self.python = python
        self.name = "macos_%s-python_%s" % (os_version, python)
        self.python_cmd = self.python_cmds.get(self.python, self.python_cmd)
        self.pip_cmd = self.pip_cmds.get(self.python, self.pip_cmd)
        self.uat_skip = self.uat_skips.get(python) or []

    def env_config(self):
        return {"xcode": self.xcode_version}

    def _install_build_deps_cmd(self):
        default_lines = super(MacBuild, self)._install_build_deps_cmd()
        mac_lines = []
        mac_lines.extend(self._python_install_cmd())
        return mac_lines + default_lines

    def _ensure_virtual_env_cmd(self):
        # Workaround issue with Python 2.7 virtualenv 20.x, which
        # doesn't isolate environments from system packages.
        if self.python == "2.7":
            return self._pip_install(["virtualenv==16.7.9"], sudo=True)
        return super(MacBuild, self)._ensure_virtual_env_cmd()

    def _python_install_cmd(self):
        if self.python == "2.7":
            # 2.7 is default on OSX
            return []
        pyenv_ver = self.pyenv_versions[self.python]
        return [
            "brew install pyenv",
            "pyenv install %s" % pyenv_ver,
        ]


class Config(object):

    version = 2

    def __init__(self, builds):
        self.builds = builds

    def write(self):
        config = {"version": 2, "jobs": self._jobs(), "workflows": self._workflows()}
        with open("config.yml", "w") as out:
            yaml.dump(config, out, default_flow_style=False, width=9999)

    def _jobs(self):
        return {build.name: build.job() for build in self.builds}

    def _workflows(self):
        return {
            "version": self.version,
            "all": {"jobs": [build.workflow_job() for build in self.builds]},
        }


builds = [
    # LinuxBuild(python="2.7"),
    # LinuxBuild(python="3.5"),
    # LinuxBuild(python="3.6"),
    # LinuxBuild(python="3.7"),
    # LinuxBuild(python="3.8"),
    # MacBuild("10.14", python="2.7"),
    # MacBuild("10.15", python="2.7"),
    # MacBuild("10.14", python="3.6"),
    MacBuild("10.15", python="3.6"),
    # MacBuild("10.14", python="3.7"),
    MacBuild("10.15", python="3.7"),
    # MacBuild("10.14", python="3.8"),
    MacBuild("10.15", python="3.8"),
]


def main():
    config = Config(builds)
    config.write()


if __name__ == "__main__":
    main()
