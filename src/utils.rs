use std::marker::PhantomData;

pub trait IndentationInfo {
    fn is_indent(marker: char) -> bool;

    fn is_dedent(marker: char) -> bool;
}

struct VariantIndentationInfo;

impl VariantIndentationInfo {
    const INDENTS: &'static [char] = &['{', '['];
    const DEDENTS: &'static [char] = &['}', ']'];
}

impl IndentationInfo for VariantIndentationInfo {
    fn is_indent(marker: char) -> bool { Self::INDENTS.contains(&marker) }

    fn is_dedent(marker: char) -> bool { Self::DEDENTS.contains(&marker) }
}

struct SplitOnLevel<'a, I = VariantIndentationInfo> {
    offset: usize,
    depth: usize,
    haystack: &'a str,
    sep: char,
    _indent_phantom: PhantomData<I>
}

impl<'a, I> Iterator for SplitOnLevel<'a, I>
where
    I: IndentationInfo
{
    type Item = &'a str;

    fn next(&mut self) -> Option<Self::Item> {
        if self.haystack.is_empty() { return None; }
        while let [char, tail @ ..] = self.haystack {
            if I::is_indent(char) {
                self.depth += 1;
            }
            if I::is_dedent(char) {
                self.depth -= 1;
            }
            if self.depth == 0 && char == self.sep {
                let old_offset = self.offset;
                self.offset = index + 1;
                self.haystack = 
                return Some(&self.haystack[old_offset..index]);
            }
        }
        Some(self.haystack)
    }
}



fn split_on_level<T, P, I>(input: &str, pat: P)
where
    P: sep,
    I: IndentationInfo
{

}