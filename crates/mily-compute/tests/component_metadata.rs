use serde_json::Value;

#[test]
fn compute_component_metadata_declares_independent_v3_identity() {
    let metadata: Value = serde_json::from_str(include_str!("../COMPONENT.json")).unwrap();

    assert_eq!(metadata["id"], "compute");
    assert_eq!(metadata["package"], "mily-compute");
    assert_eq!(metadata["version"], "2.0.0");
    assert_eq!(metadata["contract"], "compute/v1");
    assert_eq!(metadata["stage"], "candidate");
}
