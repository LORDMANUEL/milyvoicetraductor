use mily_engine::hardware_runtime_environment;

#[test]
fn runtime_environment_exposes_cpu_topology_to_python_sidecar() {
    let env = hardware_runtime_environment();
    let physical = env
        .iter()
        .find(|(key, _)| key == "MILY_PHYSICAL_CPUS")
        .expect("physical core count must be propagated")
        .1
        .parse::<usize>()
        .unwrap();
    let logical = env
        .iter()
        .find(|(key, _)| key == "MILY_LOGICAL_CPUS")
        .expect("logical core count must be propagated")
        .1
        .parse::<usize>()
        .unwrap();

    assert!(physical >= 1);
    assert!(logical >= physical);
    assert!(env.iter().any(|(key, _)| key == "MILY_CPU_AVX2"));
    assert!(env.iter().any(|(key, _)| key == "MILY_CPU_FMA"));
}
