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
    #[serde(default)]
    route: Option<String>,
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
    let mut args = std::env::args_os();
    let _program = args.next();
    let first = args.next().unwrap_or_default();
    let first_text = first.to_string_lossy();

    // El mismo binario incluido por el instalador sirve como Native Messaging
    // y como bridge privado de whisper.cpp. Los protocolos nunca se mezclan.
    if matches!(first_text.as_ref(), "--stdio" | "--whispercpp-stdio") {
        if whispercpp::run_stdio(args).is_err() {
            std::process::exit(2);
        }
        return;
    }

    // Chromium pasa el origen de la extensión como primer argumento. El manifiesto
    // allowed_origins ya limita el acceso; este chequeo agrega defensa en profundidad.
    let origin = first_text.into_owned();
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

        let result = match request.r#type.as_str() {
            "hello" => runtime.status(true),
            "status" => runtime.status(false),
            "prepare-route" => {
                let Some(route) = request.route.as_deref() else {
                    let _ = write_json(
                        &mut writer,
                        &ErrorReply {
                            protocol: 1,
                            r#type: "bridge.error",
                            code: "BRIDGE_ROUTE_REQUIRED",
                            message: "prepare-route requiere una ruta Tier 1.",
                        },
                    );
                    continue;
                };
                runtime.prepare_route(route)
            }
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

        match result {
            Ok(reply) => {
                if write_json(&mut writer, &reply).is_err() {
                    break;
                }
            }
            Err(error) => {
                if write_json(
                    &mut writer,
                    &ErrorReply {
                        protocol: 1,
                        r#type: "bridge.error",
                        code: error.public_code(),
                        message: error.public_message(),
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
