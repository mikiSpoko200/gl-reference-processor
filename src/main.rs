mod utils;

use logos::{Logos};

use std::fs::read_to_string;

const FILES: &'static [&'static str] = [
    "buffer.txt",
    "compute shaders.txt",
    "debug output.txt",
    "fragment shader.txt",
    "framebuffer.txt",
    "per fragment operations.txt",
    "rasterization.txt",
    "reading and copying pixels.txt",
    "reference_contents.txt",
    "shader.txt",
    "state and state requests.txt",
    "textures and samplers.txt",
    "vao.txt",
    "vertex attributes.txt",
    "vertex post-processing.txt",
    "vertices.txt",
    "whole framebuffers.txt",
].as_slice();

type Ts<'source> = &'source [Token<'source>];

#[derive(Logos, Debug, PartialEq)]
#[logos(skip r"[ \t\n\f]+")]
pub enum Token<'source> {
    #[token("(")]
    OpeningParenthesis,
    #[token(")")]
    ClosingParenthesis,
    #[token("[")]
    OpeningBrace,
    #[token("]")]
    ClosingBrace,
    #[token("{")]
    OpeningBracket,
    #[token("}")]
    ClosingBracket,
    #[token(",")]
    Comma,
    #[token(".")]
    Period,
    #[token(":")]
    Colon,
    #[token(";")]
    Semicolon,
    #[token("*")]
    Asterisk,
    #[regex("[0-9]+", |lex| lex.slice().parse().ok())]
    Number(u64),
    #[regex("[a-zA-Z_/]+")]
    Text(&'source str),
}

#[derive(Debug, Clone, Hash, PartialEq, Eq)]
pub struct ParameterDelegation<'s> {
    pub name: &'s str,
    pub target: &'s function::Function<'s>,
}

#[derive(Debug, Clone, Hash, PartialEq, Eq)]
pub struct ParameterDescription<'s> {
    pub name: &'s str,
    pub description: &'s str,
}

#[derive(Debug, Clone, Hash, PartialEq, Eq)]
pub enum ReferenceTarget {
    Core([u8; 3]),
    Table([u8; 2]),
    Shader([u8; 3]),
}

#[derive(Debug, Clone, Hash, PartialEq, Eq)]
pub struct SpecificationReference<'s> {
    title: &'s str,
    target: ReferenceTarget
}

#[derive(Debug, Clone, Hash, PartialEq, Eq)]
pub struct Section<'s> {
    title: &'s str,
    numbers: [u8; 3]
}

#[derive(Debug, Clone, Hash, PartialEq, Eq)]
pub enum Ast<'s> {
    Parameter(parameter::Parameter<'s>),
    EnumVariant { name: &'s str, variants: () },
    Function(function::Function<'s>),
    Section(Section<'s>),
}

pub mod test_helpers {
    use logos::{Logos};
    use crate::Token;

    pub fn tokenize(source: &str) -> Vec<Token> {
        Token::lexer(source)
            .map(|token| token.expect("source contains valid tokens"))
            .collect()
    }
}

pub mod parameter {
    use crate::Ts;
    use super::{Token};

    #[derive(Debug, Clone, Hash, PartialEq, Eq)]
    pub enum Type<'s> {
        Value(&'s str),
        Pointer(&'s str),
        ConstPointer(&'s str),
    }

    #[derive(Debug, Clone, Hash, PartialEq, Eq)]
    pub struct Parameter<'s> {
        pub ty: Type<'s>,
        pub ident: &'s str,
    }

    pub fn parse<'source>(tokens: &mut Ts<'source>) -> Vec<Parameter<'source>> {
        use Token::Text;

        let mut params = Vec::new();
        let parenthesis_pos = tokens
            .iter()
            .position(|token| token == &Token::ClosingParenthesis)
            .expect("closing parenthesis exists");
        let (param_tokens, tail) = tokens.split_at(parenthesis_pos);
        *tokens = &tail[1..];

        for slice in param_tokens.split(|token| token == &Token::Comma) {
            params.push(match slice {
                [Text(ty), Text(ident)]
                => value(ty, ident),
                [Text(ty), Token::Asterisk, Text(ident)]
                => pointer(ty, ident),
                [Text("const"), Text(ty), Token::Asterisk, Text(ident)]
                => const_pointer(ty, ident),
                other => panic!("unsupported parameter format: {:?}", other),
            });
        }
        params
    }
    pub fn value<'s>(ty: &'s str, ident: &'s str) -> Parameter<'s> {
        Parameter { ty: Type::Value(ty), ident }
    }

    pub fn pointer<'s>(ty: &'s str, ident: &'s str) -> Parameter<'s> {
        Parameter { ty: Type::Pointer(ty), ident }
    }

    pub fn const_pointer<'s>(ty: &'s str, ident: &'s str) -> Parameter<'s> {
        Parameter { ty: Type::ConstPointer(ty), ident }
    }

    #[cfg(test)]
    pub mod tests {
        use crate::test_helpers::tokenize;
        use super::{value, pointer, parse};

        #[test]
        fn parse_multi_value_parameters() {
            let tokens = tokenize("uint buffer, enum internalformat, enum format, enum type)");
            let mut ts = tokens.as_ref();
            let result = parse(&mut ts);

            let expected = [
                value("uint", "buffer" ),
                value("enum", "internalformat" ),
                value("enum", "format" ),
                value("enum", "type" ),
            ];

            for (result, expected) in result.into_iter().zip(expected) {
                assert_eq!(result, expected);
            }
        }

        #[test]
        fn parse_multi_pointer_parameters() {
            let tokens = tokenize("uint* buffer, void *data);");
            let mut ts = tokens.as_ref();
            let result = parse(&mut ts);

            let expected = [
                pointer("uint", "buffer" ),
                pointer("void", "data" ),
            ];

            for (result, expected) in result.into_iter().zip(expected) {
                assert_eq!(result, expected);
            }
        }
    }
}

pub mod function {
    use super::{Ts, parameter, Token};

    #[derive(Debug, Clone, Hash, PartialEq, Eq)]
    pub struct Function<'s> {
        pub return_type: parameter::Type<'s>,
        pub ident: &'s str,
        pub params: Vec<parameter::Parameter<'s>>
    }

    fn parse<'source>(ts: &mut Ts<'source>) -> Function<'source> {
        use Token::Text;
        use parameter::Type;

        let (rty, rest) = match *ts {
            [Text("const"), Text(ty), Token::Asterisk, rest @ ..]
            => (Type::ConstPointer(ty), rest),
            [Text(ty), Token::Asterisk, rest @ ..] => (Type::Pointer(ty), rest),
            [Text(ty), rest @ ..] => (Type::Value(ty), rest),
            other => panic!("invalid return type {:?}", other),
        };

        match rest {
            [Text(ident), Token::OpeningParenthesis, rest @ ..] => {
                *ts = rest;
                Function {
                    return_type: rty,
                    ident,
                    params: parameter::parse(ts),
                }
            },
            other => panic!("invalid identifier {:?}", other),
        }
    }

    #[cfg(test)]
    mod tests {
        use crate::parameter::Type;
        use crate::test_helpers::tokenize;
        use super::{parse, Token};

        #[test]
        pub fn value_return() {
            let tokens = tokenize("void BindBuffersRange(enum target, uint first, sizei count,const uint *buffers, const intptr *offsets, const sizeiptr *size);");
            let mut ts = tokens.as_ref();

            let function = parse(&mut ts);

            assert_eq!(function.return_type, Type::Value("void"));
            assert_eq!(function.ident, "BindBuffersRange");
            assert_eq!(ts.first(), Some(&Token::Semicolon));
        }

        #[test]
        pub fn pointer_return() {
            let tokens = tokenize("void *MapBufferRange(enum target, intptr offset, sizeiptr length, bitfield access);");
            let mut ts = tokens.as_ref();

            let function = parse(&mut ts);

            assert_eq!(function.return_type, Type::Pointer("void"));
            assert_eq!(function.ident, "MapBufferRange");
            assert_eq!(ts.first(), Some(&Token::Semicolon));
        }
    }
}

pub mod preprocessor {
    fn
}

pub mod enumeration {
    use super::Ts;

    /// Iterator that produces expanded enumeration variants as str
    ///
    /// Variant prefix / infix / suffix copies will be kept down to minimum.
    ///
    /// The enumeration creates a tree, and iterator will yield paths to leaf nodes.
    /// The least amount of copies can be achieved using DFS?
    /// There is only need for one path and the prefix remains the same for as long as possible
    ///
    /// Upon encountering enumeration separator token we can eagerly search for the corresponding
    /// closing token in order to take advantage that sub variants are contiguously laid out in
    /// token stream thus we can easily find one with largest span and use this as search heuristic
    /// to reduce line buffer relocations by initially allocating memory for largest possible variant.
    ///
    pub struct VariantIter<'source> {
        source: Ts<'source>,
        buffer: String,
    }

    impl Iterator for VariantIter {
        type Item = ();

        fn next(&mut self) -> Option<Self::Item> {
            todo!()
        }
    }

    pub fn expand_variant(variant: &str) -> impl Iterator<Item=&str> {

    }

    pub fn parse(ts: &mut Ts) {
        use super::Token::*;


        let [Text(ident), Colon, rest @ ..] = ts else {
            let params = ts.split(|token| token == &Colon).next().expect("colon exists");
            panic!("unsupported parameter enumeration format: {params:?}");
        };
        *ts = rest;

    }
}

// pub fn parse(tokens: Vec<Token>) {
//     let ts = &mut tokens.as_slice();
//     match token_steam {
//         // match for section name
//         [Token::OpeningParenthesis, ..] => todo!(), //parse_params(rest)
//         [return_type, Token::Asterisk, ident, Token::OpeningParenthesis, rest @ ..] =>
//             Ast::Function(
//                 Function {
//                     return_type: todo!(),
//                     ident: "",
//                     params: vec![],
//                 }
//             ),
//         // match for function declaration -- note type parsing won't work correctly.
//         [return_type, ident, Token::OpeningParenthesis, rest @ ..] => todo!(),
//         _ => todo!(),
//     };
// }

fn main() {
    let source = read_to_string("buffer.txt").expect("file exists");
    let tokens: Vec<_> = Token::lexer(&source)
        .map(|err| {
            err.expect("all possible tokens are accounted for")
        })
        .collect();
    for token in &tokens {
        println!("{:?}", token);
    }
    // let mut redirects = HashMap::new();
    // parse_parameters(&tokens);
    // let ast = parse_rec(&tokens, &mut redirects);
    println!("Hello, world!");
}
