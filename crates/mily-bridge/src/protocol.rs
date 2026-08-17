use std::io::{self, Read, Write};
use thiserror::Error;

/// Chrome Native Messaging usa un prefijo de longitud de 32 bits. En Windows
/// se procesa en modo binario y con little-endian para no corromper el framing.
pub const MAX_MESSAGE_BYTES: usize = 1024 * 1024;

#[derive(Debug, Error)]
pub enum ProtocolError {
    #[error("mensaje Native Messaging demasiado grande")]
    MessageTooLarge,
    #[error("mensaje Native Messaging truncado")]
    Truncated,
    #[error("error de E/S Native Messaging: {0}")]
    Io(#[from] io::Error),
}

pub fn read_frame<R: Read>(reader: &mut R) -> Result<Vec<u8>, ProtocolError> {
    let mut length_bytes = [0_u8; 4];
    match reader.read_exact(&mut length_bytes) {
        Ok(()) => {}
        Err(error) if error.kind() == io::ErrorKind::UnexpectedEof => {
            return Err(ProtocolError::Truncated);
        }
        Err(error) => return Err(ProtocolError::Io(error)),
    }

    let length = u32::from_le_bytes(length_bytes) as usize;
    if length > MAX_MESSAGE_BYTES {
        return Err(ProtocolError::MessageTooLarge);
    }

    let mut payload = vec![0_u8; length];
    match reader.read_exact(&mut payload) {
        Ok(()) => Ok(payload),
        Err(error) if error.kind() == io::ErrorKind::UnexpectedEof => Err(ProtocolError::Truncated),
        Err(error) => Err(ProtocolError::Io(error)),
    }
}

pub fn write_frame<W: Write>(writer: &mut W, payload: &[u8]) -> Result<(), ProtocolError> {
    if payload.len() > MAX_MESSAGE_BYTES {
        return Err(ProtocolError::MessageTooLarge);
    }
    writer.write_all(&(payload.len() as u32).to_le_bytes())?;
    writer.write_all(payload)?;
    writer.flush()?;
    Ok(())
}

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
