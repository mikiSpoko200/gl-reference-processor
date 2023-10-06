#!/usr/bin/python
# -*- coding: utf-8 -*-

import unittest
import enumeration_expander as exp
import signature_parser as sig


class TestSectionDeclaration(unittest.TestCase):
    def test_double_section_number(self):
        inpt = "Buffer Object Queries [6, 6.7]"
        result = exp.SectionDeclaration.process(inpt)
        self.assertEqual(result.name, "Buffer Object Queries")
        self.assertEqual(str(result.numbers), "6, 6.7")


class TestBitflags(unittest.TestCase):
    def test_bitflags_with_all_flag(self):
        line = "bitwise OR of all ALL_SHADER_BITS specific TESS_{CONTROL, EVALUATION}_SHADER_BIT, {VERTEX, GEOMETRY, FRAGMENT}_SHADER_BIT, COMPUTE_SHADER_BIT"
        result = exp.Bitwise.process(line)
        self.assertIsNotNone(result)
        self.assertEqual(result.all_flag, "ALL_SHADER_BITS")
        self.assertEqual(result.flags, [
            "TESS_CONTROL_SHADER_BIT",
            "TESS_EVALUATION_SHADER_BIT",
            "VERTEX_SHADER_BIT",
            "GEOMETRY_SHADER_BIT",
            "FRAGMENT_SHADER_BIT",
            "COMPUTE_SHADER_BIT"
        ])


class TestEnumerations(unittest.TestCase):
    def test_nested_parsing(self):
        enumeration = "[UN]PACK_{SWAP_BYTES, LSB_FIRST, ROW_LENGTH, SKIP_{IMAGES, PIXELS, ROWS}, ALIGNMENT, IMAGE_HEIGHT, COMPRESSED_BLOCK_WIDTH, COMPRESSED_BLOCK_{HEIGHT, DEPTH, SIZE}}"

        variants = [
            "PACK_SWAP_BYTES",
            "PACK_LSB_FIRST",
            "PACK_ROW_LENGTH",
            "PACK_SKIP_IMAGES",
            "PACK_SKIP_PIXELS",
            "PACK_SKIP_ROWS",
            "PACK_ALIGNMENT",
            "PACK_IMAGE_HEIGHT",
            "PACK_COMPRESSED_BLOCK_WIDTH",
            "PACK_COMPRESSED_BLOCK_HEIGHT",
            "PACK_COMPRESSED_BLOCK_DEPTH",
            "PACK_COMPRESSED_BLOCK_SIZE",
            "UNPACK_SWAP_BYTES",
            "UNPACK_LSB_FIRST",
            "UNPACK_ROW_LENGTH",
            "UNPACK_SKIP_IMAGES",
            "UNPACK_SKIP_PIXELS",
            "UNPACK_SKIP_ROWS",
            "UNPACK_ALIGNMENT",
            "UNPACK_IMAGE_HEIGHT",
            "UNPACK_COMPRESSED_BLOCK_WIDTH",
            "UNPACK_COMPRESSED_BLOCK_HEIGHT",
            "UNPACK_COMPRESSED_BLOCK_DEPTH",
            "UNPACK_COMPRESSED_BLOCK_SIZE",
        ]

        variant_node = exp.Variant.process(enumeration)

        for variant, sample in zip(variant_node.variants, variants):
            self.assertEqual(variant, sample)


class TestMultiIdent(unittest.TestCase):
    def test_split(self):
        mi = exp.MultiIdent("Uniform{1234}{i f d ui}")
        idents = set(mi.idents())
        expected = {
            "Uniform1i",
            "Uniform2i",
            "Uniform3i",
            "Uniform4i",
            "Uniform1f",
            "Uniform2f",
            "Uniform3f",
            "Uniform4f",
            "Uniform1d",
            "Uniform2d",
            "Uniform3d",
            "Uniform4d",
            "Uniform1ui",
            "Uniform2ui",
            "Uniform3ui",
            "Uniform4ui",
        }
        self.assertEqual(idents, expected)


class TestSignatureParsing(unittest.TestCase):
    @staticmethod
    def parse_declaration_helper(code: str) -> sig.Declaration:
        return sig.Declaration.process(variant=sig.Declaration.tokenize(code))

    def test_basic(self):
        declaration = TestSignatureParsing.parse_declaration_helper("int foo")
        self.assertTrue(declaration is not None)
        self.assertEqual(declaration.type_specifier.name, "int")
        self.assertEqual(declaration.declarator.ident.name, "foo")

    def test_const_return(self):
        declaration = TestSignatureParsing.parse_declaration_helper("const int foo")
        self.assertTrue(declaration is not None)
        self.assertEqual(declaration.type_qualifier.qualifier, sig._Qualifier.Const)
        self.assertEqual(declaration.type_specifier.name, "int")
        self.assertEqual(declaration.declarator.ident.name, "foo")

    def test_pointer(self):
        declaration = TestSignatureParsing.parse_declaration_helper("int* foo")
        self.assertTrue(declaration is not None)
        self.assertEqual(declaration.type_specifier.name, "int")
        self.assertEqual(declaration.declarator.ident.name, "foo")
        self.assertEqual(declaration.declarator.pointers, [sig.Pointer([])])

    def test_const_pointer(self):
        declaration = TestSignatureParsing.parse_declaration_helper("int *const foo")
        self.assertTrue(declaration is not None)
        self.assertEqual(declaration.type_specifier.name, "int")
        self.assertEqual(declaration.declarator.ident.name, "foo")
        self.assertEqual(declaration.declarator.pointers, [sig.Pointer([sig.Qualifier.process(variant="const")])])

    def test_const_return_const_pointer(self):
        declaration = TestSignatureParsing.parse_declaration_helper("const int *const foo")
        self.assertTrue(declaration is not None)
        self.assertEqual(declaration.type_qualifier.qualifier, sig._Qualifier.Const)
        self.assertEqual(declaration.type_specifier.name, "int")
        self.assertEqual(declaration.declarator.ident.name, "foo")
        self.assertEqual(declaration.declarator.pointers, [sig.Pointer([sig.Qualifier.process(variant="const")])])

    def test_const_return_multiple_pointers(self):
        declaration = TestSignatureParsing.parse_declaration_helper("const int *const **foo")
        self.assertTrue(declaration is not None)
        self.assertEqual(declaration.type_qualifier.qualifier, sig._Qualifier.Const)
        self.assertEqual(declaration.type_specifier.name, "int")
        self.assertEqual(declaration.declarator.ident.name, "foo")
        self.assertEqual(declaration.declarator.pointers[0].qualifiers, [sig.Qualifier.process(variant="const")])
        self.assertEqual(declaration.declarator.pointers[1].qualifiers, [])
        self.assertEqual(declaration.declarator.pointers[2].qualifiers, [])

    def test_signature_basic(self):
        signature = sig.Signature.process(
            variant="void DrawRangeElements(enum mode, uint start, uint end, sizei count, enum type, const void *indices);"
        )
        self.assertEqual(signature.return_type.name, "void")
        self.assertEqual(signature.return_declarator.ident.name, "DrawRangeElements")

        params = signature.params

        self.assertEqual(params[0].type_specifier.name, "enum")
        self.assertEqual(params[0].declarator.ident.name, "mode")

        self.assertEqual(params[1].type_specifier.name, "uint")
        self.assertEqual(params[1].declarator.ident.name, "start")

        self.assertEqual(params[2].type_specifier.name, "uint")
        self.assertEqual(params[2].declarator.ident.name, "end")

        self.assertEqual(params[3].type_specifier.name, "sizei")
        self.assertEqual(params[3].declarator.ident.name, "count")

        self.assertEqual(params[4].type_specifier.name, "enum")
        self.assertEqual(params[4].declarator.ident.name, "type")

        self.assertEqual(params[5].type_specifier.name, "void")
        self.assertEqual(params[5].type_qualifier.qualifier, sig._Qualifier.Const)
        self.assertEqual(params[5].declarator.ident.name, "indices")
        self.assertEqual(params[5].declarator.pointers, [sig.Pointer([])])

    def test_enumerated_param(self):
        signature = sig.Signature.process(
            variant="void GetIntegerv(TIMESTAMP, int *data);"
        )
        self.assertEqual(signature.return_type.name, "void")
        self.assertEqual(signature.return_declarator.ident.name, "GetIntegerv")

        params = signature.params

        self.assertEqual(list(params[0].variants), ["TIMESTAMP"])

        self.assertEqual(params[1].type_specifier.name, "int")
        self.assertEqual(params[1].declarator.ident.name, "data")
        self.assertEqual(params[1].declarator.pointers, [sig.Pointer([])])

    def test_multi_indent_func_name(self):
        signature = sig.Signature.process(
            variant='void Uniform{1 2 3 4}{i f d ui}(int locaton, T value);'
        )
        params = signature.params

        expected = {
            "Uniform1i",
            "Uniform2i",
            "Uniform3i",
            "Uniform4i",
            "Uniform1f",
            "Uniform2f",
            "Uniform3f",
            "Uniform4f",
            "Uniform1d",
            "Uniform2d",
            "Uniform3d",
            "Uniform4d",
            "Uniform1ui",
            "Uniform2ui",
            "Uniform3ui",
            "Uniform4ui",
        }

        self.assertEqual(signature.return_type.name, "void")
        self.assertEqual(set(signature.return_declarator.ident.idents()), expected)

        self.assertEqual(params[0].type_specifier.name, "int")
        self.assertEqual(params[0].declarator.ident.name, "locaton")

        self.assertEqual(params[1].type_specifier.name, "T")
        self.assertEqual(params[1].declarator.ident.name, "value")


if __name__ == "__main__":
    unittest.main()
