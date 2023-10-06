#!/usr/bin/python
# -*- coding: utf-8 -*-
import dataclasses

import enumeration_expander as exp
import signature_parser as sig


@dataclasses.dataclass
class Bitwise:
    param: exp.MultiIdent
    flags: list[str]


@dataclasses.dataclass
class Function:
    function: sig.Signature
    enumerations: list[exp.ParameterEnumeration]
    associated_get: sig.AssociatedGet

    def __str__(self) -> str:
        lines = [str(self.function)]
        lines.extend(map(str, self.enumerations))
        return "\n".join(lines)


@dataclasses.dataclass
class Section:
    header: exp.SectionDeclaration
    description: list[exp.SectionDescription]
    associated_gets: sig.AssociatedGet
    functions: list[Function]

    def __str__(self) -> str:
        lines = [str(self.header)]
        lines.extend(map(str, self.description))
        lines.extend(map(str, self.functions))
        return "\n".join(lines)
