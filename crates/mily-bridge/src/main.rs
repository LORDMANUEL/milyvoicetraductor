#![cfg_attr(all(windows, not(debug_assertions)), windows_subsystem = "windows")]

mod protocol;
mod runtime;
mod whispercpp;

use protocol::{ProtocolError, read_frame, write_frame};
use runtime::{BridgeRuntime, caller_origin_allowed};
use serde::{Deserialize, Serialize};
use std::io::{self, BufReader, BufWriter};

#[derive(Debug, Deserialize)]
struct BridgeRequest {
    protocol: u8,
    r#type: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ErrorReply<'a> {
    protocol: u8,
    r#type: &'static str,
    code: &'a str,
    message: &'a str,
}

fn write_json<T: Serialize>(writer: &mut impl io::Write, value: &T) -> Result<(), ProtocolError> {
    let payload = serde_json::to_vec(value).map_err(|error| {
        ProtocolError::Io(io::Error::new(
            io::ErrorKind::InvalidData,
            error.to_string(),
        ))
    })?;
    write_frame(writer, &payload)
}

fn main() {
    let mut args = std::env::args();
    let _program = args.next();
    let first = args.next().unwrap_or_default();

    // El mismo binario incluido por el instalador sirve como Native Messaging
    // y como bridge privado de whisper.cpp. Los protocolos nunca se mezclan.
    if matches!(first.as_str(), "--stdio" | "--whispercpp-stdio") {
        if whispercpp::run_stdio(args).is_err() {
            std::process::exit(2);
        }
        return;
    }

    // Chromium pasa el origen de la extensión como primer argumento. El manifiesto
    // allowed_origins ya limita el acceso; este chequeo agrega defensa en profundidad.
    let origin = first;
    if !caller_origin_allowed(&origin) {
        return;
    }

    let runtime = match BridgeRuntime::discover() {
        Ok(runtime) => runtime,
        Err(_) => return,
    };
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut reader = BufReader::new(stdin.lock());
    let mut writer = BufWriter::new(stdout.lock());

    loop {
        let payload = match read_frame(&mut reader) {
            Ok(payload) => payload,
            Err(ProtocolError::Truncated) => break,
            Err(_) => break,
        };
        let request = match serde_json::from_slice::<BridgeRequest>(&payload) {
            Ok(request) if request.protocol == 1 => request,
            _ => {
                let _ = write_json(
                    &mut writer,
                    &ErrorReply {
                        protocol: 1,
                        r#type: "bridge.error",
                        code: "BRIDGE_PROTOCOL",
                        message: "Solicitud Native Messaging no válida.",
                    },
                );
                continue;
            }
        };

        let ensure_started = match request.r#type.as_str() {
            "hello" => true,
            "status" => false,
            _ => {
                let _ = write_json(
                    &mut writer,
                    &ErrorReply {
                        protocol: 1,
                        r#type: "bridge.error",
                        code: "BRIDGE_COMMAND",
                        message: "Comando no permitido.",
                    },
                );
                continue;
            }
        };

        match runtime.status(ensure_started) {
            Ok(reply) => {
                if write_json(&mut writer, &reply).is_err() {
                    break;
                }
            }
            Err(_) => {
                if write_json(
                    &mut writer,
                    &ErrorReply {
                        protocol: 1,
                        r#type: "bridge.error",
                        code: "BRIDGE_RUNTIME",
                        message: "No se pudo consultar el runtime local.",
                    },
                )
                .is_err()
                {
                    break;
                }
            }
        }
    }
}
