#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn native_message_roundtrip_uses_little_endian_length_prefix() {
        let payload = br#"{"protocol":1,"type":"status"}"#;
        let mut output = Vec::new();
        write_frame(&mut output, payload).expect("write frame");

        let expected_len = (payload.len() as u32).to_le_bytes();
        assert_eq!(&output[..4], &expected_len);
        assert_eq!(&output[4..], payload);

        let decoded = read_frame(&mut Cursor::new(output)).expect("read frame");
        assert_eq!(decoded, payload);
    }

    #[test]
    fn oversized_native_message_is_rejected_before_allocation() {
        let mut frame = Vec::new();
        frame.extend_from_slice(&((1024_u32 * 1024) + 1).to_le_bytes());
        let error = read_frame(&mut Cursor::new(frame)).expect_err("oversized frame must fail");
        assert!(error.to_string().contains("demasiado grande"));
    }
}
