# -*- coding: utf-8 -*-
import abc
import dataclasses
import re
import logging
from itertools import chain, pairwise, product, zip_longest, takewhile, islice
from typing import Iterable, Iterator, Tuple, TypeVar, Callable, Self, Generic, Pattern, ClassVar, Never

logging.basicConfig(
    filename='parsing.log',
    filemode='w',
    encoding='utf-8',
    level=logging.DEBUG,
    format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S'
)

T = TypeVar('T')


# def variant_processor(func):
#     def logged(*args, **kwargs) -> Ast:
#         result = func(*args, **kwargs)
#         logging.debug(f"variant: '{kwargs['variant']}', {func.__name__}: {result}")
#         return result
#
#     return logged


def chars(c1, c2):
    """Generates the characters from `c1` to `c2`, inclusive."""
    for c in range(ord(c1), ord(c2) + 1):
        yield chr(c)


class All:
    variants: Iterator[str]

    def __init__(self, variants: Iterator[str]):
        self.variants = variants

    def __iter__(self) -> Iterator[str]:
        return self.variants

    def __next__(self) -> str:
        return next(self.variants)


class Option:
    variants: Iterator[str]

    def __init__(self, variants: Iterator[str]):
        self.variants = chain([""], variants)

    def __iter__(self) -> Iterator[str]:
        return self.variants

    def __next__(self) -> str:
        return next(self.variants)


SEPARATOR_TOKEN_PAIRS: dict[str, str] = {"{": "}", "[": "]"}
SEPARATOR_ITER: dict[str, Callable[[Iterator[str]], Iterator[str]]] = {"{": All, "[": Option}
START_TOKENS: list[str] = list(SEPARATOR_TOKEN_PAIRS.keys())
END_TOKENS: list[str] = list(SEPARATOR_TOKEN_PAIRS.values())
ALL_TOKENS: list[str] = START_TOKENS + END_TOKENS


# ====================================================================================#
#                                Iterator Adapters                                    #
# ====================================================================================#


def flatten(it: Iterator[Iterator[T]]) -> Iterator[T]:
    return (t for inner in it for t in inner)


def interleave(*iters: Iterator[Iterator[T]]) -> Iterator[T]:
    return takewhile(
        lambda val: val is not None,
        (val for tup in zip_longest(*iters, fillvalue=None) for val in tup)  # type: ignore
    )


# ====================================================================================#
#                                Enumeration Parsing                                  #
# ====================================================================================#


def sep_matches(lhs: str, rhs: str) -> bool:
    return lhs == rhs


def sep_rmatches(lhs: str, rhs: str) -> bool:
    return SEPARATOR_TOKEN_PAIRS[lhs] == rhs


def variant_enumeration_ranges(variant: str) -> Iterator[Tuple[int, int]]:
    """Iterator over tuples representing substring ranges that contain enumerations.
    Indices returned are the positions of leading and trailing separator tokens.
    """
    start = 0
    depth = 0
    start_sep = None
    letters = (char for char in variant)

    for (index, sep) in filter(lambda index_char: index_char[1] in ALL_TOKENS, enumerate(letters)):
        if sep in START_TOKENS:
            if depth == 0:
                start = index
                start_sep = sep
            depth += 1
        if sep in END_TOKENS:
            depth -= 1
        if sep_rmatches(start_sep, sep) and depth == 0:  # type: ignore
            yield start, index


def invert_variant_enumeration_ranges(variant: str, ranges: Iterator[Tuple[int, int]]) -> Iterator[Tuple[int, int]]:
    """Invert enumeration ranges to find static parts of variant."""
    return ((end + 1, start) for end, start in islice(
        pairwise(chain([-1], flatten(ranges), [len(variant)])),  # type: ignore
        0, None, 2
    ))


def variant_enumerations(variant: str) -> Iterator[str]:
    """Find substrings of given variant that represent enumerations."""
    return (variant[range_[0]:range_[1] + 1] for range_ in variant_enumeration_ranges(variant))


def invert_variant_enumerations(variant: str) -> Iterator[str]:
    """Find substrings of given variant that represent static parts."""
    return (variant[range_[0]:range_[1]] for range_ in
            invert_variant_enumeration_ranges(variant, variant_enumeration_ranges(variant)))


# ====================================================================================#
#                                Enumeration Expansion                                #
# ====================================================================================#


def split_on_level(
        data: str,
        sep: str = ",",
        indents: dict[str, str] | None = None
) -> Iterable[str]:
    if indents is None:
        indents = SEPARATOR_TOKEN_PAIRS
    start = 0
    depth = 0
    for index, char in enumerate(data):
        if char in indents.keys():
            depth += 1
        if char in indents.values():
            depth -= 1
        if depth == 0 and char == sep:
            yield data[start: index]
            start = index + 1
    yield data[start:]


def enumeration_variants(enumeration: str) -> Iterator[str]:
    """Iterator over variants of given string representation of an enumeration.
    Enumeration is expected to contain both leading and trailing separators.
    """
    assert (enumeration[0] in START_TOKENS)
    assert (enumeration.count(enumeration[0]) == enumeration.count(SEPARATOR_TOKEN_PAIRS[enumeration[0]]))
    it = SEPARATOR_ITER[enumeration[0]]
    return it(flatten(expand_variant(sub_variant.strip()) for sub_variant in split_on_level(enumeration[1:-1])))


def expand_variant(variant: str) -> Iterator[str]:
    """Expand variant """
    enumerations = variant_enumerations(variant)
    expended_enumerations = list(product(*(enumeration_variants(enum) for enum in enumerations)))
    static_variant_parts = list(invert_variant_enumerations(variant))

    for expanded_sub_variants in expended_enumerations:
        yield "".join(interleave(static_variant_parts, expanded_sub_variants))  # type: ignore


class PatternMatcher:
    section_regex = re.compile(r"\[\d+(.(\d+|\d+-\d+))*]")
    variant_letter_set: set[str] = {letter for letter in flatten([chars('A', 'Z'), '_, ', ALL_TOKENS])}  # type: ignore

    @staticmethod
    def is_table_delegation(variant: str) -> bool:
        return variant.startswith("[See Table") or variant.startswith("[Table")

    @staticmethod
    def is_see_delegation(variant: str) -> bool:
        return variant.startswith("See")

    @staticmethod
    def is_lod_level(variant: str) -> bool:
        return variant == "LOD level"

    @staticmethod
    def is_enumeration(variant: str) -> bool:
        return all(letter in PatternMatcher.variant_letter_set for letter in variant)


@dataclasses.dataclass
class MultiIdent:
    name: str

    @staticmethod
    def _enumeration_variants(variant: str):
        yield from variant.split(" ") if " " in variant else variant

    def idents(self) -> Iterator[str]:
        """
        Examples:
        - void VertexAttrib{1234}{s f d}(uint index, T values);
          If space then yield by space
          if no space then yield without space
        :return:
        """
        expended_enumerations = product(*(MultiIdent._enumeration_variants(enum[1:-1])
                                          for enum in variant_enumerations(self.name)))
        static_variant_parts = list(invert_variant_enumerations(self.name))
        for expanded_sub_variants in expended_enumerations:
            yield "".join(interleave(static_variant_parts, expanded_sub_variants))  # type: ignore


class ParsingException(Exception):
    def __init__(self, node_type: type, content: str, note: str = "", *args):
        super().__init__(*args)
        self.content = content
        self.node_type = re.sub(r'(?<!^)(?=[A-Z])', ' ', node_type.__name__).lower()
        self.note = note

    def __str__(self) -> str:
        message = "expected {}, found: '{}'".format(self.node_type, self.content)
        if self.note != "":
            message + ". note: {}".format(self.note)
        return message


class Ast(abc.ABC, Generic[T]):
    @classmethod
    @abc.abstractmethod
    def process(cls, variant: T) -> Self | None:
        ...

    @abc.abstractmethod
    def __str__(self) -> str:
        ...

    @classmethod
    def parsing_error(cls, cause: str, note: str = "") -> Never:
        raise ParsingException(cls, cause, note)


class ParseAst(Ast[str]):
    @staticmethod
    @abc.abstractmethod
    def check(variant) -> bool:
        ...

    @classmethod
    @abc.abstractmethod
    def parse(cls, variant: str) -> Self:
        ...

    @classmethod
    def process(cls, variant: str) -> Self | None:
        is_valid = cls.check(variant)
        if is_valid:
            return cls.parse(variant)
        else:
            return None


IR = TypeVar("IR")


class AssembleAst(Ast[str], Generic[IR]):
    @staticmethod
    @abc.abstractmethod
    def check(variant: str) -> IR | None:
        ...

    @classmethod
    @abc.abstractmethod
    def assemble(cls, data: IR) -> Self:
        ...

    @classmethod
    def process(cls, variant: str) -> Self | None:
        ir = cls.check(variant)
        if ir is not None:
            return cls.assemble(ir)
        else:
            return None


IF = TypeVar("IF")


class ProcessedAst(Ast, Generic[IF, IR]):
    @staticmethod
    @abc.abstractmethod
    def check(variant: IF) -> IR | None:
        ...

    @classmethod
    @abc.abstractmethod
    def assemble(cls, data: IR) -> Self:
        ...

    @classmethod
    def process(cls, variant: IF) -> Self | None:
        ir = cls.check(variant)
        if ir is not None:
            return cls.assemble(ir)
        else:
            return None


@dataclasses.dataclass
class SeeDelegation(AssembleAst[list[str]]):
    multi_ident: MultiIdent

    @staticmethod
    def check(variant: str):
        tokens = variant.split(" ")
        if len(tokens) != 2:
            return None
            # raise ParsingException(f"Expected 2 tokens for SeeDelegation found: {count}")
        if tokens[0] != "See":
            return None
            # raise ParsingException(f"Invalid first token for SeeDelegation: {tokens[0]}")
        return tokens

    @classmethod
    def assemble(cls, tokens: list[str]) -> Self:
        return cls(MultiIdent(tokens[1]))

    def __str__(self) -> str:
        return "See {}".format(self.multi_ident.name)


@dataclasses.dataclass
class SeeParamDelegation(AssembleAst[list[str]]):
    param: MultiIdent
    target: MultiIdent

    @staticmethod
    def check(variant: str) -> list[str] | None:
        tokens = variant.split(" ")
        if len(tokens) != 4:
            return None
            # raise ParsingException(f"Expected 4 tokens for SeeParamDelegation found: {count}")
        if tokens[0] != "See":
            return None
            # raise ParsingException(f"Invalid first token for SeeParamDelegation: {tokens[0]}")
        if tokens[2] != "for":
            return None
            # raise ParsingException(f"Invalid third token for SeeParamDelegation: {tokens[2]}")
        return tokens

    @classmethod
    def assemble(cls, tokens: list[str]) -> Self:
        [_, param, _, target] = tokens
        return cls(MultiIdent(param), MultiIdent(target))

    def __str__(self) -> str:
        return "See {} for {}".format(self.param.name, self.target.name)


@dataclasses.dataclass
class SectionNumber(ParseAst):
    matcher: ClassVar[Pattern[str]] = re.compile(r"\d+(\.\d+(-\d+)?)*")
    path: list[int | range]

    @staticmethod
    def check(variant: str) -> bool:
        return SectionNumber.matcher.fullmatch(variant) is not None

    @staticmethod
    def _parse_stage(stage: str) -> int | range:
        match stage.split("-"):
            case [number]:
                return int(number)
            case [start, end]:
                return range(int(start), int(end))
            case _:
                SectionNumber.parsing_error(stage)

    @classmethod
    def parse(cls, variant: str) -> Self:
        return cls(
            list(cls._parse_stage(stage) for stage in variant.split("."))
        )

    def __str__(self) -> str:
        return ".".join(str(elem) if type(elem) == int else f"{elem.start}-{elem.stop}" for elem in self.path) # type: ignore


@dataclasses.dataclass
class SectionNumbers(AssembleAst[list[str]]):
    numbers: list[SectionNumber]

    @staticmethod
    def check(variant) -> list[str] | None:
        tokens = variant.split(", ")
        if any(not SectionNumber.check(number) for number in tokens):
            return None
        return tokens

    @classmethod
    def assemble(cls, stages: list[str]) -> Self:
        return cls([SectionNumber.parse(stage) for stage in stages])

    def __str__(self) -> str:
        return ", ".join(map(str, self.numbers))


@dataclasses.dataclass
class TableDelegation(ParseAst):
    numbers: SectionNumbers

    @staticmethod
    def check(variant: str) -> bool:
        if not variant.startswith("[Table"):
            return False
        if not variant.endswith("]"):
            return False
        return True

    @classmethod
    def parse(cls, variant: str) -> Self:
        trim = 8 if variant.startswith("[Tables") else 7
        numbers = SectionNumbers.process(variant[trim:-1])
        if numbers is None:
            SectionNumbers.parsing_error(variant)
        return cls(numbers)

    def __str__(self) -> str:
        message = "[Tables {}]" if len(self.numbers.numbers) > 1 else "[Table {}]"
        return message.format(self.numbers)


class LodLevel(ParseAst):
    @staticmethod
    def check(variant: str) -> bool:
        return variant == "LOD level"

    @classmethod
    def parse(cls, variant: str) -> Self:
        return cls()

    def __str__(self) -> str:
        return "LOD level"


@dataclasses.dataclass
class Variant(ParseAst):
    variants: list[str]
    variant_letter_set: ClassVar[set[str]] = {letter for letter in chain(chars('A', 'Z'), '_, ', ALL_TOKENS)}

    @staticmethod
    def expand(enumeration: str) -> Iterator[str]:
        yield from flatten(expand_variant(sub_variant) for sub_variant in enumeration_variants("{" + enumeration + "}"))

    @staticmethod
    def check(variant) -> bool:
        return all(letter in Variant.variant_letter_set for letter in variant)

    @classmethod
    def parse(cls, variant: str) -> Self:
        return cls(list(Variant.expand(variant)))

    def __str__(self) -> str:
        return ", ".join(self.variants)


@dataclasses.dataclass
class SectionDeclaration(AssembleAst[Tuple[str, str]]):
    name: str
    numbers: SectionNumbers

    @staticmethod
    def check(variant: str) -> Tuple[str, str] | None:
        # TODO: this check is not thorough enough
        if not all(section_sep in variant for section_sep in ["[", "]"]):
            return None
        name = variant[:variant.find("[") - 1]
        number = variant[variant.find("[") + 1: -1]
        return name, number

    @classmethod
    def assemble(cls, name_numbers: Tuple[str, str]) -> Self:
        name, numbers_str = name_numbers
        numbers = SectionNumbers.process(numbers_str)
        if numbers is None:
            SectionNumbers.parsing_error(numbers_str)
        return cls(name, numbers)

    def __str__(self) -> str:
        # ", ".join(map(str, self.sections))
        return f"{self.name}" if self.numbers is None else f"{self.name} [{self.numbers}]"


@dataclasses.dataclass
class SectionDescription(ParseAst):
    description: str

    @staticmethod
    def check(variant) -> bool:
        return True

    @classmethod
    def parse(cls, variant: str) -> Self:
        return cls(variant)

    def __str__(self) -> str:
        return self.description


@dataclasses.dataclass
class Bitwise(ParseAst):
    all_flag: str | None
    flags: list[str]

    @staticmethod
    def check(variant) -> bool:
        return variant.startswith("bitwise OR of")

    @classmethod
    def parse(cls, variant: str) -> Self:
        inner = variant.removeprefix("bitwise OR of ")
        all_flag = None
        if inner.startswith("all "):
            end = inner.find(" specific ")
            all_flag = inner[4:end]
            inner = inner[end + 10:]

        result = Variant.process(inner)
        if result is None:
            cls.parsing_error(variant)
        return cls(all_flag, result.variants)

    def __str__(self) -> str:
        all_flag = "all {} specific ".format(self.all_flag) if self.all_flag is not None else ""
        flags = ", ".join(self.flags)
        return "bitwise OR of {}{}".format(all_flag, flags)


Enumeration = Variant | SeeParamDelegation | SeeDelegation | TableDelegation | LodLevel | Bitwise


def unsupported_variant(variant: str) -> Enumeration:
    raise ParsingException(Variant, variant)


def parse_variant(
        variant: str,
        fallback: Callable[[str], Enumeration] = unsupported_variant
) -> Enumeration:
    node_types: list[type] = [
        Variant,
        SeeParamDelegation,
        SeeDelegation,
        TableDelegation,
        Bitwise,
        LodLevel
    ]
    for node_type in node_types:
        if result := node_type.process(variant):  # type: ignore
            return result
    return fallback(variant)


def parse_variant_list(variants: str) -> Iterator[Enumeration]:
    table_delegation_brace = variants.find("]")
    # If variant list starts with table delegation trim it.
    if result := TableDelegation.process(variants[:(trim := table_delegation_brace + 1)]):
        yield result
        variants = variants[trim + 1:]
    yield from (parse_variant(variant.strip()) for variant in split_on_level(variants))


@dataclasses.dataclass
class ParameterEnumeration(ParseAst):
    params: list[str]
    variants: list[Enumeration]

    @staticmethod
    def check(variant) -> bool:
        return ":" in variant

    @classmethod
    def parse(cls, variant: str) -> Self:
        [params, variants_str] = variant.split(": ")
        names = params.split(", ")
        variants = list(parse_variant_list(variants_str))
        return cls(
            names,
            variants
        )

    def __str__(self) -> str:
        return ", ".join(self.params) + ": " + ", ".join(map(str, self.variants))
