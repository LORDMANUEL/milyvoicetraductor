use milyvoicetraductor_desktop_lib::native_bootstrap::{
    BootstrapLayout, build_native_host_manifest, parse_expected_sha256,
};
use std::path::Path;
use tempfile::tempdir;

#[test]
fn native_bootstrap_resolves_only_bundled_resources_beside_desktop() {
    let root = tempdir().unwrap();
    let layout = BootstrapLayout::from_install_root(root.path());
    assert_eq!(layout.bootstrap_root, root.path().join("bootstrap"));
    assert_eq!(
        layout.runtime_zip,
        root.path()
            .join("bootstrap")
            .join("runtime")
            .join("milyvoice-python-runtime.zip")
    );
    assert_eq!(
        layout.bridge_source,
        root.path()
            .join("bootstrap")
            .join("bridge")
            .join("milyvoice-bridge.exe")
    );
}

#[test]
fn runtime_sha_parser_accepts_standard_checksum_line() {
    let hash = "a".repeat(64);
    assert_eq!(
        parse_expected_sha256(&format!("{hash} *milyvoice-python-runtime.zip\n")).unwrap(),
        hash
    );
}

#[test]
fn runtime_sha_parser_rejects_malformed_hash() {
    assert!(parse_expected_sha256("not-a-sha runtime.zip").is_err());
}

#[test]
fn native_host_manifest_uses_exact_local_bridge_path() {
    let template = r#"{
      "name":"com.milyvoice.traductor",
      "path":"__BRIDGE_PATH__",
      "type":"stdio",
      "allowed_origins":["chrome-extension://edcpjonegaempcifgodcmgejbcpdpddm/"]
    }"#;
    let bridge = Path::new(r"C:\Users\Public\MilyVoiceTraductor\bridge\milyvoice-bridge.exe");
    let payload = build_native_host_manifest(template, bridge).unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&payload).unwrap();
    assert_eq!(parsed["path"].as_str(), Some(bridge.to_string_lossy().as_ref()));
    assert_eq!(parsed["name"], "com.milyvoice.traductor");
    assert_eq!(parsed["allowed_origins"].as_array().unwrap().len(), 1);
}
