import itertools
import json
import re
from typing import Iterator, Callable, Any, Iterable

import reference
import signature_parser as sig
import enumeration_expander as exp

REFERENCE_CARD = "reference-original.txt"

KEYWORDS = ["(", ":"]

SECTION_REGEX = re.compile(r"\[(\d+\.)*\d+]|\d-\d]|\[\d, \d")
OPTIONAL_REGEX = re.compile(r"\[\D+]")

LINE_SEP_PREDICATES = [
    lambda line: any(keyword in line for keyword in KEYWORDS), 
]

LINE_INLINE_PREDICATES = [
    lambda line: SECTION_REGEX.search(line) is not None
]


def should_separate(line: str) -> bool:
    return any(pred(line) for pred in LINE_SEP_PREDICATES)


def should_inline(line: str) -> bool:
    return any(pred(line) for pred in LINE_INLINE_PREDICATES)


def inline_func_signatures(lines: Iterator[str]) -> list[str]:
    buffer = []
    result = []
    look_for_matching_parenthesis = False
    for line in lines:
        if "(" in line:
            look_for_matching_parenthesis = True
        if not look_for_matching_parenthesis:
            result.append(line)
        else:
            buffer.append(line)
        if ")" in line:
            look_for_matching_parenthesis = False
            result.append("".join(buffer))
            buffer = []
    return result


def inline_enumerations(lines: Iterator[str]) -> list[str]:
    buffer: list[str] = []
    result = []
    for line in lines:
        line = line.strip()
        if should_inline(line):
            if buffer:
                result.append(" ".join(buffer))
            result.append(line)
            buffer = []
        elif should_separate(line):
            if buffer:
                result.append(" ".join(buffer))
            buffer = [line]
        else:
            buffer.append(line)
    return result


def process_enumeration_line(line: str) -> str:
    result = []
    variants = []
    entries = line.split(",")
    look_for_matching_brace = False
    base = ""
    for entry in entries:
        trimmed = entry.strip()
        if "{" in trimmed:
            if "_" in trimmed:
                pos = trimmed.find("_")
                base = trimmed[:pos+1]
            pos = trimmed.find("{")
            trimmed = trimmed[pos+1:]
            look_for_matching_brace = True
        if not look_for_matching_brace:
            result.append(entry)
        else:
            if "}" in trimmed:
                if "_" in trimmed:
                    pos = trimmed.find("_")
                    base = trimmed[pos:]
                look_for_matching_brace = False
                pos = trimmed.find("}")
                trimmed = trimmed[:pos]
                variants.append(trimmed)
                result.extend(
                    base + variant if base.endswith("_") else variant + base
                    for variant in variants
                )
            else:
                variants.append(trimmed)
    return ", ".join(result)


def preprocess(lines) -> Iterator[str]:
    lines = inline_func_signatures(lines)
    lines = inline_enumerations(lines)
    return lines


def parse_param_line(
        line: str,
        fallback: Callable[[str], Any] = lambda line: print("Unrecognized format: {}".format(line))
):
    match line.split(":"):
        case [_params, variants]:
            exp.parse_variant_list(variants)
        case [line] if "[" in line:
            if section_dec := exp.SectionDeclaration.process(line):
                return section_dec
        case [line]:
            if signature := sig.Signature.process(line):
                return signature
            else:
                return fallback(line)
        case _:
            return fallback(line)


class Lines(Iterable[str]):
    def __init__(self, lines: Iterator[str]):
        self.inner = iter(lines)

    def __iter__(self) -> Iterator[str]:
        return self

    def __next__(self) -> str:
        return next(self.inner)

    def push(self, line: str):
        self.inner = itertools.chain([line], self.inner)


def process_functions(lines: Lines) -> list[reference.Function]:
    functions = list()
    line = ""
    try:
        while sig.Signature.check(line := next(lines)):
            try:
                signature: sig.Signature | None = sig.Signature.process(line)
                if signature is None:
                    sig.Signature.parsing_error(line)
            except StopIteration:
                sig.Signature.parsing_error("at least one function definition in section")

            enumerations = list()

            try:
                line = next(lines)
                enumeration_line: exp.ParameterEnumeration | None
                while enumeration_line := exp.ParameterEnumeration.process(line):
                    enumerations.append(enumeration_line)
                    line = next(lines)
                lines.push(line)
            except StopIteration:
                pass
            functions.append(reference.Function(signature, enumerations, {}))
    finally:
        lines.push(line)
        return functions


def process_section(lines: Lines) -> reference.Section | None:
    description = list()

    try:
        line = next(lines)
        section: exp.SectionDeclaration | None = exp.SectionDeclaration.process(line)
        if section is None:
            exp.SectionDeclaration.parsing_error(line)
    except StopIteration:
        return None

    try:
        line = next(lines)
        while not sig.Signature.check(line):
            desc = exp.SectionDescription.process(line)
            assert(desc is not None)
            description.append(desc)
            line = next(lines)
    except StopIteration:
        pass
    lines.push(line)

    functions = process_functions(lines)

    return reference.Section(
        section,
        description,
        functions
    )


RED_FONT = "\u001b[31m"
WHITE_FONT = "\u001b[0m"


def report_malformed(lines: list[str]):
    print(f"{RED_FONT}============== MALFORMED LINES =============={WHITE_FONT}")
    for index, line in enumerate(lines):
        print("{}. '{}'".format(index + 1, line))


def main():
    with (
        open("out-reference.txt", "r", encoding="utf-8") as reference
        , open("custom-format-cache.json", "r", encoding="utf-8") as cache_file
        # , open("out-reference.txt", "w", encoding="utf-8") as _output
    ):
        # _output.write("\n".join(preprocess(file.splitlines())))
        cache = json.load(cache_file)

        print(WHITE_FONT, end="")
        sections = list()
        lines = Lines(reference.read().splitlines())
        lines_to_fix = list()
        seek_section = True
        while True:
            try:
                section = process_section(lines)
                seek_section = False
                # test is lines is empty
                line = next(lines)
                lines.push(line)
                if section is not None:
                    print(section)
                    sections.append(section)
                else:
                    break
            except exp.ParsingException as err:
                if not seek_section:
                    print(f"{RED_FONT}>>>{WHITE_FONT}")
                    print(f"{RED_FONT}>>>{WHITE_FONT} {err}")
                    print(f"{RED_FONT}>>>{WHITE_FONT}")
                    lines_to_fix.append(err.content)
                    seek_section = True
            except StopIteration:
                break

        # report_malformed(lines_to_fix)

        def fallback(line_: str):
            for entry in cache["lines"]:
                if line_ == entry["line"]:
                    return entry
            # print("Unrecognized format: {}".format(line_))


if __name__ == '__main__':
    main()
