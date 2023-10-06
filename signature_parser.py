# -*- coding: utf-8 -*-

import dataclasses
import enum
import itertools as it
import re
from typing import Self, ClassVar, Pattern, Tuple

from enumeration_expander import AssembleAst, ParseAst, ParsingException, MultiIdent, ProcessedAst, Variant, \
    split_on_level


class _Qualifier(enum.Enum):
    Const = enum.auto
    Volatile = enum.auto

    def __str__(self) -> str:
        match self:
            case _Qualifier.Const:
                return "const"
            case _Qualifier.Volatile:
                return "volatile"


@dataclasses.dataclass
class Qualifier(ParseAst):
    Const: ClassVar[str] = "const"
    Volatile: ClassVar[str] = "volatile"

    def __init__(self, qualifier: _Qualifier):
        self.qualifier = qualifier

    @staticmethod
    def check(variant: str) -> bool:
        return variant in {Qualifier.Const, Qualifier.Volatile}

    @classmethod
    def parse(cls, variant: str) -> Self:
        match variant:
            case Qualifier.Const:
                return cls(_Qualifier.Const)
            case Qualifier.Volatile:
                return cls(_Qualifier.Volatile)
            case _:
                Qualifier.parsing_error(variant)

    def __str__(self) -> str:
        return str(self.qualifier)


@dataclasses.dataclass
class Pointer:
    qualifiers: list[Qualifier]

    def __str__(self) -> str:
        return "*" + " ".join(map(str, self.qualifiers))


@dataclasses.dataclass
class Declarator(ProcessedAst[list[str], list[str]]):
    # from left to right modifiers
    pointers: list[Pointer]
    ident: MultiIdent

    @staticmethod
    def check(variant: list[str]) -> list[str] | None:
        if len(variant) == 0:
            return None
        return variant

    @staticmethod
    def parse_pointers(tokens: list[str]) -> list[Pointer]:
        pointers: list[Pointer] = list()
        if len(tokens) == 0:
            return pointers
        while tokens[0] == "*":

            qualifiers = list(it.takewhile(
                lambda value: value is not None, 
                map(lambda token: Qualifier.process(variant=token), tokens[1:])
            ))
            del tokens[:len(qualifiers) + 1]
            pointers.append(Pointer(qualifiers))  # type: ignore
        return pointers

    @classmethod
    def assemble(cls, tokens: list[str]) -> Self:
        pointers = Declarator.parse_pointers(tokens)
        [ident] = tokens
        return cls(pointers, MultiIdent(ident))

    def __str__(self) -> str:
        pointers = " ".join(map(str, self.pointers)) + " " if len(self.pointers) > 0 else ""
        return pointers + self.ident.name


@dataclasses.dataclass
class Declaration(ProcessedAst[list[str], list[str]]):
    type_qualifier: Qualifier | None
    type_specifier: MultiIdent
    declarator: Declarator
    splitter: ClassVar[Pattern[str]] = re.compile(r"(\s+|\*)")

    @staticmethod
    def tokenize(code: str) -> list[str]:
        return [token for token in re.split(Declaration.splitter, code) if token.strip() != ""]

    @staticmethod
    def check(tokens: list[str]) -> list[str] | None:
        if len(tokens) > 1:
            return tokens
        return None

    @classmethod
    def assemble(cls, tokens: list[str]) -> Self:
        if type_qualifier := Qualifier.process(variant=tokens[0]):
            del tokens[:1]
        ident = MultiIdent(tokens.pop(0))
        declarator = Declarator.process(tokens)
        if declarator is None:
            Declarator.parsing_error(" ".join(tokens))
        return cls(type_qualifier, ident, declarator)

    def __str__(self) -> str:
        words = list()
        if self.type_qualifier:
            words.append(str(self.type_qualifier))
        words.append(self.type_specifier.name)
        words.append(str(self.declarator))
        return " ".join(words)


@dataclasses.dataclass
class AssociatedGet(ParseAst):
    param_name: str

    @staticmethod
    def check(line: str) -> bool:
        return line.startswith("Enable/Disable/IsEnabled")

    @classmethod
    def parse(cls, line: str) -> Self:
        return cls(line[line.find("(") + 1:line.rfind(")")])

    def __str__(self) -> str:
        return "Enable/Disable/IsEnabled({});".format(self.param_name)


@dataclasses.dataclass
class Signature(AssembleAst[Tuple[str, str]]):
    return_type_qualifier: Qualifier | None
    return_type: MultiIdent
    return_declarator: Declarator
    params: list[Variant | Declaration]

    @staticmethod
    def check(variant: str) -> Tuple[str, str] | None:
        if not variant.endswith(");"):
            return None
        opening, closing = variant.find("("), -2
        prefix = variant[:opening]
        params = variant[opening + 1: closing]
        return prefix, params

    @classmethod
    def assemble(cls, data: Tuple[str, str]) -> Self:
        prefix, params = data
        prefix_tokens = list(split_on_level(prefix, " "))
        if type_qualifier := Qualifier.process(variant=prefix_tokens[0]):
            del prefix_tokens[:1]
        ret_type = MultiIdent(prefix_tokens.pop(0))
        declarator = Declarator.process(prefix_tokens)
        if declarator is None:
            Declarator.parsing_error(" ".join(prefix_tokens))
        parsed_params = list()
        for param in params.split(","):
            param_tokens = Declaration.tokenize(param.strip())
            parsed: Declaration | Variant | None
            parsed = Declaration.process(param_tokens)
            if parsed is None:
                parsed = Variant.process(param)
            if parsed is None:
                Declaration.parsing_error(param)
            parsed_params.append(parsed)
        return cls(
            type_qualifier,
            ret_type,
            declarator,
            parsed_params
        )

    def __str__(self) -> str:
        words: list[str] = list()
        if self.return_type_qualifier:
            words.append(str(self.return_type_qualifier))
        words.append(self.return_type.name)
        words.append(str(self.return_declarator))
        words.append("(" + ", ".join(map(str, self.params)) + ");")
        return " ".join(words)
