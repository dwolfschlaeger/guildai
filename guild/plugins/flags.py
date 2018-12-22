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

from __future__ import absolute_import
from __future__ import division

import hashlib
import imp
import json
import os
import subprocess
import sys

from guild import cli
from guild import op_util
from guild import util
from guild import var

from guild.plugin import Plugin

class DataLoadError(Exception):
    pass

class FlagsPlugin(Plugin):

    def guildfile_data(self, data, _src):
        local_cache = {}
        for op_data in self._iter_ops_with_flags(data):
            try:
                flags_import = op_data["flags"].pop("$import")
            except KeyError:
                continue
            else:
                self._try_apply_imports(flags_import, op_data, local_cache)

    def _iter_ops_with_flags(self, data):
        if not isinstance(data, list):
            data = [data]
        for top_level in data:
            for op_data in self._iter_ops_with_flags_recurse(top_level):
                yield op_data

    def _iter_ops_with_flags_recurse(self, data):
        if isinstance(data, dict):
            for name, val in sorted(data.items()):
                if name == "operations" and isinstance(val, dict):
                    for _, op_data in sorted(val.items()):
                        if isinstance(op_data, dict) and "flags" in op_data:
                            yield op_data
                else:
                    for op_data in self._iter_ops_with_flags_recurse(val):
                        yield op_data

    def _try_apply_imports(self, flags_import, op_data, local_cache):
        import_data = self._import_data(flags_import, op_data, local_cache)
        if import_data:
            self._apply_import_data(import_data, op_data)

    def _import_data(self, imports, op_data, local_cache):
        main_mod = op_util.split_main(op_data.get("main"))[0]
        try:
            flags_data = local_cache[main_mod]
        except KeyError:
            flags_data = self._flags_data(main_mod)
            local_cache[main_mod] = flags_data
        return self._filter_flags(flags_data, imports)

    def _flags_data(self, main_mod):
        try:
            sys_path, mod_path = self._find_module(main_mod)
        except ImportError as e:
            self.log.warning(
                "cannot import flags from %s: %s",
                main_mod, e)
            return {}
        else:
            return self._flags_data_for_path(mod_path, sys_path)

    def _flags_data_for_path(self, mod_path, sys_path):
        data, cached_data_path = self._cached_data(mod_path)
        if data is not None:
            return data
        if os.getenv("NO_IMPORT_FLAGS_PROGRESS") != "1":
            cli.note_once("Refreshing project info...")
        try:
            data = self._load_flags_data(mod_path, sys_path)
        except DataLoadError:
            return {}
        else:
            self._cache_data(data, cached_data_path)
            return data

    def _find_module(self, main_mod):
        main_mod_sys_path, module = self._split_module(main_mod)
        # Copied from guild.op_main
        parts = module.split(".")
        module_path = parts[0:-1]
        module_name_part = parts[-1]
        for sys_path_item in [main_mod_sys_path] + sys.path:
            cur_path = os.path.join(sys_path_item, *module_path)
            try:
                mod_info = imp.find_module(module_name_part, [cur_path])
            except ImportError:
                pass
            else:
                _f, found_path, _desc = mod_info
                return main_mod_sys_path, found_path
        raise ImportError("No module named %s" % main_mod)

    @staticmethod
    def _split_module(main_mod):
        parts = main_mod.rsplit("/", 1)
        if len(parts) == 1:
            return ".", parts[0]
        return parts

    def _cached_data(self, mod_path):
        cached_path = self._cached_data_path(mod_path)
        if self._cache_valid(cached_path, mod_path):
            with open(cached_path, "r") as f:
                return json.load(f), cached_path
        return None, cached_path

    @staticmethod
    def _cached_data_path(mod_path):
        cache_dir = var.cache_dir("import-flags")
        abs_path = os.path.abspath(mod_path)
        path_hash = hashlib.md5(abs_path.encode()).hexdigest()
        return os.path.join(cache_dir, path_hash)

    @staticmethod
    def _cache_valid(cache_path, mod_path):
        if not os.path.exists(cache_path):
            return False
        return os.path.getmtime(mod_path) <= os.path.getmtime(cache_path)

    @staticmethod
    def _cache_data(data, path):
        util.ensure_dir(os.path.dirname(path))
        with open(path, "w") as f:
            json.dump(data, f)

    def _load_flags_data(self, mod_path, sys_path):
        env = {
            "PYTHONPATH": os.path.pathsep.join([sys_path] + sys.path),
            "LOG_LEVEL": str(self.log.getEffectiveLevel()),
        }
        with util.TempFile() as data_path:
            cmd = [
                sys.executable,
                "-m", "guild.plugins.import_flags_main",
                mod_path, data_path]
            self.log.debug("import_flags_main env: %s", env)
            self.log.debug("import_flags_main cmd: %s", cmd)
            try:
                out = subprocess.check_output(
                    cmd, stderr=subprocess.STDOUT, env=env)
            except subprocess.CalledProcessError as e:
                self.log.warning(
                    "cannot import flags from %s: %s",
                    mod_path, e.output.decode().strip())
                raise DataLoadError()
            else:
                self.log.debug("import_flags_main output: %s", out)
                return self._load_data(data_path)

    @staticmethod
    def _load_data(path):
        out = open(path, "r").read().strip()
        if not out:
            return {}
        return json.loads(out)

    @staticmethod
    def _filter_flags(data, imports):
        return {
            name: data[name] for name in data if name in imports
        }

    def _apply_import_data(self, flag_import_data, op_data):
        for flag_name, flag_data in flag_import_data.items():
            op_flags = op_data["flags"]
            try:
                op_flag_data = op_flags[flag_name]
            except KeyError:
                op_flags[flag_name] = flag_data
            else:
                if not isinstance(op_flag_data, dict):
                    # Coerce default value to full data
                    op_flag_data = {"default": op_flag_data}
                    op_flags[flag_name] = op_flag_data
                self._apply_import_flag(flag_data, op_flag_data)

    @staticmethod
    def _coerce_flag_data(data):
        if isinstance(data, dict):
            return data
        return {"default": data}

    @staticmethod
    def _apply_import_flag(flag_import_data, op_flag_data):
        for name, val in flag_import_data.items():
            if name not in op_flag_data:
                op_flag_data[name] = val
