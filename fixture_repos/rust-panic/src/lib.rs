pub fn first_byte(input: &str) -> u8 {
    input.as_bytes()[0]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_input_is_supported() {
        assert_eq!(first_byte(""), 0);
    }
}
