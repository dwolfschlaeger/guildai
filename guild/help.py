# Copyright 2017 TensorHub, Inc.
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

import os
import textwrap

import click

class ConsoleFormatter(click.HelpFormatter):

    _in_section = False

    def start_section(self, val):
        if self._in_section:
            self.dedent()
            self.dedent()
            self.write_paragraph()
        self.write_text(click.style(val, bold=True))
        self.write_paragraph()
        self.indent()
        self.indent()
        self._in_section = True

    def write_heading(self, val):
        self.write_text(click.style(val, bold=True))

    def write_subheading(self, val):
        self.write_text("%s:" % val)

    def write_description(self, val):
        self.write_text(val)

class RestFormatter(click.HelpFormatter):

    _in_section = False

    def start_section(self, val):
        if self._in_section:
            self.write_paragraph()
        self.write_text(val)
        self.write_text("=" * len(val))
        self.write_paragraph()
        self._in_section = True

    def write_heading(self, val):
        self.write_text(val)
        self.write_text("-" * len(val))

    def write_subheading(self, val):
        self.write_text(val)
        self.write_text("`" * len(val))

    def write_description(self, val):
        self.write_text("*%s*" % val)

    def write_dl(self, rows, _col_max=None, _col_spacing=None):
        for i, (name, desc) in enumerate(rows):
            if i > 0:
                self.write_paragraph()
            self.write_text("**%s**" % name)
            super(RestFormatter, self).indent()
            self.write_text("*%s*" % desc)
            super(RestFormatter, self).dedent()

    def indent(self):
        pass

    def dedent(self):
        pass

def modelfile_console_help(modelfile, refs):
    out = ConsoleFormatter()
    out.start_section("OVERVIEW")
    _write_console_help_overview(modelfile, out)
    out.start_section("MODELS")
    _write_models(modelfile, out)
    out.start_section("REFERENCES")
    _write_references(refs, out)
    return "".join(out.buffer)

def _write_console_help_overview(modelfile, out):
    out.write_text(textwrap.dedent(
        """

        You are viewing help models defined in %s.

        To run an operation, use 'guild run MODEL:OPERATION' where
        MODEL is one of the model names listed below and OPERATION is
        an associated operation.

        You may set operation flags using 'FLAG=VALUE' arguments to
        the run command.

        For more help, try 'guild run --help' or 'guild --help'.

        """
        % _format_modelfile_src(modelfile.src)))

def _format_modelfile_src(path):
    relpath = os.path.relpath(path)
    if relpath[0] != '.':
        relpath = os.path.join(".", relpath)
    return relpath

def package_description(modelfile, refs):
    out = RestFormatter()
    out.start_section("Models")
    _write_models(modelfile, out)
    out.start_section("References")
    _write_references(refs or [], out)
    return "".join(out.buffer)

def _write_models(modelfile, out):
    i = 0
    for model in modelfile:
        if model.visibility != "public":
            continue
        if i > 0:
            out.write_paragraph()
        _write_model(model, out)
        i += 1

def _write_model(m, out):
    out.write_heading(m.name)
    out.indent()
    if m.description:
        out.write_paragraph()
        out.write_description(m.description)
    out.write_paragraph()
    _write_operations(m, out)
    out.write_paragraph()
    _write_flags(m, out)
    out.dedent()

def _write_operations(m, out):
    out.write_subheading("Operations")
    out.write_paragraph()
    out.indent()
    if m.operations:
        out.write_dl([
            (op.name, op.description or "")
            for op in m.operations])
    else:
        out.write_text("There are no operations defined for this model.")
    out.dedent()

def _write_flags(m, out):
    out.write_subheading("Flags")
    out.write_paragraph()
    out.indent()
    if m.flags:
        out.write_dl([
            (name, _flag_desc(flag))
            for name, flag in m.flags.items()])
    else:
        out.write_text("There are no flags defined for this model.")
    out.dedent()

def _flag_desc(flag):
    desc = flag.description or ""
    if flag.value is None:
        return desc
    else:
        return "%s (default is %s)" % (desc, flag.value)

def _write_references(refs, out):
    for i, (name, val) in enumerate(refs):
        if i > 0:
            out.write_paragraph()
        out.write_text("%s: %s" % (name, val))
