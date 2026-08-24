use mily_supervisor::{ComponentDescriptor, ComponentStage, ProductDescriptor, ProductManifest};

fn valid_manifest() -> ProductManifest {
    ProductManifest {
        product: ProductDescriptor {
            name: "MilyVoiceTraductor".into(),
            version: "3.0.0-alpha.1".into(),
        },
        components: vec![ComponentDescriptor {
            id: "supervisor".into(),
            version: "1.0.0".into(),
            contract: "supervisor/v1".into(),
            stage: ComponentStage::Candidate,
            required: true,
        }],
    }
}

#[test]
fn valid_manifest_is_accepted() {
    valid_manifest().validate().unwrap();
}

#[test]
fn duplicate_component_ids_are_rejected() {
    let mut manifest = valid_manifest();
    manifest.components.push(manifest.components[0].clone());
    assert!(manifest.validate().is_err());
}

#[test]
fn malformed_component_identity_is_rejected() {
    let mut manifest = valid_manifest();
    manifest.components[0].id = "Bad_ID".into();
    assert!(manifest.validate().is_err());
}

#[test]
fn malformed_component_version_is_rejected() {
    let mut manifest = valid_manifest();
    manifest.components[0].version = "1.0".into();
    assert!(manifest.validate().is_err());
}

#[test]
fn malformed_contract_is_rejected() {
    let mut manifest = valid_manifest();
    manifest.components[0].contract = "supervisor/latest".into();
    assert!(manifest.validate().is_err());
}

#[test]
fn empty_component_list_is_rejected() {
    let mut manifest = valid_manifest();
    manifest.components.clear();
    assert!(manifest.validate().is_err());
}

#[test]
fn malformed_hyphen_rules_are_rejected() {
    for invalid in ["-audio", "audio-", "audio--capture", "2audio"] {
        let mut manifest = valid_manifest();
        manifest.components[0].id = invalid.into();
        assert!(manifest.validate().is_err(), "{invalid} must be rejected");
    }
}

#[test]
fn contract_major_zero_is_rejected() {
    let mut manifest = valid_manifest();
    manifest.components[0].contract = "supervisor/v0".into();
    assert!(manifest.validate().is_err());
}
