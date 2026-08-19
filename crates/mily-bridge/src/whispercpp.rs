//! Bridge stdio persistente para whisper.cpp.
//!
//! El contexto/modelo se carga una sola vez. Cada solicitud crea únicamente un
//! estado de inferencia y recibe PCM f32 mono a 16 kHz mediante tuberías locales.

use serde::{Deserialize, Serialize};
use std::ffi::OsString;
use std::io::{self, BufReader, BufWriter, Read, Write};
use std::path::PathBuf;
use thiserror::Error;
use whisper_rs::{
    FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters, get_lang_str,
};

const PROTOCOL_VERSION: u8 = 1;
const SAMPLE_RATE: u32 = 16_000;
const MAX_METADATA_BYTES: usize = 64 * 1024;
const MAX_PCM_BYTES: usize = 16 * 1024 * 1024;
const MAX_RESPONSE_BYTES: usize = 16 * 1024 * 1024;

#[derive(Debug, Error)]
enum WhisperBridgeError {
    #[error("argumentos whisper.cpp inválidos")]
    InvalidArguments,
    #[error("backend whisper.cpp no disponible en este binario")]
    UnsupportedBackend,
    #[error("modelo whisper.cpp no disponible")]
    ModelMissing,
    #[error("trama whisper.cpp inválida")]
    InvalidFrame,
    #[error("metadatos whisper.cpp inválidos")]
    InvalidMetadata,
    #[error("whisper.cpp no pudo cargar o ejecutar el modelo: {0}")]
    Runtime(String),
    #[error(transparent)]
    Io(#[from] io::Error),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct BridgeConfig {
    model: PathBuf,
    backend: String,
    threads: i32,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct RequestMetadata {
    protocol: u8,
    sample_rate: u32,
    language: String,
    sample_count: usize,
    #[serde(default)]
    word_timestamps: bool,
}

#[derive(Debug)]
struct TranscriptionRequest {
    metadata: RequestMetadata,
    samples: Vec<f32>,
}

#[derive(Debug, Serialize)]
struct TranscriptionResponse {
    protocol: u8,
    text: String,
    language: String,
}

struct WhisperEngine {
    config: BridgeConfig,
    context: Option<WhisperContext>,
}

impl WhisperEngine {
    fn new(config: BridgeConfig) -> Self {
        Self {
            config,
            context: None,
        }
    }

    fn context(&mut self) -> Result<&WhisperContext, WhisperBridgeError> {
        if self.context.is_none() {
            if !self.config.model.is_file() {
                return Err(WhisperBridgeError::ModelMissing);
            }
            let model = self
                .config
                .model
                .to_str()
                .ok_or(WhisperBridgeError::ModelMissing)?;
            let context =
                WhisperContext::new_with_params(model, WhisperContextParameters::default())
                    .map_err(|error| WhisperBridgeError::Runtime(error.to_string()))?;
            self.context = Some(context);
        }
        self.context
            .as_ref()
            .ok_or(WhisperBridgeError::ModelMissing)
    }

    fn transcribe(
        &mut self,
        request: TranscriptionRequest,
    ) -> Result<TranscriptionResponse, WhisperBridgeError> {
        let threads = self.config.threads;
        let requested_language = request.metadata.language.clone();
        let word_timestamps = request.metadata.word_timestamps;
        let mut state = self
            .context()?
            .create_state()
            .map_err(|error| WhisperBridgeError::Runtime(error.to_string()))?;
        let mut params = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
        params.set_n_threads(threads);
        params.set_no_context(true);
        params.set_single_segment(false);
        params.set_print_special(false);
        params.set_print_progress(false);
        params.set_print_realtime(false);
        params.set_print_timestamps(false);
        params.set_token_timestamps(word_timestamps);
        params.set_no_timestamps(!word_timestamps);
        params.set_temperature(0.0);
        if requested_language == "auto" {
            params.set_language(None);
            params.set_detect_language(true);
        } else {
            params.set_language(Some(requested_language.as_str()));
            params.set_detect_language(false);
        }
        state
            .full(params, &request.samples)
            .map_err(|error| WhisperBridgeError::Runtime(error.to_string()))?;

        let text = state
            .as_iter()
            .filter_map(|segment| segment.to_str_lossy().ok())
            .map(|segment| segment.trim().to_owned())
            .filter(|segment| !segment.is_empty())
            .collect::<Vec<_>>()
            .join(" ");
        let language = if requested_language == "auto" {
            get_lang_str(state.full_lang_id_from_state())
                .unwrap_or("auto")
                .to_owned()
        } else {
            requested_language
        };
        Ok(TranscriptionResponse {
            protocol: PROTOCOL_VERSION,
            text,
            language,
        })
    }
}

fn parse_args<I>(args: I) -> Result<BridgeConfig, WhisperBridgeError>
where
    I: IntoIterator<Item = OsString>,
{
    let mut values = args.into_iter();
    let mut model: Option<PathBuf> = None;
    let mut backend = String::from("cpu");
    let mut threads = 1_i32;
    while let Some(argument) = values.next() {
        match argument.to_string_lossy().as_ref() {
            "--model" => {
                model = values.next().map(PathBuf::from);
            }
            "--backend" => {
                backend = values
                    .next()
                    .ok_or(WhisperBridgeError::InvalidArguments)?
                    .to_string_lossy()
                    .to_ascii_lowercase();
            }
            "--threads" => {
                let raw = values.next().ok_or(WhisperBridgeError::InvalidArguments)?;
                threads = raw
                    .to_string_lossy()
                    .parse::<i32>()
                    .map_err(|_| WhisperBridgeError::InvalidArguments)?
                    .clamp(1, 64);
            }
            _ => return Err(WhisperBridgeError::InvalidArguments),
        }
    }
    if backend != "cpu" {
        return Err(WhisperBridgeError::UnsupportedBackend);
    }
    Ok(BridgeConfig {
        model: model.ok_or(WhisperBridgeError::InvalidArguments)?,
        backend,
        threads,
    })
}

fn read_header(reader: &mut impl Read) -> Result<Option<[u8; 8]>, WhisperBridgeError> {
    let mut header = [0_u8; 8];
    let first = reader.read(&mut header[..1])?;
    if first == 0 {
        return Ok(None);
    }
    reader.read_exact(&mut header[1..])?;
    Ok(Some(header))
}

fn read_request(
    reader: &mut impl Read,
) -> Result<Option<TranscriptionRequest>, WhisperBridgeError> {
    let Some(header) = read_header(reader)? else {
        return Ok(None);
    };
    let metadata_length = u32::from_le_bytes(header[..4].try_into().unwrap()) as usize;
    let pcm_length = u32::from_le_bytes(header[4..].try_into().unwrap()) as usize;
    if metadata_length == 0
        || metadata_length > MAX_METADATA_BYTES
        || pcm_length == 0
        || pcm_length > MAX_PCM_BYTES
        || pcm_length % 4 != 0
    {
        return Err(WhisperBridgeError::InvalidFrame);
    }
    let mut metadata_bytes = vec![0_u8; metadata_length];
    reader.read_exact(&mut metadata_bytes)?;
    let mut pcm_bytes = vec![0_u8; pcm_length];
    reader.read_exact(&mut pcm_bytes)?;
    let metadata: RequestMetadata = serde_json::from_slice(&metadata_bytes)?;
    let expected_pcm = metadata
        .sample_count
        .checked_mul(4)
        .ok_or(WhisperBridgeError::InvalidMetadata)?;
    if metadata.protocol != PROTOCOL_VERSION
        || metadata.sample_rate != SAMPLE_RATE
        || metadata.sample_count == 0
        || expected_pcm != pcm_length
        || metadata.language.is_empty()
        || metadata.language.len() > 16
        || !metadata
            .language
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || character == '-')
    {
        return Err(WhisperBridgeError::InvalidMetadata);
    }
    let mut samples = Vec::with_capacity(metadata.sample_count);
    for chunk in pcm_bytes.chunks_exact(4) {
        let value = f32::from_le_bytes(chunk.try_into().unwrap());
        if !value.is_finite() {
            return Err(WhisperBridgeError::InvalidFrame);
        }
        samples.push(value.clamp(-1.0, 1.0));
    }
    Ok(Some(TranscriptionRequest { metadata, samples }))
}

fn write_response(
    writer: &mut impl Write,
    response: &TranscriptionResponse,
) -> Result<(), WhisperBridgeError> {
    let payload = serde_json::to_vec(response)?;
    if payload.len() > MAX_RESPONSE_BYTES || payload.len() > u32::MAX as usize {
        return Err(WhisperBridgeError::InvalidFrame);
    }
    writer.write_all(&(payload.len() as u32).to_le_bytes())?;
    writer.write_all(&payload)?;
    writer.flush()?;
    Ok(())
}

pub fn run_stdio<I>(args: I) -> Result<(), WhisperBridgeError>
where
    I: IntoIterator<Item = OsString>,
{
    let config = parse_args(args)?;
    let mut engine = WhisperEngine::new(config);
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut reader = BufReader::new(stdin.lock());
    let mut writer = BufWriter::new(stdout.lock());
    while let Some(request) = read_request(&mut reader)? {
        let response = engine.transcribe(request)?;
        write_response(&mut writer, &response)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn parses_cpu_configuration_and_clamps_threads() {
        let config = parse_args([
            OsString::from("--model"),
            OsString::from("model.bin"),
            OsString::from("--backend"),
            OsString::from("cpu"),
            OsString::from("--threads"),
            OsString::from("100"),
        ])
        .unwrap();
        assert_eq!(config.model, PathBuf::from("model.bin"));
        assert_eq!(config.backend, "cpu");
        assert_eq!(config.threads, 64);
    }

    #[test]
    fn rejects_uncompiled_gpu_backend_instead_of_claiming_acceleration() {
        let result = parse_args([
            OsString::from("--model"),
            OsString::from("model.bin"),
            OsString::from("--backend"),
            OsString::from("vulkan"),
        ]);
        assert!(matches!(
            result,
            Err(WhisperBridgeError::UnsupportedBackend)
        ));
    }

    #[test]
    fn decodes_binary_pcm_frame_with_validated_metadata() {
        let metadata = serde_json::json!({
            "protocol": 1,
            "sampleRate": 16000,
            "language": "en",
            "sampleCount": 3,
            "wordTimestamps": false
        });
        let metadata = serde_json::to_vec(&metadata).unwrap();
        let samples = [0.0_f32, 0.5_f32, -0.5_f32];
        let pcm = samples
            .iter()
            .flat_map(|sample| sample.to_le_bytes())
            .collect::<Vec<_>>();
        let mut frame = Vec::new();
        frame.extend_from_slice(&(metadata.len() as u32).to_le_bytes());
        frame.extend_from_slice(&(pcm.len() as u32).to_le_bytes());
        frame.extend_from_slice(&metadata);
        frame.extend_from_slice(&pcm);
        let request = read_request(&mut Cursor::new(frame)).unwrap().unwrap();
        assert_eq!(request.metadata.sample_rate, 16000);
        assert_eq!(request.samples, samples);
    }

    #[test]
    fn rejects_sample_count_that_does_not_match_pcm_bytes() {
        let metadata = serde_json::json!({
            "protocol": 1,
            "sampleRate": 16000,
            "language": "en",
            "sampleCount": 2
        });
        let metadata = serde_json::to_vec(&metadata).unwrap();
        let pcm = 0.0_f32.to_le_bytes();
        let mut frame = Vec::new();
        frame.extend_from_slice(&(metadata.len() as u32).to_le_bytes());
        frame.extend_from_slice(&(pcm.len() as u32).to_le_bytes());
        frame.extend_from_slice(&metadata);
        frame.extend_from_slice(&pcm);
        assert!(matches!(
            read_request(&mut Cursor::new(frame)),
            Err(WhisperBridgeError::InvalidMetadata)
        ));
    }

    #[test]
    fn writes_length_prefixed_json_response() {
        let response = TranscriptionResponse {
            protocol: 1,
            text: String::from("hello"),
            language: String::from("en"),
        };
        let mut output = Vec::new();
        write_response(&mut output, &response).unwrap();
        let length = u32::from_le_bytes(output[..4].try_into().unwrap()) as usize;
        assert_eq!(length, output.len() - 4);
        let payload: serde_json::Value = serde_json::from_slice(&output[4..]).unwrap();
        assert_eq!(payload["text"], "hello");
        assert_eq!(payload["language"], "en");
    }
}
