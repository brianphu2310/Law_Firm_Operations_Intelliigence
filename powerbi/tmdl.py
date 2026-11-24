"""Small writers for TMDL (the text format of a Power BI semantic model). Only what this project needs."""
from __future__ import annotations

import uuid

NS = uuid.UUID("6b3c2f1e-8a4d-4c7b-9a51-2f0d6c1e7b42")


def guid(*parts):
    return str(uuid.uuid5(NS, "/".join(map(str, parts))))


def q(name):
    """Quote a TMDL object name when it is not a plain identifier."""
    if name.replace("_", "").isalnum() and not name[0].isdigit():
        return name
    return "'" + name.replace("'", "''") + "'"


def indent(text, tabs):
    pad = "\t" * tabs
    return "\n".join(pad + line if line.strip() else pad for line in text.splitlines())


class Column:
    def __init__(self, name, data_type, source=None, fmt=None, hidden=False, summarize="none", is_key=False, sort_by=None,
                 expression=None, description=None, calc_source=None, category=None):
        self.name, self.data_type, self.source, self.fmt = name, data_type, source if source is not None else name, fmt
        self.hidden, self.summarize, self.is_key, self.sort_by = hidden, summarize, is_key, sort_by
        self.expression, self.description, self.calc_source, self.category = expression, description, calc_source, category

    def render(self):
        out = []
        if self.description:
            out.append(f"\t/// {self.description}")
        if self.expression:                                   # calculated column
            out.append(f"\tcolumn {q(self.name)} = {self.expression}")
        else:
            out.append(f"\tcolumn {q(self.name)}")
        out.append(f"\t\tdataType: {self.data_type}")
        if self.hidden:
            out.append("\t\tisHidden")
        if self.is_key:
            out.append("\t\tisKey")
        if self.fmt:
            out.append(f"\t\tformatString: {self.fmt}")
        if self.category:
            out.append(f"\t\tdataCategory: {self.category}")
        out.append(f"\t\tsummarizeBy: {self.summarize}")
        if not self.expression:
            if self.calc_source:
                if self.calc_source == self.name:
                    out.append("\t\tisNameInferred")
                out.append(f"\t\tsourceColumn: [{self.calc_source}]")
            else:
                out.append(f"\t\tsourceColumn: {self.source}")
        if self.sort_by:
            out.append(f"\t\tsortByColumn: {q(self.sort_by)}")
        return "\n".join(out)


class Measure:
    def __init__(self, name, expression, fmt=None, folder=None, hidden=False, description=None):
        self.name, self.expression, self.fmt, self.folder, self.hidden, self.description = name, expression.strip(), fmt, folder, hidden, description

    def render(self):
        out = []
        if self.description:
            out.append(f"\t/// {self.description}")
        lines = self.expression.splitlines()
        if len(lines) == 1:
            out.append(f"\tmeasure {q(self.name)} = {lines[0]}")
        else:
            out.append(f"\tmeasure {q(self.name)} =")
            out.append(indent(self.expression, 3))
        if self.fmt:
            out.append(f"\t\tformatString: {self.fmt}")
        if self.hidden:
            out.append("\t\tisHidden")
        if self.folder:
            out.append(f"\t\tdisplayFolder: {self.folder}")
        return "\n".join(out)


class Table:
    def __init__(self, name, columns, partition_kind, source, hidden=False, description=None, data_category=None):
        self.name, self.columns, self.kind, self.source = name, columns, partition_kind, source
        self.measures: list[Measure] = []
        self.hidden, self.description, self.data_category = hidden, description, data_category

    def render(self):
        out = []
        if self.description:
            out.append(f"/// {self.description}")
        out.append(f"table {q(self.name)}")
        if self.hidden:
            out.append("\tisHidden")
        if self.data_category:
            out.append(f"\tdataCategory: {self.data_category}")
        out.append("")
        for m in self.measures:
            out.append(m.render())
            out.append("")
        for c in self.columns:
            out.append(c.render())
            out.append("")
        out.append(f"\tpartition {q(self.name)} = {self.kind}")
        out.append("\t\tmode: import")
        out.append("\t\tsource =")
        out.append(indent(self.source, 4))
        out.append("")
        return "\n".join(out)


def relationship(from_table, from_col, to_table, to_col, active=True):
    out = [f"relationship {guid('rel', from_table, from_col, to_table, to_col)}"]
    if not active:
        out.append("\tisActive: false")
    out.append(f"\tfromColumn: {q(from_table)}.{q(from_col)}")
    out.append(f"\ttoColumn: {q(to_table)}.{q(to_col)}")
    return "\n".join(out)
