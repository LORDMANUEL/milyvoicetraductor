use mily_supervisor::{
    ComponentDescriptor, ComponentHealth, ComponentStage, HealthStatus, ProductDescriptor,
    ProductManifest, Supervisor,
};

fn manifest_with_two_components() -> ProductManifest {
    ProductManifest {
        product: ProductDescriptor {
            name: "MilyVoiceTraductor".into(),
            version: "3.0.0-alpha.1".into(),
        },
        components: vec![
            ComponentDescriptor {
                id: "supervisor".into(),
                version: "1.0.0".into(),
                contract: "supervisor/v1".into(),
                stage: ComponentStage::Candidate,
                required: true,
            },
            ComponentDescriptor {
                id: "audio".into(),
                version: "1.0.0".into(),
                contract: "audio/v1".into(),
                stage: ComponentStage::Development,
                required: false,
            },
        ],
    }
}

#[test]
fn supervisor_starts_known_components_in_manifest_order() {
    let supervisor = Supervisor::new(manifest_with_two_components()).unwrap();
    let snapshot = supervisor.snapshot();

    assert_eq!(snapshot.len(), 2);
    assert_eq!(snapshot[0].component_id, "supervisor");
    assert_eq!(snapshot[0].status, HealthStatus::Starting);
    assert_eq!(snapshot[1].component_id, "audio");
    assert_eq!(snapshot[1].status, HealthStatus::Starting);
}

#[test]
fn known_component_health_can_be_updated() {
    let mut supervisor = Supervisor::new(manifest_with_two_components()).unwrap();

    supervisor
        .report_health(ComponentHealth {
            component_id: "supervisor".into(),
            status: HealthStatus::Healthy,
            reason: Some("ready".into()),
        })
        .unwrap();

    let snapshot = supervisor.snapshot();
    assert_eq!(snapshot[0].status, HealthStatus::Healthy);
    assert_eq!(snapshot[0].reason.as_deref(), Some("ready"));
}

#[test]
fn unknown_component_health_is_rejected_without_mutating_snapshot() {
    let mut supervisor = Supervisor::new(manifest_with_two_components()).unwrap();
    let before = supervisor.snapshot();

    let result = supervisor.report_health(ComponentHealth {
        component_id: "unknown".into(),
        status: HealthStatus::Unhealthy,
        reason: Some("not registered".into()),
    });

    assert!(result.is_err());
    assert_eq!(supervisor.snapshot(), before);
}

#[test]
fn subsequent_updates_do_not_change_snapshot_order() {
    let mut supervisor = Supervisor::new(manifest_with_two_components()).unwrap();

    supervisor
        .report_health(ComponentHealth {
            component_id: "audio".into(),
            status: HealthStatus::Degraded,
            reason: Some("high latency".into()),
        })
        .unwrap();

    let snapshot = supervisor.snapshot();
    let ids: Vec<&str> = snapshot.iter().map(|item| item.component_id.as_str()).collect();
    assert_eq!(ids, vec!["supervisor", "audio"]);
}
