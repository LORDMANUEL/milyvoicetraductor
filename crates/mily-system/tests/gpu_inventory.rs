use mily_system::{GpuVendor, classify_gpu_vendor};

#[test]
fn classifies_common_gpu_pci_vendors_without_driver_specific_logic() {
    assert_eq!(classify_gpu_vendor(0x8086), GpuVendor::Intel);
    assert_eq!(classify_gpu_vendor(0x10DE), GpuVendor::Nvidia);
    assert_eq!(classify_gpu_vendor(0x1002), GpuVendor::Amd);
    assert_eq!(classify_gpu_vendor(0x1414), GpuVendor::Microsoft);
}

#[test]
fn preserves_unknown_vendor_id_instead_of_guessing_support() {
    assert_eq!(
        classify_gpu_vendor(0x1234),
        GpuVendor::Other { vendor_id: 0x1234 }
    );
}
