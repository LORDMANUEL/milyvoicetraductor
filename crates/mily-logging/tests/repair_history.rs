use mily_logging::{LogService, RepairStatus};
use tempfile::tempdir;

#[test]
fn repair_history_is_structured_sanitized_and_correlated() {
    let dir = tempdir().unwrap();
    let service = LogService::new(dir.path(), 64 * 1024, 2);
    let incident = service.new_incident_id("bootstrap");

    service
        .record_repair(
            &incident,
            RepairStatus::Started,
            "bootstrap",
            "RUNTIME_IMPORT",
            "RUNTIME_IMPORT_FAILED",
            "Fallo para user@example.com token=secret123 en C:\\Users\\Luis\\AppData",
            "Revalidar runtime privado",
        )
        .unwrap();
    service
        .record_repair(
            &incident,
            RepairStatus::Succeeded,
            "bootstrap",
            "BOOTSTRAP_FINALIZE",
            "BOOTSTRAP_OK",
            "Runtime reparado",
            "Ninguna",
        )
        .unwrap();

    let events = service.recent_repairs(10).unwrap();
    assert_eq!(events.len(), 2);
    assert_eq!(events[0].incident_id, incident);
    assert_eq!(events[0].status, RepairStatus::Succeeded);
    assert_eq!(events[1].status, RepairStatus::Started);
    assert!(!events[1].message.contains("secret123"));
    assert!(!events[1].message.contains("user@example.com"));
    assert!(!events[1].message.contains("Luis"));
    assert!(dir.path().join("repair-history.jsonl").is_file());
}

#[test]
fn repair_history_limit_returns_only_newest_events() {
    let dir = tempdir().unwrap();
    let service = LogService::new(dir.path(), 64 * 1024, 2);
    for index in 0..5 {
        service
            .record_repair(
                &format!("incident-{index}"),
                RepairStatus::Failed,
                "installer",
                "TEST",
                "TEST_FAILURE",
                &format!("failure {index}"),
                "retry",
            )
            .unwrap();
    }
    let events = service.recent_repairs(2).unwrap();
    assert_eq!(events.len(), 2);
    assert_eq!(events[0].incident_id, "incident-4");
    assert_eq!(events[1].incident_id, "incident-3");
}
